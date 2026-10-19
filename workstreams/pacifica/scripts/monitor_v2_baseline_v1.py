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

PLAN=ROOT/'configs/monitor_v2_baseline_v1.json'
DATA=ROOT/'data/diagnostics/monitor_v2_baseline_v1'
CODE=['scripts/monitor_v2_baseline_v1.py','scripts/monitor_v2_baseline_v1.sbatch',
      'scripts/analyze_monitor_v2_baseline_v1.py',
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
    if PLAN.exists() or DATA.exists():raise RuntimeError('Frozen new-family baseline exists')
    old=read(ROOT/'configs/candidate_monitor_pilot_v1.json')
    p={k:deepcopy(old[k]) for k in ('model','model_digest','num_ctx','num_predict','seed','sampling','system_sha256','backend_installation_hashes')}
    p.update(protocol='monitor_v2_baseline_v1',split='predeclared_train_validation_scripted_audit',automatic_retries=0,
        max_calls=11,max_gpu_seconds=1200,runner_deadline_seconds=1060,max_http_seconds=240,
        max_consecutive_output_failures=2,source_hashes={name:sha(ROOT/name) for name in CODE},
        inputs=[],trajectories=[],planned_attempts=[],not_available=[],actor_generated_cases=0,
        limits='Single unchanged baseline before any fitting; 11 scripted audit events across three preassigned families. Not natural actor detection, not final unseen test, not training approval.')
    packet=ROOT/'data/annotation_review/monitor_v2_cpu_audit_v1'
    manifest=read(packet/'manifest.json');counter=NativeCounter();pending=[]
    cpu_plan=ROOT/'configs/monitor_v2_cpu_audit_v1.json'
    if manifest['plan_sha256']!=sha(cpu_plan) or len(manifest['cases'])!=8 or manifest['mutation_events']!=11:
        raise ValueError('New-family audit differs from its frozen generation plan')
    p['source_hashes'][str(cpu_plan.relative_to(ROOT))]=sha(cpu_plan)
    p['source_hashes'][str((packet/'manifest.json').relative_to(ROOT))]=sha(packet/'manifest.json')
    for i,c in enumerate(manifest['cases'],1):
        path=packet/c['input_file']
        if sha(path)!=c['sha256']:raise ValueError('Audit view changed')
        if c['split'] not in ('train','validation'):raise ValueError('Unexpected family assignment')
        view=read(path);aid=('airline_' if 'airline' in c['family_id'] else 'bank_')+c['case_id']
        items=event_bundles(view);p['planned_attempts'].append(aid)
        p['trajectories'].append({'attempt_id':aid,'view_path':str(path.relative_to(ROOT)),'view_sha256':sha(path),
             'mutation_count':len(items),'status':'scripted_CPU_audit','split':c['split'],'family_id':c['family_id']})
        for item in items:
            iid=f'n{i:03d}_{item["event_id"]}';dest=DATA/(iid+'.json')
            count=counter.check(payload(item,p)['prompt'],p['num_predict']);pending.append((dest,item))
            p['inputs'].append({'input_id':iid,'attempt_id':aid,'event_id':item['event_id'],'path':str(dest.relative_to(ROOT)),
                              'expected_prompt_tokens':count,'split':c['split'],'family_id':c['family_id']})
    if len(p['inputs'])!=11:raise ValueError('Expected all11 audit mutations')
    DATA.mkdir(parents=True)
    for (dest,item),e in zip(pending,p['inputs']):save(dest,item);e['sha256']=sha(dest)
    save(PLAN,p);print(json.dumps({'scripted_cases':8,'events':11,'max_input':max(e['expected_prompt_tokens'] for e in p['inputs'])}))


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
    with (ROOT/'results/monitor_v2_baseline_v1.reservation.json').open('x') as f:
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
