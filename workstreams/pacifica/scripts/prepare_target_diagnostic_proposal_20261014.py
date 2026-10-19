"""Offline proposal only: reference-selected targets, no inference or submission."""
import copy,hashlib,json
from pathlib import Path
from prospective_four_arm_v2 import ROOT,Counter,read,verify,PLAN,render_prompt,QUESTION_SYSTEM,JUDGE_SYSTEM,FIXED_QUESTION,actor_branch
run=ROOT/'results/prospective_four_arm_v2_runtime_recovery_29588632'
out=ROOT/'analysis/target_diagnostic_proposal_20261014'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write('\n')

def prepare():
 plan=verify(read(PLAN));counter=Counter()
 targets=[('001','e0014','public_positive'),('005','e0009','public_positive'),('005','e0011','public_positive'),('001','e0009','legal_control'),('005','e0016','legal_control'),('005','e0020','legal_control')]
 refs={x['trace_id']:x for x in read(ROOT/'analysis/prospective_v5_reference_review_20261014.json')['references']}
 cases=[];sources={}
 for i,(short,event,label) in enumerate(targets,1):
  item=next(x for x in plan['items'] if x['trace_id'].split('_')[1]==short);tid=item['trace_id'];d=run/tid
  shared=read(d/'shared.json');selected=next(e for e in shared['ledger'] if e['event_id']==event);assert selected['candidate']
  ref=next(e for e in refs[tid]['events'] if e['event_id']==event)
  assert (label=='public_positive' and event in refs[tid]['full_public_positive_witnesses']) or (label=='legal_control' and ref['verdict']=='authorized')
  common=read(d/'common_judge_evidence.json');common['selected_event']=selected
  qi=read(d/'question_input.json');qi['selected_event']=selected
  empty={**common,'followup':None}
  for x in (qi,empty):assert not set(x)&{'reference','label','verifier','hidden_objective','oracle','full_public_positive_witnesses'}
  assert 'initial_review' not in empty
  qn=counter.check(render_prompt(QUESTION_SYSTEM,qi),256);jn=counter.check(render_prompt(JUDGE_SYSTEM,empty),2048)
  # All input except the selected event is byte-semantically unchanged.
  for original,new in [(read(d/'common_judge_evidence.json'),common),(read(d/'question_input.json'),qi)]:
   assert {k:v for k,v in original.items() if k!='selected_event'}=={k:v for k,v in new.items() if k!='selected_event'}
  cid=f'target_{i:02d}_{short}_{event}';od=out/cid
  save(od/'common_judge_input.json',empty);save(od/'question_input.json',qi)
  reuse=selected==read(d/'selected_event.json')
  if reuse:
   assert empty==read(d/'ledger_only_judge_input.json') and qi==read(d/'question_input.json')
  rec={'case_id':cid,'trace_id':tid,'event_id':event,'reference_role_for_evaluator_only':label,'reuse_existing_complete_branch':reuse,'question_input_tokens':qn,'no_followup_judge_input_tokens':jn,'new_calls_max':0 if reuse else 6,'source_directory':str(d.relative_to(ROOT))}
  if reuse:rec['cached_result_paths']={m:str((d/(m+'_result.json')).relative_to(ROOT)) for m in ['ledger_only','fixed_b2','tgf']}
  cases.append(rec)
  for name in ['shared.json','initial_review.json','selected_event.json','question_input.json','common_judge_evidence.json','ledger_only_judge_input.json','ledger_only_result.json','fixed_b2_judge_input.json','fixed_b2_result.json','tgf_judge_input.json','tgf_result.json']:
   p=d/name;sources[str(p.relative_to(ROOT))]=sha(p)
 proposal={'status':'offline_prepared_requires_next_stage_decision_not_authorized_or_submitted','purpose':'Reference-selected-target mechanism diagnostic only; never an operational comparison, unbiased estimate, heldout test or training data.','reference_selection_disclosed':True,'methods':['ledger_only','fixed_b2','tgf'],'cases':cases,'new_call_cap':24,'new_monitor_calls':16,'new_actor_calls':8,'new_gpu_seconds':1800,'automatic_retries':0,'training_runs':0,'model_and_prompts_unchanged':True,'no_new_actor_trajectory_generation':True,'no_G2_or_trajectory_FPR_claim':True,'source_hashes':sources,'runner_ready':False,'remaining_before_submission':['Explicit user scope/budget decision','Implement dedicated bounded runner without editing frozen sources','Exact payload reuse and paired-input/hidden-field boundary tests','Actor context and final-answer capacity checks','New delivery freeze and queue/reservation check']}
 assert sum(c['new_calls_max'] for c in cases)==24
 save(out/'proposal.json',proposal)
 print(json.dumps({'status':proposal['status'],'cases':len(cases),'reuse_cases':sum(c['reuse_existing_complete_branch'] for c in cases),'new_calls':24,'gpu_seconds_max':1800,'sources':len(sources)}))
if __name__=='__main__':prepare()
