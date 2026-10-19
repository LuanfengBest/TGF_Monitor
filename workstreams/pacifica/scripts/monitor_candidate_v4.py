"""One frozen Qwen3.5 deployment comparison; no reference labels at runtime."""
import argparse
import hashlib
import json
import os
import shutil
import urllib.error
from pathlib import Path
import time
import tokenizers
from tokenizers import Tokenizer
from monitor_selection_v1 import ROOT, SYSTEM, compact, read, sha, parse_response, validate_output
from ollama_client import Ollama, save

PLAN = ROOT / 'configs/monitor_candidate_v4.json'
TOKENIZER = ROOT / 'data/tokenizers/qwen3_5_9b/tokenizer.json'
MODEL = 'qwen3.5:9b'
MODEL_SHA = '56671c2ab9385f9cfcb404638e32cd62d88e3501d44822208363c010179a3c90'
ARM = 'qwen3_5_9b_general_think'
SOURCE_PATHS = [
    'scripts/monitor_candidate_v4.py', 'scripts/monitor_candidate_v4.sbatch',
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
            'think':True, 'keep_alive':'10m', 'truncate':False, 'shift':False,
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


def run(out):
    plan=read(PLAN); verify(plan)
    # Supervisor exclusively creates the output directory and installation record.
    assert (out/'installation.json').is_file()
    with (ROOT/'results/monitor_candidate_v4.reservation.json').open('x') as f:
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
        installed=read(out/'installation.json')
        if installed['asset'] != plan['runtime_asset']: raise ValueError('Runtime asset mismatch')
        if installed['model_manifest_sha256'] != plan['model_digest']: raise ValueError('Manifest changed')
        items=[{**c,'kind':'calibration'} for c in plan['calibrations']]
        items += [{'input_id':e['input_id'],'prompt':render(read(ROOT/e['path'])),
                   'kind':'task','bundle':read(ROOT/e['path']),'num_predict':plan['num_predict'],
                   'expected_prompt_tokens':plan['capacity'][e['input_id']]} for e in plan['inputs']]
        for item in items:
            if len(rows)>=plan['max_calls']: raise RuntimeError('Call budget exhausted')
            if time.monotonic()-started>=plan['runner_wall_seconds']: raise RuntimeError('Time budget exhausted')
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
                row['status']='transport_error'
                error={'error':repr(exc),'wall_seconds':time.monotonic()-start}
                if isinstance(exc,urllib.error.HTTPError):
                    error.update(status_code=exc.code,body=exc.read().decode('utf-8','replace'))
                save(str(stem)+'_error.json',error);save(str(stem)+'_usage.json',row);raise
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
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    run(p.parse_args().output)
