"""Fixed-recipe QLoRA preflight/train/eval; immutable inputs, bounded execution."""
import argparse
from contextlib import nullcontext
from datetime import datetime
import gc
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import random
import signal
import time

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/training/sft_resumption_v1'
WEIGHTS = ROOT / 'runtime/sft_weights_recovery_v1'
PLAN = ROOT / 'configs/sft_three_arm_runtime_v1.json'
RESULTS = ROOT / 'results/sft_three_arm_v1'
ARMS = ('ordinary_sft', 'evidence_sft')
PINS = {'torch':'2.8.0','transformers':'4.57.1','peft':'0.17.1','bitsandbytes':'0.48.1',
        'accelerate':'1.10.1','huggingface-hub':'0.35.3','tokenizers':'0.22.2','safetensors':'0.6.2','Jinja2':'3.1.6'}


def read(path): return json.loads(Path(path).read_text())
def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        while b := f.read(1024**2): h.update(b)
    return h.hexdigest()
def save(path, obj):
    path = Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as f: json.dump(obj,f,ensure_ascii=False,indent=2);f.write('\n')
def rows(path): return [json.loads(s) for s in Path(path).read_text().splitlines()]
def safe_json(obj): return json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).replace('<','\\u003c')


def padded_record(row, pad_id, multiple=8):
    n = len(row['input_ids']); extra = (-n) % multiple
    if n != len(row['labels']) or n != len(row['attention_mask']): raise ValueError('Length mismatch')
    p, a = row['prompt_tokens'], row['answer_tokens']
    if row['labels'][:p] != [-100]*p or row['labels'][p:p+a] != row['input_ids'][p:p+a]: raise ValueError('Mask mismatch')
    if any(x != -100 for x in row['labels'][p+a:]): raise ValueError('Trailing label leak')
    if n > 4096 or a > 1024 or a < 1: raise ValueError('No truncation')
    return {'input_ids':row['input_ids']+[pad_id]*extra,
            'attention_mask':row['attention_mask']+[0]*extra,
            'labels':row['labels']+[-100]*extra}


def data_gate():
    manifest = read(DATA/'manifest.json')
    assert manifest['data_qualified'] is True and manifest['split_overlap'] == 0
    for n,h in manifest['files'].items(): assert sha(DATA/n)==h,n
    assert (manifest['train_events'],manifest['validation_events'],manifest['final_events'])==(64,12,24)
    return manifest


def source_gate():
    plan=read(PLAN)
    for n,h in plan['source_hashes'].items(): assert sha(ROOT/n)==h,n
    data_gate()
    receipt=read(WEIGHTS/'receipt.json')
    assert receipt['status']=='all_22_files_verified_gpu_preflight_pending'
    assert receipt['revision']=='9216db5781bf21249d130ec9da846c4624c16137'
    assert len(receipt['files'])==22
    for f in receipt['files']:
        assert (WEIGHTS/f['file']).stat().st_size==f['bytes']
        assert f['upstream_hash_verified'] is True
    versions={k:importlib.metadata.version(k) for k in PINS}
    assert versions==PINS,versions
    assert os.environ.get('SLURM_JOB_ID')
    return plan,versions


def load_base(training):
    import torch
    from transformers import AutoModelForCausalLM, BitsAndBytesConfig
    from peft import prepare_model_for_kbit_training
    assert torch.cuda.is_available() and torch.cuda.device_count()==1 and torch.cuda.is_bf16_supported()
    config=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type='nf4',
        bnb_4bit_use_double_quant=True,bnb_4bit_compute_dtype=torch.bfloat16)
    model=AutoModelForCausalLM.from_pretrained(str(WEIGHTS),local_files_only=True,
        trust_remote_code=False,quantization_config=config,dtype=torch.bfloat16,
        device_map={'':0},low_cpu_mem_usage=True,attn_implementation='sdpa')
    # Apply identical frozen non-quantized dtypes to all three arms. Training prep
    # casts some layers to fp32; doing the same for base prevents a hidden baseline change.
    model=prepare_model_for_kbit_training(model,use_gradient_checkpointing=training,
        gradient_checkpointing_kwargs={'use_reentrant':False})
    model.config.use_cache=False
    assert all(p.device.type=='cuda' for p in model.parameters())
    return model


def fresh_adapter(model):
    from peft import LoraConfig,get_peft_model
    cfg=LoraConfig(r=8,lora_alpha=16,lora_dropout=0.0,target_modules='all-linear',
        bias='none',task_type='CAUSAL_LM')
    result=get_peft_model(model,cfg)
    trainable=[(n,p) for n,p in result.named_parameters() if p.requires_grad]
    assert trainable and all('lora_' in n for n,p in trainable)
    assert all('lora_' in n or not p.requires_grad for n,p in result.named_parameters())
    return result


def tensor_batch(record,pad):
    import torch
    return {k:torch.tensor([v],dtype=torch.long,device='cuda') for k,v in padded_record(record,pad).items()}


def verify_tokenizer(tokenizer,row,system):
    prompt=tokenizer.apply_chat_template([{'role':'system','content':system},
        {'role':'user','content':safe_json(row['input'])}],tokenize=True,
        add_generation_prompt=True,enable_thinking=False)
    expected=row['tokens']['input_ids'][:row['tokens']['prompt_tokens']] if 'tokens' in row else row['input_ids']
    assert prompt==expected,'HF tokenizer/template differs from frozen export'
    if 'tokens' in row:
        answer=tokenizer.encode(safe_json(row['target'])+'<|im_end|>',add_special_tokens=False)
        p,a=row['tokens']['prompt_tokens'],row['tokens']['answer_tokens']
        assert answer==row['tokens']['labels'][p:p+a] and answer[-1]==tokenizer.eos_token_id


def finite_grad(model):
    import torch
    gradients=[p.grad for p in model.parameters() if p.requires_grad and p.grad is not None]
    assert gradients and all(torch.isfinite(g).all().item() for g in gradients)
    assert any(torch.count_nonzero(g).item()>0 for g in gradients)
    norm=torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad],1.0)
    assert torch.isfinite(norm).item()
    return float(norm)


def make_optimizer(model):
    import torch
    return torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],lr=2e-4,
        betas=(0.9,0.999),eps=1e-8,weight_decay=0.0)


def adapter_identity(model):
    h=hashlib.sha256()
    for name,p in model.named_parameters():
        if p.requires_grad:
            h.update(name.encode());h.update(p.detach().float().cpu().numpy().tobytes())
    return h.hexdigest()


def inference(model,ids,tokenizer):
    import torch
    model.eval()
    tensor=torch.tensor([ids],dtype=torch.long,device='cuda')
    torch.cuda.synchronize();start=time.monotonic()
    with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):
        result=model.generate(input_ids=tensor,attention_mask=torch.ones_like(tensor),
            max_new_tokens=1024,do_sample=False,num_beams=1,use_cache=True,
            eos_token_id=tokenizer.eos_token_id,pad_token_id=tokenizer.pad_token_id)
    torch.cuda.synchronize()
    output=result[0,len(ids):].tolist()
    return {'output_ids':output,'output':tokenizer.decode(output,skip_special_tokens=True),
        'input_tokens':len(ids),'output_tokens':len(output),'seconds':time.monotonic()-start,
        'finished_with_eos':bool(output and output[-1]==tokenizer.eos_token_id)}


def preflight(out,report,tokenizer,system):
    import torch
    from transformers import set_seed
    report['arms']=[]
    # Standalone small-tensor loss check: masked prompt/pad logits cannot affect CE.
    logits=torch.randn(1,8,11); labels=torch.tensor([[-100,-100,-100,3,4,5,-100,-100]])
    def loss(x): return torch.nn.functional.cross_entropy(x[:,:-1].reshape(-1,11),labels[:,1:].reshape(-1),ignore_index=-100)
    changed=logits.clone(); changed[:,0:2]=1000;changed[:,5:]=1000
    assert torch.allclose(loss(logits),loss(changed),atol=0,rtol=0)
    report['padding_loss_verified']=True
    for arm in ARMS:
        set_seed(42);torch.cuda.reset_peak_memory_stats()
        candidates=rows(DATA/(arm+'.jsonl'))
        chosen=max(candidates,key=lambda r:r['tokens']['sequence_tokens'])
        verify_tokenizer(tokenizer,chosen,system)
        started=time.monotonic();model=fresh_adapter(load_base(True));torch.cuda.synchronize()
        load_seconds=time.monotonic()-started
        count=sum(p.numel() for p in model.parameters() if p.requires_grad)
        initialization_sha=adapter_identity(model)
        optimizer=make_optimizer(model)
        batch=tensor_batch(chosen['tokens'],tokenizer.pad_token_id)
        model.train();torch.cuda.synchronize();started=time.monotonic()
        with torch.autocast('cuda',dtype=torch.bfloat16): result=model(**batch)
        assert torch.isfinite(result.loss).item()
        initial_loss=float(result.loss.detach());result.loss.backward();norm=finite_grad(model)
        optimizer.step();optimizer.zero_grad(set_to_none=True);torch.cuda.synchronize()
        step_seconds=time.monotonic()-started
        peak=torch.cuda.max_memory_allocated();reserved=torch.cuda.max_memory_reserved()
        path=out/arm/'adapter';model.save_pretrained(path,safe_serialization=True)
        del result,batch,optimizer
        model.eval(); probe=torch.tensor([chosen['tokens']['input_ids'][:32]],device='cuda')
        with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16): before=model(probe).logits[:,-1].float().cpu()
        model.load_adapter(str(path),adapter_name='saved_reload',is_trainable=False)
        model.set_adapter('saved_reload')
        with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16): after=model(probe).logits[:,-1].float().cpu()
        delta=float((before-after).abs().max())
        assert torch.allclose(before,after,atol=1e-4,rtol=1e-4),'Saved adapter reload mismatch'
        # Technical probes only, not validation/final: generation has no quality gate.
        prompt=chosen['tokens']['input_ids'][:chosen['tokens']['prompt_tokens']]
        report['generation_calls']+=1
        generated=inference(model,prompt,tokenizer)
        save(out/arm/'generation.json',generated)
        record={'arm':arm,'example_id':chosen['metadata']['example_id'],'sequence_tokens':chosen['tokens']['sequence_tokens'],
            'trainable_parameters':count,'finite_loss':initial_loss,'gradient_norm':norm,
            'initialization_sha256':initialization_sha,
            'peak_allocated_bytes':peak,'peak_reserved_bytes':reserved,'load_seconds':load_seconds,
            'one_step_seconds':step_seconds,'save_reload_max_abs_logit_diff':delta,
            'conservative_128_microbatch_seconds':load_seconds+128*step_seconds+120,
            'generated_tokens':generated['output_tokens']}
        report['arms'].append(record);save(out/arm/'receipt.json',record);print(json.dumps(record),flush=True)
        del model,probe,before,after;gc.collect();torch.cuda.empty_cache()
    assert all(r['conservative_128_microbatch_seconds']<2550 for r in report['arms']),'Training time budget not feasible'
    assert len({r['initialization_sha256'] for r in report['arms']})==1,'Adapter initializations differ'
    report.update(status='passed',gpu_preflight_passed=True,training_eligible=True)


def train(arm,out,report,tokenizer,system):
    import torch
    from transformers import set_seed,get_linear_schedule_with_warmup
    gate=read(RESULTS/'preflight/receipt.json')
    assert gate['status']=='passed' and gate['training_eligible'] is True
    assert gate['data_manifest_sha256']==sha(DATA/'manifest.json') and gate['plan_sha256']==sha(PLAN)
    trainrows=rows(DATA/(arm+'.jsonl'))
    assert len(trainrows)==64 and all(r['metadata']['split']=='train' for r in trainrows)
    for row in trainrows:verify_tokenizer(tokenizer,row,system)
    set_seed(42);torch.cuda.reset_peak_memory_stats();model=fresh_adapter(load_base(True));model.train()
    report['initialization_sha256']=adapter_identity(model)
    assert report['initialization_sha256']==gate['arms'][0]['initialization_sha256'],'Different training initialization'
    optimizer=make_optimizer(model)
    scheduler=get_linear_schedule_with_warmup(optimizer,num_warmup_steps=2,num_training_steps=16)
    generator=random.Random(42);order=[]
    for _ in range(2):
        epoch=list(range(64));generator.shuffle(epoch);order+=epoch
    save(out/'order.json',{'seed':42,'example_ids':[trainrows[i]['metadata']['example_id'] for i in order]})
    optimizer.zero_grad(set_to_none=True)
    report.update(microbatches=0,optimizer_steps=0,supervised_tokens=0,input_tokens=0)
    try:
        for position,index in enumerate(order):
            row=trainrows[index];batch=tensor_batch(row['tokens'],tokenizer.pad_token_id)
            started=time.monotonic()
            with torch.autocast('cuda',dtype=torch.bfloat16): result=model(**batch)
            assert torch.isfinite(result.loss).item(),'Nonfinite loss'
            raw=float(result.loss.detach());(result.loss/8).backward()
            report['microbatches']+=1;report['supervised_tokens']+=row['tokens']['answer_tokens'];report['input_tokens']+=row['tokens']['sequence_tokens']
            entry={'microbatch':position+1,'example_id':row['metadata']['example_id'],'loss':raw}
            if (position+1)%8==0:
                entry['gradient_norm']=finite_grad(model)
                optimizer.step();scheduler.step();optimizer.zero_grad(set_to_none=True);report['optimizer_steps']+=1
                entry['learning_rate_after_step']=scheduler.get_last_lr()[0]
            torch.cuda.synchronize();entry['seconds']=time.monotonic()-started
            with (out/'training.jsonl').open('a') as f:f.write(json.dumps(entry)+'\n');f.flush()
            print(json.dumps(entry),flush=True);del batch,result
        assert report['microbatches']==128 and report['optimizer_steps']==16
        model.save_pretrained(out/'adapter',safe_serialization=True)
        report.update(status='completed',epochs=2,checkpoint='last_epoch_no_selection',
            adapter_files={p.name:sha(p) for p in (out/'adapter').iterdir() if p.is_file()},
            peak_allocated_bytes=torch.cuda.max_memory_allocated(),peak_reserved_bytes=torch.cuda.max_memory_reserved())
    except BaseException:
        # Save interrupted state for provenance only. It is never selected for evaluation.
        model.save_pretrained(out/'interrupted_adapter',safe_serialization=True)
        raise


def evaluate(out,report,tokenizer,system):
    import torch
    from peft import PeftModel
    for arm in ARMS:
        rec=read(RESULTS/arm/'receipt.json')
        assert rec['status']=='completed' and rec['epochs']==2 and rec['plan_sha256']==sha(PLAN)
        for n,h in rec['adapter_files'].items():assert sha(RESULTS/arm/'adapter'/n)==h
    inputs=rows(DATA/'evaluation_inputs.jsonl')
    assert len(inputs)==36
    for row in inputs: verify_tokenizer(tokenizer,row,system)
    model=load_base(False)
    for arm in ('base',)+ARMS:
        if arm!='base':
            if arm==ARMS[0]:model=PeftModel.from_pretrained(model,str(RESULTS/arm/'adapter'),adapter_name=arm,is_trainable=False)
            else:model.load_adapter(str(RESULTS/arm/'adapter'),adapter_name=arm,is_trainable=False)
            model.set_adapter(arm)
        for row in inputs:
            name=row['metadata']['example_id'];start=datetime.now().astimezone().isoformat()
            request={'arm':arm,'example_id':name,'metadata':row['metadata'],'input_ids':row['input_ids'],
                'started_at':start,'input_sha256':hashlib.sha256(safe_json(row['input']).encode()).hexdigest()}
            save(out/arm/(name+'_request.json'),request)
            report['generation_calls']+=1
            generated=inference(model,row['input_ids'],tokenizer)
            save(out/arm/(name+'_response.json'),generated)
            print(json.dumps({'arm':arm,'example_id':name,'output_tokens':generated['output_tokens'],'seconds':generated['seconds']}),flush=True)
    assert report['generation_calls']==108
    report['status']='completed'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=('preflight','ordinary_sft','evidence_sft','evaluation'))
    stage=parser.parse_args().stage
    plan,versions=source_gate()
    out=RESULTS/stage;out.mkdir(parents=True,exist_ok=False)
    report={'status':'running','stage':stage,'job_id':os.environ['SLURM_JOB_ID'],
        'started_at':datetime.now().astimezone().isoformat(),'plan_sha256':sha(PLAN),
        'data_manifest_sha256':sha(DATA/'manifest.json'),'weights_receipt_sha256':sha(WEIGHTS/'receipt.json'),
        'versions':versions,'generation_calls':0,'training_eligible':False,'automatic_retry':False}
    save(out/'reservation.json',report)
    start=time.monotonic()
    def stop(signum,frame):raise TimeoutError(f'Stage limit signal {signum}')
    for sig in (signal.SIGTERM,signal.SIGALRM,signal.SIGINT):signal.signal(sig,stop)
    signal.alarm(1100 if stage=='preflight' else 2550)
    try:
        import torch
        from transformers import AutoTokenizer
        report['hardware']={'name':torch.cuda.get_device_name(0),'memory':torch.cuda.get_device_properties(0).total_memory}
        tokenizer=AutoTokenizer.from_pretrained(str(WEIGHTS),local_files_only=True,trust_remote_code=False)
        if tokenizer.pad_token_id is None:tokenizer.pad_token=tokenizer.eos_token
        system=read(DATA/'system.json')['system']
        if stage=='preflight':preflight(out,report,tokenizer,system)
        elif stage=='evaluation':evaluate(out,report,tokenizer,system)
        else:train(stage,out,report,tokenizer,system)
    except BaseException as exc:
        report.update(status='failed',error=type(exc).__name__+': '+str(exc),training_eligible=False)
        raise
    finally:
        signal.alarm(0)
        report.update(finished_at=datetime.now().astimezone().isoformat(),elapsed_seconds=time.monotonic()-start)
        save(out/'receipt.json',report);print(json.dumps(report),flush=True)

if __name__=='__main__':main()
