"""One frozen six-case intervention: omit only initial_review from final TGF input."""
import argparse,hashlib,json,os,signal
from copy import deepcopy
from pathlib import Path
import prospective_four_arm_v1 as prior
from ollama_client import save,digest
ROOT=prior.ROOT
PLAN=ROOT/'configs/initial_review_ablation_v1.json'
PUBLIC=('user_request','policy','original_messages','ledger')
ALLOWED=set(PUBLIC)|{'initial_review','selected_event','followup'}
read,sha,create=prior.read,prior.sha,prior.create

def remove_initial_review(original):
 if set(original)!=ALLOWED:raise ValueError('Unexpected or missing final-input fields')
 if not isinstance(original['initial_review'],dict):raise ValueError('Initial review must exist')
 from tgf_evidence_eval_v1 import citation_audit
 citation_audit({k:original[k] for k in PUBLIC},{'evidence':[]})
 if original['followup'] is None:raise ValueError('This frozen intervention requires the original TGF followup')
 result=deepcopy(original);del result['initial_review']
 return result

def verify_item(item):
 original=read(ROOT/item['original_input_path']);derived=read(ROOT/item['input_path'])
 if digest(original)!=item['original_input_digest'] or digest(derived)!=item['input_digest']:raise ValueError('Input digest changed')
 if derived!=remove_initial_review(original):raise ValueError('Intervention changed more than initial_review')
 shared=read(ROOT/item['shared_path'])
 if {k:derived[k] for k in PUBLIC}!=shared:raise ValueError('Public evidence differs')
 return derived,shared

def verify(plan):
 if plan['max_calls']!=6 or plan['gpu_seconds']!=900 or plan['automatic_retries']!=0 or plan['training_runs']!=0:raise ValueError('Frozen budget changed')
 if plan['runner_deadline_seconds']!=800 or plan['per_call_seconds']!=150 or plan['judge_output_tokens']!=2048:raise ValueError('Deadline/output changed')
 old=read(ROOT/'configs/prospective_four_arm_v1.json')
 if [i['trace_id'] for i in plan['items']]!=[i['trace_id'] for i in old['items']]:raise ValueError('Must include all six in original order')
 if plan['models']['qwen3:32b']!=old['models']['qwen3:32b']:raise ValueError('Model changed')
 for n,h in plan['source_hashes'].items():
  if sha(ROOT/n)!=h:raise ValueError('Frozen source changed: '+n)
 counter=prior.Counter()
 for item in plan['items']:
  bundle,shared=verify_item(item)
  n=counter.check(prior.render_prompt(prior.JUDGE_SYSTEM,bundle),2048)
  if n!=item['expected_prompt_tokens']:raise ValueError('Frozen prompt token count differs')
 return plan

def run_case(client,item,out):
 bundle,shared=verify_item(item);out.mkdir(parents=True,exist_ok=False)
 save(out/'judge_input.json',bundle);save(out/'shared.json',shared)
 result=client.monitor(prior.JUDGE_SYSTEM,bundle,prior.judge_schema(shared),2048,item['trace_id']+'/judge_without_initial_review')
 save(out/'result.json',{'judgment':result,'input_digest':digest(bundle),'removed_field':'initial_review','new_actor_calls':0})
 return result

def run(out):
 plan=verify(read(PLAN));create(ROOT/'results/initial_review_ablation_v1.reservation.json',{'job_id':os.environ['SLURM_JOB_ID'],'plan_sha256':sha(PLAN),'output':str(out)})
 out.mkdir(parents=True,exist_ok=False);create(out/'plan.json',plan)
 signal.signal(signal.SIGALRM,lambda *a:(_ for _ in ()).throw(TimeoutError('Per-call deadline; no retry')))
 client=prior.Client(out/'calls',plan);attempts=[];status='failed';error=None
 try:
  model='qwen3:32b';meta=client.metadata(model);save(out/'monitor_metadata.json',meta)
  if meta['version']['version']!=plan['api_reported_version'] or {m['name']:m['digest'] for m in meta['tags']['models']}.get(model)!=plan['models'][model]['digest']:raise ValueError('Model/backend identity mismatch')
  if hashlib.sha256(meta['show']['template'].encode()).hexdigest()!=plan['models'][model]['template_sha256']:raise ValueError('Template identity mismatch')
  for item in plan['items']:
   row={'trace_id':item['trace_id'],'status':'started'};attempts.append(row);save(out/'attempts.json',attempts)
   try:run_case(client,item,out/item['trace_id']);row['status']='completed'
   except Exception as exc:row.update(status='failed',error=repr(exc));raise
   finally:save(out/'attempts.json',attempts)
  status='completed'
 except BaseException as exc:error=repr(exc);raise
 finally:
  signal.alarm(0);save(out/'summary.json',{'status':status,'error':error,'calls':client.count,'attempts':attempts,'planned_ids':[x['trace_id'] for x in plan['items']],'new_actor_calls':0,'training_runs':0,'costs_successful_calls_only':client.costs,'semantic_review':'pending'})
  try:client.unload('qwen3:32b')
  except Exception:pass
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('command',choices=['verify','run']);p.add_argument('--output',type=Path);a=p.parse_args()
 if a.command=='verify':verify(read(PLAN));print('Verified all six single-field interventions')
 elif a.output:run(a.output)
 else:p.error('output required')
