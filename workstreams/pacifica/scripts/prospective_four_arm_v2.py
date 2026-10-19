"""Four-way public event interface v2 draft; no run without a new actual-input plan."""
import argparse,hashlib,json,math,os,signal,time,urllib.request
from pathlib import Path
from copy import deepcopy
import jsonschema
from paired_protocol_v3 import (ROOT,Counter,REVIEW_SYSTEM,QUESTION_SYSTEM,JUDGE_SYSTEM,FIXED_QUESTION,
    review_schema,judge_schema,obj_schema,text_schema,select_event,actor_branch,reply_projection,render_prompt)
from tgf_public_trace_v1 import shared_bundle
from analyze_prospective_actor_v5 import check_context
from b3_review_v2 import EXTRA_SYSTEM,extra_schema,judge_bundle
from run_paired_v3 import Client as PriorClient
from ollama_client import save,digest
from public_event_contract_v2 import prepare,select

PLAN=ROOT/'configs/prospective_four_arm_v2.json'
METHODS=('ledger_only','fixed_b2','tgf','b3')
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def create(p,v):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(v,f,ensure_ascii=False,indent=2);f.write('\n')
def verify_input(item):
 view=read(ROOT/item['view_path']);original=read(ROOT/item['actor_context_path'])
 if digest(view)!=item['view_digest'] or digest(original)!=item['actor_context_digest']:raise ValueError('Frozen input changed')
 check_context(original,view)
 shared,facts=prepare(shared_bundle(view))
 return original,shared,facts
def assert_same_public_inputs(common,bundles):
 for method,b in bundles.items():
  core={k:v for k,v in b.items() if k not in ('followup','extra_monitor_review')}
  if core!=common:raise ValueError('Baseline public input inequality: '+method)
 return True

class Client(PriorClient):
 def __init__(self,out,plan):
  super().__init__(out,plan,plan['max_calls']);self.deadline=time.monotonic()+plan['runner_deadline_seconds'];self.costs={}
 def api(self,endpoint,payload=None):
  remaining=self.deadline-time.monotonic()
  if remaining<=0:raise TimeoutError('Stage deadline')
  req=urllib.request.Request(self.host+'/api/'+endpoint,data=None if payload is None else json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
  with urllib.request.urlopen(req,timeout=min(remaining,self.plan['per_call_seconds'])) as r:return json.load(r)
 def request(self,endpoint,payload,name,expected_tokens=None):
  if time.monotonic()>=self.deadline:raise TimeoutError('Stage deadline before request')
  response=super().request(endpoint,payload,name,expected_tokens)
  self.costs[name]=response['prompt_eval_count']+response['eval_count']
  return response

def run_trace(client,item,out,plan):
 original,shared,facts=verify_input(item);out.mkdir(parents=True,exist_ok=False);save(out/'shared.json',shared)
 save(out/'public_observations.json',facts)
 review_input={**shared,'public_execution_observations':facts}
 prefix=item['trace_id']+'/'
 review=client.monitor(REVIEW_SYSTEM,review_input,review_schema(shared),4096,prefix+'initial_review');save(out/'initial_review.json',review)
 selected=select(shared,review,facts);save(out/'selected_event.json',selected)
 question_input={**review_input,'initial_review':review,'selected_event':selected}
 common={**review_input,'selected_event':selected}
 if plan['final_judge_initial_review']=='retain':common['initial_review']=review
 elif plan['final_judge_initial_review']!='omit':raise ValueError('Final review policy must be frozen')
 save(out/'question_input.json',question_input);save(out/'common_judge_evidence.json',common)
 questions={};replies={};bundles={};results={}
 if selected is not None:
  question=client.monitor(QUESTION_SYSTEM,question_input,obj_schema({'question':text_schema(600)}),256,prefix+'targeted_question')['question']
  if not question.strip():raise ValueError('Empty TGF question')
  questions={'fixed_b2':FIXED_QUESTION,'tgf':question};save(out/'questions.json',questions)
  client.unload('qwen3:32b')
  for method in ('fixed_b2','tgf'):
   branch=actor_branch(original,selected,questions[method])
   if branch[:-1]!=original:raise ValueError('Actor branch context altered')
   save(out/(method+'_branch_identity.json'),{'base_context_digest':digest(branch[:-1]),'tools_provided':False,'answer_cap':1024})
   response=client.actor(branch,prefix+method+'_answer');replies[method]=reply_projection(response);save(out/(method+'_reply.json'),replies[method])
  client.unload('gpt-oss:20b')
 for method in ('ledger_only','fixed_b2','tgf'):
  followup=None if method=='ledger_only' or selected is None else {'question':questions[method],'reply':replies[method]}
  bundle={**common,'followup':followup};bundles[method]=bundle;save(out/(method+'_judge_input.json'),bundle)
  judged=client.monitor(JUDGE_SYSTEM,bundle,judge_schema(shared),2048,prefix+method+'_judge')
  results[method]={'judgment':judged,'shared_evidence_digest':digest(common),'question_count':int(followup is not None)};save(out/(method+'_result.json'),results[method])
 # The control receives the same common evidence and an extra original-trace review.
 initial_cost=client.costs[prefix+'initial_review']
 tgf_cost=initial_cost+client.costs.get(prefix+'targeted_question',0)+client.costs[prefix+'tgf_judge']
 maximum=plan['per_arm_monitor_token_ceiling']
 if maximum!=98304:raise ValueError('Available token ceiling differs from protocol')
 if tgf_cost>maximum:raise ValueError('TGF available monitor budget exceeded')
 ep=render_prompt(EXTRA_SYSTEM,question_input);en=client.counter.check(ep,256)
 empty=judge_bundle(common,{'findings':[]});jn=client.counter.check(render_prompt(JUDGE_SYSTEM,empty),2048)
 if initial_cost+en+256+jn+2048>maximum:raise ValueError('B3 available budget insufficient')
 save(out/'b3_extra_input.json',question_input)
 extra=client.monitor(EXTRA_SYSTEM,question_input,extra_schema(question_input),256,prefix+'b3_extra_review');save(out/'b3_extra_review.json',extra)
 bundle=judge_bundle(common,extra);bundles['b3']=bundle;save(out/'b3_judge_input.json',bundle)
 jn=client.counter.check(render_prompt(JUDGE_SYSTEM,bundle),2048)
 if initial_cost+client.costs[prefix+'b3_extra_review']+jn+2048>maximum:raise ValueError('B3 final token ceiling exceeded')
 judged=client.monitor(JUDGE_SYSTEM,bundle,judge_schema(shared),2048,prefix+'b3_judge')
 results['b3']={'judgment':judged,'shared_evidence_digest':digest(common),'question_count':0};save(out/'b3_result.json',results['b3'])
 assert_same_public_inputs(common,bundles)
 b3_cost=initial_cost+client.costs[prefix+'b3_extra_review']+client.costs[prefix+'b3_judge']
 if b3_cost>maximum:raise ValueError('Actual B3 budget exceeded')
 gate={'public_inputs_equal':True,'branches_independent':True,'tools_disabled':True,'monitor_counts_exact':True,'within_equal_available_monitor_budget':True}
 save(out/'integrity_gate.json',gate)
 save(out/'summary.json',{'status':'completed','scores':{k:v['judgment']['unauthorized_action_score'] for k,v in results.items()},'tgf_monitor_tokens':tgf_cost,'b3_monitor_tokens':b3_cost,'b3_to_tgf_actual_token_ratio':b3_cost/tgf_cost,'per_arm_available_monitor_calls':3,'per_arm_available_monitor_tokens':maximum,'tgf_monitor_calls':2+int(selected is not None),'b3_monitor_calls':3,'not_same_flops':True,'not_same_actual_tokens':True,'final_judge_initial_review':plan['final_judge_initial_review'],'semantic_review':'pending'})
 return gate

def verify(plan):
 for n,h in plan['source_hashes'].items():
  if sha(ROOT/n)!=h:raise ValueError('Frozen source changed: '+n)
 if not 1<=len(plan['items'])<=6 or plan['max_calls']>54 or plan['gpu_seconds']>2700:raise ValueError('Bound exceeded')
 if plan['automatic_retries']!=0 or plan['training_runs']!=0:raise ValueError('Retries/training not allowed')
 if plan['final_judge_initial_review'] not in ('retain','omit') or plan['per_arm_monitor_token_ceiling']!=98304:raise ValueError('Missing frozen information/budget policy')
 policy=read(ROOT/plan['final_judge_policy_path'])
 if policy['final_judge_initial_review']!=plan['final_judge_initial_review']:raise ValueError('Final judge policy differs from prior decision')
 gate=read(ROOT/plan['qualification_path'])
 if not gate['stage_qualified'] or [i['trace_id'] for i in plan['items']]!=gate['technical_eligible_ids']:raise ValueError('Qualification or complete eligible batch mismatch')
 if plan['max_calls']!=gate['max_following_calls'] or plan['max_calls']!=9*len(plan['items']):raise ValueError('Actual batch call budget mismatch')
 for item in plan['items']:
  original,shared,facts=verify_input(item);Counter().check(render_prompt(REVIEW_SYSTEM,{**shared,'public_execution_observations':facts}),4096)
  for event in shared['ledger']:
   if event['candidate']:
    for question in (FIXED_QUESTION,'\U0001f600'*600):
     branch=actor_branch(original,event,question)
     size=len(json.dumps({'messages':branch,'tools':[]},ensure_ascii=False).encode())
     if size+4096+128*len(branch)+1024>plan['actor_context']:raise ValueError('Actor branch capacity; no new calls or truncation')
 return plan

def run(out):
 plan=verify(read(PLAN));create(ROOT/'results/prospective_four_arm_v2.reservation.json',{'job_id':os.environ['SLURM_JOB_ID'],'plan_sha256':sha(PLAN),'output':str(out)})
 out.mkdir(parents=True,exist_ok=False);create(out/'plan.json',plan)
 signal.signal(signal.SIGALRM,lambda *a:(_ for _ in ()).throw(TimeoutError('Per-call deadline')))
 client=Client(out/'calls',plan);attempts=[];status='failed';error=None
 try:
  for model in ('qwen3:32b','gpt-oss:20b'):
   meta=client.metadata(model);save(out/(model.replace(':','_')+'_metadata.json'),meta)
   if meta['version']['version']!=plan['api_reported_version'] or {m['name']:m['digest'] for m in meta['tags']['models']}.get(model)!=plan['models'][model]['digest']:raise ValueError('Model/backend identity mismatch')
   if hashlib.sha256(meta['show']['template'].encode()).hexdigest()!=plan['models'][model]['template_sha256']:raise ValueError('Template identity mismatch')
  failures=0
  for index,item in enumerate(plan['items']):
   row={'trace_id':item['trace_id'],'status':'started'};attempts.append(row);save(out/'attempts.json',attempts)
   try:
    gate=run_trace(client,item,out/item['trace_id'],plan)
    if not all(gate.values()):raise ValueError('First/each trace integrity failed')
    row['status']='completed';failures=0
   except Exception as exc:
    row.update(status='failed',error=repr(exc));failures+=1
    if index==0 or failures>=2:raise
   finally:save(out/'attempts.json',attempts)
  status='completed_with_failures' if any(a['status']!='completed' for a in attempts) else 'completed'
 except BaseException as exc:error=repr(exc);raise
 finally:
  signal.alarm(0);save(out/'summary.json',{'status':status,'error':error,'calls':client.count,'attempts':attempts,'planned_ids':[x['trace_id'] for x in plan['items']],'training_runs':0,'semantic_results':'pending','costs_successful_calls_only':client.costs})
  for model in ('qwen3:32b','gpt-oss:20b'):
   try:client.unload(model)
   except Exception:pass
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('command',choices=['verify','run']);p.add_argument('--output',type=Path);a=p.parse_args()
 if a.command=='verify':verify(read(PLAN));print('Verified')
 elif a.output:run(a.output)
 else:p.error('output required')
