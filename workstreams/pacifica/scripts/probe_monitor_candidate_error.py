"""Last reserved calibration, solely to capture backend diagnostics; no task loop."""
import json
import os
from pathlib import Path
import time
import urllib.error
from monitor_candidate_v2 import ROOT, PLAN, read, sha, verify, Counter, payload
from ollama_client import Ollama, save

plan=read(PLAN);verify(plan)
prior=read(ROOT/'results/monitor_candidate_v2_29437497/summary.json')
assert prior['status']=='failed' and len(prior['calls'])==1
assert prior['calls'][0]['input_id']=='calibration_tiny' and prior['calls'][0]['status']=='transport_error'
out=ROOT/'results'/('monitor_candidate_error_probe_'+os.environ['SLURM_JOB_ID'])
out.mkdir(parents=True,exist_ok=False)
with (ROOT/'results/monitor_candidate_error_probe.reservation.json').open('x') as f:
    json.dump({'output':str(out),'purpose':'capture error body on the remaining predeclared mixed calibration; no task calls'},f)
save(out/'plan.json',plan);save(out/'probe_source_hashes.json',{p:sha(ROOT/p) for p in ['scripts/probe_monitor_candidate_error.py','scripts/probe_monitor_candidate_error.sbatch']})
client=Ollama(out);meta=client.metadata(plan['model']);save(out/'metadata.json',meta)
assert any(m['name']==plan['model'] and m['digest']==plan['model_digest'] for m in meta['tags']['models'])
assert {p:sha(p) for p in plan['installation_hashes']}==plan['installation_hashes']
calibration=plan['calibrations'][1];counter=Counter();n=counter.check(calibration['prompt'],calibration['num_predict'])
assert n==calibration['expected_prompt_tokens']
req=payload(plan,calibration['prompt'],calibration['num_predict']);save(out/'request.json',req)
save(out/'summary.json',{'status':'started','requests':1,'purpose':'backend_diagnostics_only'})
start=time.monotonic()
try:
    r=client.api('generate',req);save(out/'response.json',r)
    count_matches=r.get('prompt_eval_count')==n
    save(out/'summary.json',{'status':'response_received','requests':1,'count_matches':count_matches,'expected_prompt_tokens':n,'wall_seconds':time.monotonic()-start,'task_calls':0})
    print(json.dumps({'count_matches':count_matches,'response_received':True}),flush=True)
except urllib.error.HTTPError as e:
    detail={'status':'http_error','requests':1,'http_status':e.code,'body':e.read().decode('utf-8',errors='replace'),'wall_seconds':time.monotonic()-start,'task_calls':0}
    save(out/'summary.json',detail);print(json.dumps(detail),flush=True);raise
except Exception as e:
    save(out/'summary.json',{'status':'transport_error','requests':1,'error':repr(e),'task_calls':0});raise
