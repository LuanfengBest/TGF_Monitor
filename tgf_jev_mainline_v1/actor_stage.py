"""One allocation: natural collection, sealed references, isolated F/T answers."""
import argparse,random,signal,time,traceback
from copy import deepcopy
from .common import *
from . import specs,protocol as p
from prospective_monitoring.collection import collect_case
from prospective_data_v2.fixtures import prepare_environment
from prospective_monitoring.native_backend import ProcessStageBackend
from prospective_monitoring.reference import evaluate_reference,render_public_contract

class Guard:
 origin_kind='natural_actor'
 def __init__(self,backend,deadline):self.backend=backend;self.deadline=deadline;self.calls=0;self.cid=None
 def generate_actor(self,request,timeout_seconds):
  if self.calls>=1920 or time.monotonic()>=self.deadline-5:raise TimeoutError('Collection envelope exhausted')
  save(OUT/'actor_dispatch'/f'{self.cid}.{request["turn_index"]:02d}.json',{'request_sha256':digest(request),'output_reserve':4096,'attempt':1})
  self.calls+=1
  return self.backend.generate_actor(request,timeout_seconds=min(timeout_seconds,self.deadline-time.monotonic()-3))

def audit(t,r):
 # Reference uses simulator execution, independently of any Judge or Actor claim.
 again=evaluate_reference(r['contract'],r['journal'])
 if again!=r['reference']:raise ValueError('Reference replay differs')
 if r['monitor_case'] is None:return False
 if digest(r['conversation'])!=r['conversation_sha256']:raise ValueError('Conversation hash changed')
 public=r['monitor_case']['public'];users={m['source_id']:m['content'] for m in public['messages'] if m['role']=='user'}
 for b in r['authorization_bindings']:
  if users.get(b['source_id'])!=t['authorization_messages'][b['revision_index']]['content']:raise ValueError('Public authorization binding differs')
  if b['effective_from_sequence']!=b['delivered_before_sequence']:raise ValueError('Authorization chronology differs')
 return (r['status']=='completed' and again['status']=='resolved' and again['sensitive_execution'] and again['label'] in (0,1))

def run():
 c=cfg();seal=admission('actor');start=time.monotonic();elapsed=time.time()-float(os.environ['TGF_MAINLINE_START']);deadline=start+7200-elapsed-15
 save(OUT/'actor_allocation_claim.json',{'job_id':os.environ['SLURM_JOB_ID'],'manifest_sha256':seal,'attempt':1,'startup_unix':time.time()})
 backend=ProcessStageBackend('actor',c,c['actor_snapshot'],permit_live=True,startup_timeout_seconds=min(900,deadline-start))
 guard=Guard(backend,deadline);rows=[];error=None;followups=0
 def expired(*args):raise TimeoutError('Actor allocation hard deadline')
 signal.signal(signal.SIGALRM,expired);signal.signal(signal.SIGTERM,expired);signal.setitimer(signal.ITIMER_REAL,max(1,deadline-time.monotonic()))
 try:
  backend.start();save(OUT/'actor_ready.json',{'job_id':os.environ['SLURM_JOB_ID'],'ready_after_seconds':time.monotonic()-start,'model':c['models']['actor'],'revision':c['revisions']['actor']})
  failures=0
  for t in tasks():
   if backend.closed or time.monotonic()>deadline-10:break
   cid=t['anonymous_id'];guard.cid=cid
   save(OUT/'collection_claims'/f'{cid}.json',{'task_sha256':digest(t),'attempt':1})
   r=collect_case(t,guard,OUT/'collection'/cid,specs.CASE_LIMITS,environment_factory=prepare_environment)
   eligible=audit(t,r) if r['journal'] is not None else False
   state=None;dimension=None
   if eligible:
    try:state,dimension=p.public_state(r['monitor_case']['public'])
    except ValueError:eligible=False
   row={'case_id':cid,'task_case_id':t['case_id'],'block':t['instance_id'],'environment':t['environment'],'family':t['family_id'],'condition':t['condition'],'collection_status':r['status'],'eligible':eligible,'label':r['reference']['label'],'reference_status':r['reference']['status'],'sensitive_execution':r['reference']['sensitive_execution'],'public_sha256':digest(state) if state else None,'dimension':dimension,'result_sha256':sha(OUT/'collection'/cid/'result_private.json'),'label_provenance':'simulator_execution_and_public_authorization_binding_check','human_gold':False}
   rows.append(row);save(OUT/'references_PRIVATE'/f'{cid}.json',row)
   if eligible:save(OUT/'public'/f'{cid}.json',state)
   print(canonical({'stage':'collection','done':len(rows),'planned':192,'case':cid,'status':r['status'],'eligible':eligible}),flush=True)
   failures=failures+1 if r['status']!='completed' else 0
   if failures>=3:raise RuntimeError('Three consecutive collection failures')
  known={r['case_id'] for r in rows}
  rows.extend({'case_id':t['anonymous_id'],'block':t['instance_id'],'environment':t['environment'],'family':t['family_id'],'condition':t['condition'],'collection_status':'not_started','eligible':False,'label':None} for t in tasks() if t['anonymous_id'] not in known)
  save(OUT/'reference_manifest_PRIVATE.json',{'planned':192,'rows':rows,'sealed_before_followups_and_judgments':True,'method':'program reference plus public-binding audit; no independent human labels'})
  checkpoint(OUT/'collection','COLLECTION_FILES.json')
  eligible=[r for r in rows if r['eligible']];order=[(r,a) for r in eligible for a in ('F','T')];random.Random(2026111203).shuffle(order)
  failures=0
  for row,arm in order:
   if backend.closed or time.monotonic()>deadline-10:break
   cid=row['case_id'];state=read(OUT/'public'/f'{cid}.json');case=read(OUT/'collection'/cid/'monitor_case.json')
   req=p.followup(case,state,row['dimension'],arm,c);slot=OUT/'followups'/f'{cid}.{arm}'
   save(slot/'request.json',req);save(slot/'dispatch.json',{'request_sha256':digest(req),'attempt':1,'output_reserve':4096})
   followups+=1
   if followups>384:raise RuntimeError('Followup count exceeded')
   result={'status':'invalid','question':req['content']['question'],'answer':None}
   try:
    raw=backend.generate(req,timeout_seconds=min(180,deadline-time.monotonic()-3));save(slot/'raw.json',raw)
    if raw.get('finish_reason')!='stop' or raw.get('channel')!='final' or raw.get('tool_calls')!=[] or not raw.get('text','').strip():raise ValueError('Invalid tool-disabled final answer')
    result.update(status='valid',answer=raw['text'])
   except Exception as e:result['error']=type(e).__name__+': '+str(e)
   save(slot/'result.json',result)
   print(canonical({'stage':'followup','done':followups,'planned':len(order),'case':cid,'arm':arm,'status':result['status']}),flush=True)
   failures=failures+1 if result['status']!='valid' else 0
   if failures>=3:raise RuntimeError('Three consecutive followup failures')
 except BaseException as e:
  error=type(e).__name__+': '+str(e);save(OUT/'actor_failure.json',{'error':error,'traceback':traceback.format_exc()});raise
 finally:
  signal.setitimer(signal.ITIMER_REAL,0);backend.close()
  save(OUT/'actor_summary.json',{'error':error,'collection_calls':guard.calls,'followup_calls':followups,'elapsed_seconds':time.monotonic()-start,'job_id':os.environ['SLURM_JOB_ID'],'complete':error is None and len([r for r in rows if r['collection_status']!='not_started'])==192 and followups==2*sum(r['eligible'] for r in rows)})
  checkpoint(OUT/'followups','FOLLOWUP_FILES.json')
if __name__=='__main__':run()
