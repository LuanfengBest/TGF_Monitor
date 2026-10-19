"""One frozen Qwen3.5 deployment comparison; no reference labels at runtime."""
import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path
import time
import tokenizers
from tokenizers import Tokenizer
from monitor_selection_v1 import ROOT, SYSTEM, compact, read, sha, parse_response, validate_output
from ollama_client import Ollama, save

PLAN = ROOT / 'configs/monitor_candidate_v2.json'
TOKENIZER = ROOT / 'data/tokenizers/qwen3_5_9b/tokenizer.json'
MODEL = 'qwen3.5:9b'
MODEL_SHA = '56671c2ab9385f9cfcb404638e32cd62d88e3501d44822208363c010179a3c90'
ARM = 'qwen3_5_9b_general_think'
SOURCE_PATHS = [
    'scripts/monitor_candidate_v2.py', 'scripts/monitor_candidate_v2.sbatch',
    'scripts/download_monitor_candidate_v1.py', 'scripts/download_monitor_candidate_v1.sbatch',
    'scripts/monitor_selection_v1.py', 'scripts/ollama_client.py',
    'scripts/index_visible_evidence.py', 'scripts/native_ollama_tokenizer.py',
    'data/tokenizers/qwen3_5_9b/ollama_manifest.json',
    'data/tokenizers/qwen3_5_9b/provenance.json',
    'data/tokenizers/qwen3_5_9b/tokenizer.json',
    'data/tokenizers/qwen3_5_9b/tokenizer_config.json',
    'data/tokenizers/qwen3_5_9b/chat_template.jinja',
]

def render_text(system, user):
    # Exact official HF template for system + user, text-only, enable_thinking=True.
    return ('<|im_start|>system\n' + system.strip() + '<|im_end|>\n' +
            '<|im_start|>user\n' + user.strip() + '<|im_end|>\n' +
            '<|im_start|>assistant\n<think>\n')

def render(bundle):
    return render_text(SYSTEM, compact(bundle))

class Counter:
    def __init__(self):
        self.tokenizer = Tokenizer.from_file(str(TOKENIZER))
        if self.tokenizer.truncation or self.tokenizer.padding:
            raise ValueError('Tokenizer truncation/padding must be disabled')
    def count(self, prompt):
        return len(self.tokenizer.encode(prompt, add_special_tokens=False).ids)
    def check(self, prompt, predict, ctx=32768):
        n = self.count(prompt)
        if n + predict + 128 > ctx:
            raise ValueError(f'Capacity exceeded: {n}+{predict}+128>{ctx}')
        return n

def payload(plan, prompt, predict):
    return {'model':plan['model'], 'prompt':prompt, 'raw':True, 'stream':False,
            'think':True, 'keep_alive':'10m',
            'options':{'num_ctx':plan['num_ctx'], 'num_predict':predict,
                       'seed':plan['seed'], **plan['sampling']}}

def verify(plan):
    if tokenizers.__version__ != plan['tokenizers_version']:
        raise ValueError('tokenizers version mismatch')
    for path, expected in plan['source_hashes'].items():
        if sha(ROOT/path) != expected: raise ValueError(f'Frozen source changed: {path}')
    for entry in plan['inputs']:
        if sha(ROOT/entry['path']) != entry['sha256']: raise ValueError('Frozen input changed')
    if hashlib.sha256(SYSTEM.encode()).hexdigest() != plan['system_sha256']:
        raise ValueError('System prompt changed')

def freeze():
    if PLAN.exists(): raise RuntimeError('Candidate plan already frozen')
    parent = read(ROOT/'configs/monitor_selection_v1.json')
    counter = Counter()
    plan = {'protocol':'monitor_candidate_v2', 'model':MODEL, 'model_digest':MODEL_SHA,
            'arm':ARM, 'split':parent['split'], 'family':parent['family'],
            'inputs':parent['inputs'], 'system_sha256':parent['system_sha256'],
            'num_ctx':32768, 'num_predict':6144, 'seed':42,
            'sampling':{'temperature':1.0,'top_p':0.95,'top_k':20,'min_p':0.0,
                        'presence_penalty':1.5,'frequency_penalty':0.0,
                        'repeat_penalty':1.0,'repeat_last_n':-1},
            'tokenizers_version':tokenizers.__version__, 'max_calls':15,
            'max_gpu_seconds':1800, 'max_download_cpu_wall_seconds':1200,
            'automatic_retries':0, 'max_consecutive_output_failures':2,
            'sources':['https://huggingface.co/Qwen/Qwen3.5-9B',
                       'https://docs.ollama.com/modelfile'],
            'limitations':['one development family; selected-event diagnostic',
                           '6144 output cap is deployment budget, below vendor general recommendation',
                           'architecture, size, quantization, backend and sampling differ from Qwen3'],
            'calibrations':[]}
    calibration_texts = [
        ('calibration_tiny', 'Token counting calibration. Reply OK.', 'Hello.'),
        ('calibration_mixed', 'Token counting calibration. Reply OK.',
         'Quoted JSON: {"amount":1717.50,"state":"scheduled"}\nYAML: - id_: 41\n'
         'Line\r\nspaces  tabs\t escaped \\u003c; Unicode: 银行 café—€ 😀\n'
         '<tool_response>opaque</tool_response>\n' * 24),
    ]
    for iid,system,user in calibration_texts:
        prompt=render_text(system,user)
        plan['calibrations'].append({'input_id':iid,'prompt':prompt,'num_predict':16,
                                     'expected_prompt_tokens':counter.check(prompt,16)})
    plan['capacity']={e['input_id']:counter.check(render(read(ROOT/e['path'])),6144)
                      for e in plan['inputs']}
    plan['source_hashes']={p:sha(ROOT/p) for p in SOURCE_PATHS}
    save(PLAN,plan)
    print(json.dumps({'max_calls':15,'capacity':plan['capacity'],
                      'calibration_counts':[c['expected_prompt_tokens'] for c in plan['calibrations']]}))

def run(out):
    plan=read(PLAN); verify(plan)
    out.mkdir(parents=True,exist_ok=False)
    with (ROOT/'results/monitor_candidate_v2.reservation.json').open('x') as f:
        json.dump({'job_id':os.environ.get('SLURM_JOB_ID'),'output':str(out),'plan_sha256':sha(PLAN)},f)
    save(out/'plan.json',plan);save(out/'source_hashes.json',plan['source_hashes'])
    save(out/'summary.json',{'status':'starting','calls':[]})
    counter=Counter();rows=[];failures=0;started=time.monotonic()
    try:
        client=Ollama(out/'calls');meta=client.metadata(plan['model']);save(out/'metadata.json',meta)
        models=[m for m in meta['tags']['models'] if m['name']==plan['model']]
        if len(models)!=1 or models[0]['digest']!=plan['model_digest']:
            raise ValueError('Model identity mismatch')
        if meta['version'] != plan['service_version_response']:
            raise ValueError('Service version response changed')
        wrapper=shutil.which('ollama')
        if wrapper != plan['installation_wrapper']: raise ValueError('Module wrapper path changed')
        installed={p:sha(p) for p in plan['installation_hashes']}
        save(out/'installation.json',{'wrapper':wrapper,'hashes':installed,'version_response':meta['version']})
        if installed != plan['installation_hashes']: raise ValueError('Installed binary/wrapper changed')
        items=[{**c,'kind':'calibration'} for c in plan['calibrations']]
        items += [{'input_id':e['input_id'],'prompt':render(read(ROOT/e['path'])),
                   'kind':'task','bundle':read(ROOT/e['path']),'num_predict':plan['num_predict'],
                   'expected_prompt_tokens':plan['capacity'][e['input_id']]} for e in plan['inputs']]
        for item in items:
            if len(rows)>=plan['max_calls']: raise RuntimeError('Call budget exhausted')
            if time.monotonic()-started>=1680: raise RuntimeError('Time budget exhausted')
            iid=item['input_id'];predict=item['num_predict'];prompt=item['prompt']
            count=counter.check(prompt,predict,plan['num_ctx'])
            if count!=item['expected_prompt_tokens']: raise ValueError('Count differs from plan')
            stem=out/'calls'/iid
            req=payload(plan,prompt,predict)
            save(str(stem)+'_request.json',req)
            row={'input_id':iid,'kind':item['kind'],'arm':plan['arm'],
                 'expected_prompt_tokens':count,'status':'started'}
            rows.append(row);save(out/'summary.json',{'status':'running','calls':rows})
            start=time.monotonic()
            try: response=client.api('generate',req)
            except Exception as exc:
                row['status']='transport_error';save(str(stem)+'_error.json',{'error':repr(exc)});raise
            save(str(stem)+'_response.json',response)
            row.update({'wall_seconds':time.monotonic()-start,
                        **{k:v for k,v in response.items() if k.endswith(('_count','_duration'))}})
            if response.get('prompt_eval_count')!=count:
                row['status']='input_count_mismatch'
                raise RuntimeError(f'Exact tokenizer mismatch {count}/{response.get("prompt_eval_count")}')
            if response.get('model')!=plan['model']: raise ValueError('Response model mismatch')
            if item['kind']=='calibration':
                # Calibration deliberately generates only 16 tokens; output cap is expected.
                if not response.get('done'): raise RuntimeError('Calibration incomplete')
                row['status']='calibrated'
            elif not response.get('done') or response.get('done_reason')=='length' or response.get('eval_count',0)>=predict:
                row['status']='output_cap_or_incomplete';failures+=1
            else:
                try:
                    obj=parse_response(response);save(str(stem)+'_parsed.json',obj)
                    row.update(validate_output(obj,item['bundle']));row['status']='parsed';failures=0
                except (ValueError,TypeError,KeyError) as exc:
                    row['status']='invalid_output';row['error']=repr(exc);failures+=1
            save(str(stem)+'_usage.json',row)
            save(out/'summary.json',{'status':'running','calls':rows})
            print(json.dumps(row),flush=True)
            if failures>=plan['max_consecutive_output_failures']:
                save(out/'summary.json',{'status':'stopped_output_failures','calls':rows});return
    except Exception as exc:
        save(out/'summary.json',{'status':'failed','error':repr(exc),'calls':rows});raise
    save(out/'summary.json',{'status':'complete','calls':rows})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['freeze','run'])
    p.add_argument('--output',type=Path);a=p.parse_args()
    if a.command=='freeze': freeze()
    elif not a.output: p.error('--output is required')
    else: run(a.output)
