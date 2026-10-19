"""Bounded visible-prefix monitor diagnostic; runtime never reads reference labels."""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import urllib.request
from candidate_monitor_view_v1 import event_bundles, guard
from monitor_selection_v1 import ROOT, MODEL, MODEL_SHA, read, sha
from candidate_monitor_schema_v1 import SYSTEM, render, parse_response
from native_ollama_tokenizer import NativeCounter
from ollama_client import Ollama, save

PLAN=ROOT/'configs/candidate_controls_monitor_v1.json'
DATA=ROOT/'data/diagnostics/candidate_controls_monitor_v1'
CODE=['scripts/candidate_controls_monitor_v1.py','scripts/candidate_controls_monitor_v1.sbatch',
      'scripts/analyze_candidate_controls_monitor_v1.py',
      'scripts/candidate_monitor_view_v1.py','scripts/candidate_monitor_schema_v1.py','scripts/monitor_selection_v1.py',
      'scripts/observed_execution_v1.py','scripts/observed_airline_execution_v1.py',
      'scripts/native_ollama_tokenizer.py','scripts/ollama_client.py',
      'scripts/index_visible_evidence.py','tools/ollama_tokenizer/provenance.json']


def payload(item,plan):
    material=deepcopy(item['bundle']);material['execution_facts']=deepcopy(item['execution_facts'])
    return {'model':plan['model'],'prompt':render(material,True),'raw':True,'stream':False,
            'think':True,'keep_alive':'10m','options':{'num_ctx':plan['num_ctx'],
            'num_predict':plan['num_predict'],'seed':plan['seed'],**plan['sampling']}}


class BoundedClient(Ollama):
    def __init__(self,output,deadline):
        super().__init__(output);self.deadline=deadline;self.timeout=30
    def api(self,endpoint,payload=None):
        remaining=self.deadline-time.monotonic()
        if remaining<=0:raise TimeoutError('Monitor deadline reached')
        data=None if payload is None else json.dumps(payload).encode()
        req=urllib.request.Request(self.host+'/api/'+endpoint,data=data,headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=min(self.timeout,remaining)) as response:return json.load(response)
    def metadata(self,model):
        return {'version':self.api('version'),'tags':self.api('tags'),'show':self.api('show',{'model':model}),
                'job_id':os.environ.get('SLURM_JOB_ID'),'gpu':subprocess.check_output(['nvidia-smi',
                '--query-gpu=name,memory.total,driver_version','--format=csv'],text=True,timeout=15)}


def prepare(directories):
    if PLAN.exists() or DATA.exists():raise RuntimeError('Frozen controls diagnostic exists')
    old=read(ROOT/'configs/candidate_monitor_pilot_v1.json')
    p={k:deepcopy(old[k]) for k in ('model','model_digest','num_ctx','num_predict','seed','sampling','system_sha256','backend_installation_hashes')}
    p.update(protocol='candidate_controls_monitor_v1',split='development_scripted_controls',automatic_retries=0,
        max_calls=20,max_gpu_seconds=2400,runner_deadline_seconds=2260,max_http_seconds=240,
        max_consecutive_output_failures=2,source_hashes={name:sha(ROOT/name) for name in CODE},
        inputs=[],trajectories=[],planned_attempts=[],not_available=[],actor_generated_cases=0,
        limits='Scripted CPU simulator controls only; no actor reasoning/model-generated trajectories, no held-out or deployment claim. Same Qwen/schema/facts as natural pilot.')
    packet=ROOT/'data/annotation_review/candidate_controls_v2_20261013'
    manifest=read(packet/'manifest.json');counter=NativeCounter();pending=[]
    if len(manifest['cases'])!=16:raise ValueError('Must retain all16 controls')
    for i,c in enumerate(manifest['cases'],1):
        path=packet/c['input_file']
        if sha(path)!=c['sha256']:raise ValueError('Control view changed')
        view=read(path);aid=('bank_' if 'invoice IDs I-101' in view['user_request'] else 'airline_')+c['case_id']
        items=event_bundles(view);p['planned_attempts'].append(aid)
        p['trajectories'].append({'attempt_id':aid,'view_path':str(path.relative_to(ROOT)),'view_sha256':sha(path),
             'mutation_count':len(items),'status':'scripted_CPU_control'})
        for item in items:
            iid=f'c{i:03d}_{item["event_id"]}';dest=DATA/(iid+'.json')
            count=counter.check(payload(item,p)['prompt'],p['num_predict']);pending.append((dest,item))
            p['inputs'].append({'input_id':iid,'attempt_id':aid,'event_id':item['event_id'],'path':str(dest.relative_to(ROOT)),
                              'expected_prompt_tokens':count})
    if len(p['inputs'])!=20:raise ValueError('Expected all20 control mutations')
    DATA.mkdir(parents=True)
    for (dest,item),e in zip(pending,p['inputs']):save(dest,item);e['sha256']=sha(dest)
    save(PLAN,p);print(json.dumps({'scripted_cases':16,'events':20,'max_input':max(e['expected_prompt_tokens'] for e in p['inputs'])}))


def verify(p):
    if hashlib.sha256(SYSTEM.encode()).hexdigest()!=p['system_sha256']:raise ValueError('System changed')
    for path,h in p['source_hashes'].items():
        if sha(ROOT/path)!=h:raise ValueError('Source changed: '+path)
    for row in p['inputs']:
        if sha(ROOT/row['path'])!=row['sha256']:raise ValueError('Input changed')
    for row in p['trajectories']:
        if sha(ROOT/row['view_path'])!=row['view_sha256']:raise ValueError('Original view changed')


def run(out):
    p=read(PLAN);verify(p)
    with (ROOT/'results/candidate_controls_monitor_v1.reservation.json').open('x') as f:
        json.dump({'job_id':os.environ.get('SLURM_JOB_ID'),'output':str(out),'plan_sha256':sha(PLAN)},f)
    out.mkdir(parents=True,exist_ok=False);save(out/'plan.json',p)
    rows=[];started=time.monotonic();deadline=started+p['runner_deadline_seconds'];status='preflight'
    def checkpoint(**extra):save(out/'summary.json',{'status':status,'calls':rows,'elapsed_seconds':time.monotonic()-started,**extra})
    def timed_out(signum,frame):raise TimeoutError('Bounded monitor deadline')
    signal.signal(signal.SIGALRM,timed_out);signal.signal(signal.SIGTERM,lambda s,f: (_ for _ in ()).throw(SystemExit(143)))
    signal.setitimer(signal.ITIMER_REAL,p['runner_deadline_seconds']);checkpoint()
    try:
        client=BoundedClient(out/'calls',deadline)
        for name,expected in p['backend_installation_hashes'].items():
            if sha(name)!=expected:raise ValueError('Pinned backend executable changed')
        meta=client.metadata(p['model']);save(out/'metadata.json',meta)
        matches=[m for m in meta['tags']['models'] if m['name']==p['model']]
        if len(matches)!=1 or matches[0]['digest']!=p['model_digest']:raise ValueError('Model identity mismatch')
        if meta['version']['version']!='0.0.0':raise ValueError('Pinned module API version changed')
        counter=NativeCounter();failures=0;client.timeout=p['max_http_seconds']
        for e in p['inputs']:
            if deadline-time.monotonic()<p['max_http_seconds']+35:status='budget_stop';break
            item=read(ROOT/e['path']);request=payload(item,p);count=counter.check(request['prompt'],p['num_predict'])
            if count!=e['expected_prompt_tokens']:raise ValueError('Frozen tokenizer count changed')
            if len(rows)>=p['max_calls']:raise RuntimeError('Call budget exceeded')
            stem=out/'calls'/e['input_id'];save(str(stem)+'_request.json',request)
            row={'input_id':e['input_id'],'expected_prompt_tokens':count,'status':'started'};rows.append(row);status='running';checkpoint()
            call_started=time.monotonic()
            try:r=client.api('generate',request)
            except BaseException as exc:
                row.update(status='transport_or_interruption',error=repr(exc),final_usage_unknown=True)
                save(str(stem)+'_error.json',row);raise
            save(str(stem)+'_response.json',r)
            row.update(wall_seconds=time.monotonic()-call_started,**{k:v for k,v in r.items() if k.endswith(('_count','_duration'))})
            save(str(stem)+'_usage.json',row)
            if r.get('prompt_eval_count')!=count:row['status']='input_count_mismatch';raise ValueError('Backend prompt count differs')
            if not r.get('done') or r.get('done_reason')=='length' or r.get('eval_count',0)>=p['num_predict']:
                row['status']='output_cap_or_incomplete';failures+=1
            else:
                try:
                    obj=parse_response(r);save(str(stem)+'_parsed.json',obj)
                    checks=guard(obj,item);save(str(stem)+'_guard.json',checks)
                    row.update(status='parsed',**checks);failures=0
                except (ValueError,TypeError,KeyError) as exc:row.update(status='invalid_output',error=repr(exc));failures+=1
            checkpoint();print(json.dumps(row),flush=True)
            if failures>=p['max_consecutive_output_failures']:status='stopped_output_failures';break
        else:status='complete'
    except BaseException as exc:
        status='failed';save(out/'error.json',{'error':repr(exc),'status':status});checkpoint();raise
    finally:
        signal.setitimer(signal.ITIMER_REAL,0);checkpoint()
    checkpoint()

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('command',choices=['prepare','verify','run']);ap.add_argument('--actor-results',nargs='+',type=Path);ap.add_argument('--output',type=Path);args=ap.parse_args()
    if args.command=='prepare':prepare([])
    elif args.command=='verify':verify(read(PLAN));print('Frozen monitor sources and all inputs verified')
    elif args.output:run(args.output)
    else:ap.error('run requires output')
