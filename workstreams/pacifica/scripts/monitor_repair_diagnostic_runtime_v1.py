"""One bounded inference-only diagnostic on frozen inputs and existing adapters."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import zipfile
import sft_three_arm_runtime_v2 as old

ROOT=old.ROOT
PLAN=ROOT/'configs/monitor_repair_diagnostic_runtime_v1.json'
DATA=ROOT/'data/evaluation/monitor_repair_diagnostic_v1'
OUT=ROOT/'results/monitor_repair_diagnostic_v1'
SUB=ROOT/'results/monitor_repair_diagnostic_v1_submission.json'
ARMS=('base','ordinary_sft','evidence_sft')


def verify():
    p=old.read(PLAN)
    for name,h in p['source_hashes'].items():assert old.sha(ROOT/name)==h,name
    assert p['generation_calls_max']==36 and p['gpu_seconds_max']==5400 and p['retry']==0
    a=old.read(ROOT/'analysis/monitor_repair_diagnostic_data_acceptance_20261015.json')
    assert a['passed'] and a['new_generation_calls']==0 and a['rows']==12
    for arm in ARMS[1:]:
        r=old.read(old.RESULTS/arm/'receipt.json')
        assert r['status']=='completed' and r['epochs']==2
        assert r['plan_sha256']==old.sha(old.PLAN)
    return p


def freeze():
    paths=[Path(__file__),ROOT/'scripts/monitor_interface_v3.py',ROOT/'scripts/score_monitor_repair_diagnostic_v1.py',
        ROOT/'scripts/monitor_repair_diagnostic_v1.sbatch',ROOT/'tests/test_monitor_interface_v3.py',
        ROOT/'tests/test_monitor_repair_diagnostic_v1.py',ROOT/'docs/monitor_repair_diagnostic_protocol_2026-10-15.md',
        ROOT/'results/monitor_repair_authorization_20261015.json',
        ROOT/'analysis/monitor_repair_diagnostic_data_acceptance_20261015.json',
        ROOT/'configs/monitor_repair_diagnostic_data_v1.json',old.PLAN,
        ROOT/'docs/sft_semantic_scoring_contract_2026-10-14.md',
        old.RESULTS/'ordinary_sft/receipt.json',old.RESULTS/'evidence_sft/receipt.json']
    paths += [DATA/n for n in ['inputs.jsonl','references.jsonl','system.json','receipt.json']]
    # Bind every old scientific source without changing or copying its contents.
    hashes=old.read(old.PLAN)['source_hashes'].copy()
    hashes.update({str(p.relative_to(ROOT)):old.sha(p) for p in paths})
    old.save(PLAN,{'frozen_at':datetime.now().astimezone().isoformat(),'source_hashes':hashes,
        'generation_calls_max':36,'gpu_seconds_max':5400,'retry':0,'training_runs':0,
        'arms':ARMS,'examples_per_arm':12,'model_revision':'9216db5781bf21249d130ec9da846c4624c16137',
        'max_new_tokens':1024,'new_data_not_for_training':True,'partial_outputs_do_not_tune':True})
    print(json.dumps({'plan_sha256':old.sha(PLAN),'sources':len(hashes)}))


def submit():
    verify()
    assert not SUB.exists() and not OUT.exists(),'Existing attempt; never resubmit'
    q=subprocess.check_output(['squeue','-u','hpcllm_rz377','--noheader'],text=True,timeout=20)
    assert not q.strip(),'Inspect active queue first'
    rec={'status':'submission_started','at':datetime.now().astimezone().isoformat(),'plan_sha256':old.sha(PLAN),'queue_before':q}
    old.save(SUB,rec)
    try:
        cp=subprocess.run(['sbatch','--parsable','scripts/monitor_repair_diagnostic_v1.sbatch'],cwd=ROOT,capture_output=True,text=True,timeout=30)
        rec.update(status='submitted' if cp.returncode==0 else 'failed',returncode=cp.returncode,stdout=cp.stdout,stderr=cp.stderr)
    except BaseException as e:
        rec.update(status='unknown_outcome_do_not_retry',error=repr(e));raise
    finally:
        SUB.write_text(json.dumps(rec,indent=2)+'\n');print(json.dumps(rec),flush=True)
    assert rec['returncode']==0


def run():
    verify()
    _,versions=old.source_gate()
    assert not OUT.exists(),'Existing runtime reservation'
    OUT.mkdir(parents=True)
    rec={'status':'running','job_id':os.environ['SLURM_JOB_ID'],'started_at':datetime.now().astimezone().isoformat(),
         'plan_sha256':old.sha(PLAN),'generation_calls':0,'training_runs':0,'versions':versions,'automatic_retry':False}
    old.save(OUT/'reservation.json',rec)
    started=time.monotonic()
    def stop(sig,frame):raise TimeoutError(f'Frozen runtime limit {sig}')
    for sig in [signal.SIGALRM,signal.SIGTERM,signal.SIGINT]:signal.signal(sig,stop)
    signal.alarm(5250)
    try:
        import torch
        from transformers import AutoTokenizer
        from peft import PeftModel
        tokenizer=AutoTokenizer.from_pretrained(str(old.WEIGHTS),local_files_only=True,trust_remote_code=False)
        if tokenizer.pad_token_id is None:tokenizer.pad_token=tokenizer.eos_token
        inputs=old.rows(DATA/'inputs.jsonl');system=old.read(DATA/'system.json')['system']
        assert len(inputs)==12 and len({r['metadata']['example_id'] for r in inputs})==12
        for row in inputs:
            assert set(row)=={'metadata','input','input_ids'}
            old.verify_tokenizer(tokenizer,row,system)
            assert len(row['input_ids'])+1024<=4096
        for arm in ARMS[1:]:
            rr=old.read(old.RESULTS/arm/'receipt.json')
            for n,h in rr['adapter_files'].items():assert old.sha(old.RESULTS/arm/'adapter'/n)==h
        rec['hardware']={'name':torch.cuda.get_device_name(0),'memory':torch.cuda.get_device_properties(0).total_memory}
        model=old.load_base(False)
        for arm in ARMS:
            if arm=='ordinary_sft':model=PeftModel.from_pretrained(model,str(old.RESULTS/arm/'adapter'),adapter_name=arm,is_trainable=False)
            elif arm=='evidence_sft':model.load_adapter(str(old.RESULTS/arm/'adapter'),adapter_name=arm,is_trainable=False)
            if arm!='base':model.set_adapter(arm)
            for row in inputs:
                assert rec['generation_calls']<36
                eid=row['metadata']['example_id']
                request={'arm':arm,'example_id':eid,'metadata':row['metadata'],'input_ids':row['input_ids'],
                    'input_sha256':row['metadata']['input_sha256'],
                    'rendered_input_sha256':old.hashlib.sha256(old.safe_json(row['input']).encode()).hexdigest(),
                    'started_at':datetime.now().astimezone().isoformat()}
                old.save(OUT/arm/(eid+'_request.json'),request)
                rec['generation_calls']+=1
                output=old.inference(model,row['input_ids'],tokenizer)
                old.save(OUT/arm/(eid+'_response.json'),output)
                print(json.dumps({'arm':arm,'example_id':eid,'output_tokens':output['output_tokens'],'seconds':output['seconds']}),flush=True)
        assert rec['generation_calls']==36
        rec['status']='completed'
    except BaseException as e:
        rec.update(status='failed',error=repr(e));raise
    finally:
        signal.alarm(0);rec.update(finished_at=datetime.now().astimezone().isoformat(),elapsed_seconds=time.monotonic()-started)
        old.save(OUT/'receipt.json',rec);print(json.dumps(rec),flush=True)


def archive():
    sub=old.read(SUB);assert sub['status']=='submitted'
    job=sub['stdout'].strip().split(';')[0];assert job.isdigit()
    q=subprocess.check_output(['squeue','-u','hpcllm_rz377','-h','-o','%i'],text=True,timeout=20)
    assert job not in q.split(),'Job still active'
    acct=subprocess.check_output(['sacct','-j',job,'-n','-P','-o','JobID,State,ExitCode,ElapsedRaw,Start,End,MaxRSS,AllocTRES,NodeList'],text=True,timeout=20)
    line=next(l.split('|') for l in acct.splitlines() if l.split('|')[0]==job)
    assert line[1].split()[0] in {'COMPLETED','FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED','BOOT_FAIL','DEADLINE'}
    files=[SUB]+[p for p in OUT.rglob('*') if p.is_file()]+list((ROOT/'logs').glob(f'monitor_repair_diagnostic_v1-{job}.log'))
    manifest={'job_id':job,'sacct':acct,'queue_at_archive':q,'plan_sha256':old.sha(PLAN),
        'files':{str(p.relative_to(ROOT)):{'sha256':old.sha(p),'bytes':p.stat().st_size} for p in files}}
    dest=ROOT/f'results/monitor_repair_diagnostic_v1_{job}_terminal.zip'
    with zipfile.ZipFile(dest,'x',zipfile.ZIP_DEFLATED) as z:
        for p in files:z.write(p,str(p.relative_to(ROOT)))
        z.writestr('stage_archive_manifest.json',json.dumps(manifest,indent=2))
    receipt={'archive':str(dest.relative_to(ROOT)),'sha256':old.sha(dest),'files':len(files),'sacct':acct}
    old.save(ROOT/f'results/monitor_repair_diagnostic_v1_{job}_archive_receipt.json',receipt)
    print(json.dumps(receipt),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['freeze','verify','submit','run','archive']);a=p.parse_args()
    {'freeze':freeze,'verify':verify,'submit':submit,'run':run,'archive':archive}[a.mode]()
