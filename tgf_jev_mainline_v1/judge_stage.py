"""Shared frozen upstream evidence, paired Qwen/Jev classification, no retries."""
import argparse,random,signal,time,traceback
from .common import *
from . import protocol as p
from jev_monitor_v1 import core
from jev_monitor_v1.run import http_jev
from jev_monitor_v1.qwen_native import worker
from prospective_monitoring.native_backend import ProcessStageBackend

def make_plan(refs):
 rows=[]
 for r in refs:
  for arm in p.ARMS:
   row={'request_id':r['case_id']+'.'+arm,'case_id':r['case_id'],'arm':arm,'phase':'formal','status':'ineligible_collection','state':None}
   if r['eligible']:
    state=read(OUT/'public'/f'{r["case_id"]}.json');supp=None;ready=True
    if arm=='C':
     file=OUT/'reviews'/r['case_id']/'result.json';d=read(file) if file.exists() else {}
     ready=d.get('status')=='valid';supp=d.get('review')
    elif arm in ('F','T'):
     file=OUT/'followups'/row['request_id']/'result.json';d=read(file) if file.exists() else {}
     ready=d.get('status')=='valid'
     if ready:
      if d['question']!=p.question(state,r['dimension'],arm):raise ValueError('Question differs from fixed policy')
      supp={k:d[k] for k in ('question','answer')}
    row['status']='ready' if ready else 'dependency_unavailable'
    if ready:row['state']=p.with_supplement(state,arm,supp);row['state_sha256']=digest(row['state'])
   rows.append(row)
 random.Random(2026111204).shuffle(rows)
 return rows

def qwen_request(state,c,review=False):
 return {'prompt':p.review_prompt(state) if review else p.qwen_prompt(state),'schema':p.review_schema(state) if review else core.schema(),'max_output_tokens':2048 if review else 1024,'seed':17}

def classify_one(model,row,backend,deadline,key=None):
 slot=OUT/'judgments'/model/row['request_id'];c=cfg()
 if (slot/'dispatch.json').exists():return read(slot/'result.json') if (slot/'result.json').exists() else {'status':'unknown_after_dispatch'}
 if row.get('status','ready')!='ready':
  v={'status':row['status'],'verdict':None};save(slot/'result.json',v);return v
 state=row['state'];assert not row.get('state_sha256') or digest(state)==row['state_sha256']
 req=p.jev_body(state) if model=='jev' else qwen_request(state,c)
 attempts=len(list((OUT/'judgments'/model).glob('*/dispatch.json')))
 if attempts>=776:raise RuntimeError('Judge call cap reached')
 if model=='jev' and (attempts+1)*32000*0.042/1e6>c['jev']['api_usd_cap']:raise RuntimeError('Jev reserve cap reached')
 remaining=min(180,deadline-time.monotonic()-3)
 if remaining<=0:raise TimeoutError('Judge stage wall cap reached')
 save(slot/'request.json',req);save(slot/'dispatch.json',{'attempt':1,'request_sha256':digest(req),'state_sha256':digest(state),'manifest_sha256':sha(BUNDLE/'manifest.json'),'created_unix':time.time(),'reserved_input_tokens':32000 if model=='jev' else None})
 result={'status':'invalid','verdict':None,'usage':None,'usage_complete':False};fatal=False
 try:
  sent=time.monotonic()
  if model=='jev':
   raw=http_jev(req,key,remaining);save(slot/'raw.json',raw)
   if raw['http_status']!=200:
    fatal=raw['http_status'] in (400,401,403,413,422)
    raise ValueError('Jev HTTP '+str(raw['http_status']))
   payload=raw['body'];result.update(core.parse_response('jev',payload));usage=payload.get('usage',{})
   if usage.get('input_tokens',32001)>32000:raise ValueError('Unexpected Jev context usage')
  else:
   raw=backend.generate(req,timeout_seconds=remaining);save(slot/'raw.json',raw)
   result.update(core.parse_response('qwen',raw));usage={'input_tokens':raw.get('prompt_tokens'),'output_tokens':raw.get('completion_tokens')}
  result.update(usage=usage,usage_complete=all(type(usage.get(k)) is int and usage[k]>=0 for k in ('input_tokens','output_tokens')),latency_seconds=time.monotonic()-sent)
  if not result['usage_complete'] or not result.get('choice_argmax_consistent',False):raise ValueError('Invalid usage or choice/argmax mismatch')
 except Exception as e:result.update(status='invalid',verdict=None,error=type(e).__name__+': '+str(e),fatal=fatal)
 save(slot/'result.json',result)
 return result

def qwen():
 c=cfg();seal=admission('qwen')
 if read(OUT/'actor_summary.json')['complete'] is not True:raise ValueError('Actor stage incomplete; inspect before continuation')
 verify_checkpoint(OUT/'collection','COLLECTION_FILES.json');verify_checkpoint(OUT/'followups','FOLLOWUP_FILES.json')
 refs=read(OUT/'reference_manifest_PRIVATE.json')['rows'];deadline=time.monotonic()+5400-(time.time()-float(os.environ['TGF_MAINLINE_START']))-15
 save(OUT/'qwen_allocation_claim.json',{'manifest_sha256':seal,'job_id':os.environ['SLURM_JOB_ID'],'attempt':1})
 b=ProcessStageBackend('monitor',c['qwen'],c['qwen']['snapshot'],permit_live=True,startup_timeout_seconds=min(900,deadline-time.monotonic()),_worker_target=worker)
 error=None;judged=0;reviews=0
 def expired(*_):raise TimeoutError('Qwen hard wall cap')
 signal.signal(signal.SIGALRM,expired);signal.signal(signal.SIGTERM,expired);signal.setitimer(signal.ITIMER_REAL,max(1,deadline-time.monotonic()))
 try:
  b.start();save(OUT/'qwen_ready.json',{'job_id':os.environ['SLURM_JOB_ID'],'model':c['models']['monitor'],'revision':c['revisions']['monitor']})
  smoke=[]
  for row in read(BUNDLE/'smoke.json'):
   result=classify_one('qwen',row,b,deadline);smoke.append(result)
  if any(x['status'] not in ('valid','abstention') for x in smoke):raise ValueError('Qwen smoke failed')
  save(OUT/'qwen_smoke.json',{'valid':len(smoke),'accuracy_not_a_gate':True})
  failures=0
  for r in refs:
   if not r['eligible']:continue
   state=read(OUT/'public'/f'{r["case_id"]}.json');req=qwen_request(state,c,review=True);slot=OUT/'reviews'/r['case_id']
   save(slot/'request.json',req);save(slot/'dispatch.json',{'attempt':1,'request_sha256':digest(req),'output_reserve':2048});reviews+=1
   if reviews>192:raise RuntimeError('Review call cap')
   result={'status':'invalid','review':None}
   try:
    raw=b.generate(req,timeout_seconds=min(180,deadline-time.monotonic()-3));save(slot/'raw.json',raw);result.update(status='valid',review=p.parse_review(raw,state))
   except Exception as e:result['error']=type(e).__name__+': '+str(e)
   save(slot/'result.json',result);print(canonical({'stage':'review','done':reviews,'case':r['case_id'],'status':result['status']}),flush=True)
   failures=failures+1 if result['status']!='valid' else 0
   if failures>=3:raise RuntimeError('Three consecutive review failures')
  plan=make_plan(refs);save(OUT/'judge_plan.json',plan)
  save(OUT/'judge_input_seal.json',{'plan_sha256':sha(OUT/'judge_plan.json'),'reference_sha256':sha(OUT/'reference_manifest_PRIVATE.json'),'sealed_before_formal_classification':True,'same_plan_for_both_judges':True})
  failures=0
  for row in plan:
   result=classify_one('qwen',row,b,deadline);judged+=row['status']=='ready'
   print(canonical({'stage':'qwen_judge','done':judged,'request':row['request_id'],'status':result['status']}),flush=True)
   failures=failures+1 if row['status']=='ready' and result['status']=='invalid' else 0
   if failures>=3 or b.closed:raise RuntimeError('Qwen failure stop')
 except BaseException as e:
  error=type(e).__name__+': '+str(e);save(OUT/'qwen_failure.json',{'error':error,'traceback':traceback.format_exc()});raise
 finally:
  signal.setitimer(signal.ITIMER_REAL,0);b.close();save(OUT/'qwen_summary.json',{'error':error,'reviews':reviews,'formal_judge_calls':judged,'complete':error is None,'job_id':os.environ['SLURM_JOB_ID']})
  checkpoint(OUT/'judgments'/'qwen','QWEN_FILES.json')

def jev(phase,keyfile):
 verify();c=cfg();keyfile=Path(keyfile).expanduser().resolve()
 if ROOT in keyfile.parents or keyfile.stat().st_mode&0o077:raise ValueError('Key must be private and outside repository')
 key=keyfile.read_text().strip()
 if not key:raise ValueError('Empty credential')
 if phase=='smoke':plan=read(BUNDLE/'smoke.json')
 else:
  if not read(OUT/'qwen_summary.json')['complete']:raise ValueError('Qwen not complete')
  verify_checkpoint(OUT/'judgments'/'qwen','QWEN_FILES.json')
  seal=read(OUT/'judge_input_seal.json')
  if sha(OUT/'judge_plan.json')!=seal['plan_sha256'] or sha(OUT/'reference_manifest_PRIVATE.json')!=seal['reference_sha256']:raise ValueError('Input/reference seal mismatch')
  if read(OUT/'jev_smoke.json')['valid']!=8:raise ValueError('Missing Jev smoke')
  plan=read(OUT/'judge_plan.json')
 deadline=time.monotonic()+3600;failures=0;done=0
 for row in plan:
  r=classify_one('jev',row,None,deadline,key);done+=1
  print(canonical({'stage':'jev_'+phase,'done':done,'planned':len(plan),'request':row['request_id'],'status':r['status']}),flush=True)
  failures=failures+1 if r['status'] in ('invalid','unknown_after_dispatch') else 0
  if failures>=3 or r.get('fatal'):raise RuntimeError('Jev failure stop; no retry')
 if phase=='smoke':
  results=[read(OUT/'judgments'/'jev'/row['request_id']/'result.json') for row in plan]
  if any(r['status'] not in ('valid','abstention') for r in results):raise ValueError('Jev interface smoke invalid')
  save(OUT/'jev_smoke.json',{'valid':8,'accuracy_not_a_gate':True,'manifest_sha256':verify(),'result_hashes':{row['request_id']:sha(OUT/'judgments'/'jev'/row['request_id']/'result.json') for row in plan}})
 else:
  save(OUT/'jev_summary.json',{'complete':True,'planned_formal_slots':len(plan),'processed_slots':done});checkpoint(OUT/'judgments'/'jev','JEV_FILES.json')
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('model',choices=['qwen','jev']);a.add_argument('--phase',choices=['smoke','formal']);a.add_argument('--key-file');args=a.parse_args()
 qwen() if args.model=='qwen' else jev(args.phase,args.key_file)
