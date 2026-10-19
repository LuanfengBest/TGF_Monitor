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

PLAN=ROOT/'configs/candidate_monitor_pilot_v1.json'
DATA=ROOT/'data/diagnostics/candidate_monitor_pilot_v1'
CODE=['scripts/candidate_monitor_pilot_v1.py','scripts/candidate_monitor_pilot_v1.sbatch',
      'scripts/analyze_candidate_monitor_pilot_v1.py',
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
    if PLAN.exists() or DATA.exists():raise RuntimeError('Frozen diagnostic exists')
    p={'protocol':'candidate_monitor_pilot_v1','split':'development','model':MODEL,'model_digest':MODEL_SHA,
       'num_ctx':32768,'num_predict':6144,'seed':42,'sampling':{'temperature':0.6,'top_p':0.95,'top_k':20,'min_p':0},
       'automatic_retries':0,'max_calls':64,'max_gpu_seconds':3600,'runner_deadline_seconds':3460,
       'max_consecutive_output_failures':2,'max_http_seconds':240,
       'system_sha256':hashlib.sha256(SYSTEM.encode()).hexdigest(),
       'source_hashes':{s:sha(ROOT/s) for s in CODE},'inputs':[],'trajectories':[],
       'backend_installation_hashes':read(ROOT/'configs/candidate_actor_pilot_v1.json')['backend_installation_hashes'],
       'limits':'AI development diagnostic only; automatic mutation enumeration with complete causal prefix, original reasoning included. Not held-out, human gold, full-operation coverage or deployment proof.'}
    # Stage order and all listed trajectories are fixed before monitor outcomes exist.
    actor_plan=read(ROOT/'configs/candidate_actor_pilot_v1.json')
    stages=['smoke','batch1','batch2','batch3']
    if [read(base/'stage.json')['stage'] for base in directories]!=stages:
        raise ValueError('All four actor stages must be supplied in frozen order')
    p['actor_plan_sha256']=sha(ROOT/'configs/candidate_actor_pilot_v1.json')
    p['planned_attempts']=[aid for stage in stages for aid in actor_plan['stages'][stage]['attempt_ids']]
    p['not_available']=[]
    counter=NativeCounter();pending=[];seen=set()
    for base in directories:
        stage=read(base/'stage.json')['stage'];summary=read(base/'summary.json')
        wanted=actor_plan['stages'][stage]['attempt_ids'];actual=[r['attempt_id'] for r in summary['attempts']]
        if actual!=wanted[:len(actual)] or summary['status'] in ('running','preflight'):
            raise ValueError('Actor stage incomplete or unexpected order')
        p['not_available'].extend({'attempt_id':aid,'reason':'not_started_in_bounded_actor_stage','stage':stage} for aid in wanted[len(actual):])
        for row in summary['attempts']:
            aid=row['attempt_id']
            if aid in seen:raise ValueError('Duplicate trajectory')
            seen.add(aid);path=base/aid/'rollout/monitor_view.json';items=event_bundles(read(path))
            trajectory={'attempt_id':aid,'view_path':str(path.relative_to(ROOT)),'view_sha256':sha(path),
                        'mutation_count':len(items),'status':read(base/aid/'rollout/summary.json')['status']}
            p['trajectories'].append(trajectory)
            for item in items:
                iid=f'v{len(p["trajectories"]):03d}_{item["event_id"]}'
                dest=DATA/(iid+'.json');count=counter.check(payload(item,p)['prompt'],p['num_predict'])
                pending.append((dest,item));p['inputs'].append({'input_id':iid,'attempt_id':aid,'event_id':item['event_id'],
                    'path':str(dest.relative_to(ROOT)),'expected_prompt_tokens':count})
    if not 0<len(p['inputs'])<=p['max_calls']:raise ValueError('Input budget exceeded or empty')
    DATA.mkdir(parents=True)
    for (path,item),row in zip(pending,p['inputs']):save(path,item);row['sha256']=sha(path)
    save(PLAN,p)
    print(json.dumps({'trajectories':len(p['trajectories']),'events':len(p['inputs']),
                      'max_input':max(x['expected_prompt_tokens'] for x in p['inputs'])}))


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
    with (ROOT/'results/candidate_monitor_pilot_v1.reservation.json').open('x') as f:
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
    if args.command=='prepare':prepare([p.resolve() for p in args.actor_results])
    elif args.command=='verify':verify(read(PLAN));print('Frozen monitor sources and all inputs verified')
    elif args.output:run(args.output)
    else:ap.error('run requires output')
