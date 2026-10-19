"""Offline recovery audit acceptance; never submits work or changes frozen inputs."""
import json,hashlib,sys,runpy,zipfile
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from pilot_review_packet_v1 import validate_case,select_balanced
from analyze_prospective_actor_v6 import check_context,check_states
from pilot_collection_recovery_v1 import verified_guard_exclusion
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def save(path,value):
 with path.open('x') as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')
P=ROOT/'data/annotation_review/pilot_collection_recovery_v1_29691597'
M=read(P/'manifest.json');R=read(P/'reviews/blank_review.json')
S=runpy.run_path(str(ROOT/'analysis/pilot_recovery_review_decisions_20261015.py'))['S']
assert set(S)==set(range(1,21))
for name,h in read(P/'PACKET_SHA256.json').items():assert sha(P/name)==h,name
for name,h in M['source_hashes'].items():assert sha(ROOT/name)==h,name
plan=read(ROOT/'configs/pilot_collection_recovery_v1.json');parentplan=read(ROOT/plan['parent_plan'])
for obj in [plan,parentplan]:
 for name,h in obj['source_hashes'].items():assert sha(ROOT/name)==h,name
run=ROOT/M['run'];summary=read(run/'summary.json');assert summary['status']=='completed_with_guard_exclusions'
assert summary['planned_attempt_ids']==[x['attempt_id'] for x in plan['attempts']]
assert not summary['not_attempted_ids'];assert len(summary['attempts'])==20
receipt=read(ROOT/'results/pilot_collection_recovery_v1_archive_receipt.json')
assert receipt['job_id']=='29691597' or receipt['job_id']==29691597
assert '|COMPLETED|0:0|' in receipt['sacct'];assert not receipt['queue'].strip()
assert sha(ROOT/receipt['archive'])==receipt['sha256']=='c11b42faf8a4233b0885dfb7b73002d18b9bb41b53a4feeea1d5f82a00b89571'
oldaccept=read(ROOT/'analysis/pilot_recovery_29691597_archive_acceptance_20261015.json');assert oldaccept['all_perfile_hashes_passed'] and oldaccept['files']==1912
mapping={x['case_id']:x for x in read(P/'private_reference/identity_mapping.json')};rows=[];usage={'requests':0,'responses':0,'input_tokens':0,'output_tokens':0};guard=[]
for case,blank in zip(M['cases'],R['cases']):
 assert case['case_id']==blank['case_id'];cid=case['case_id'];n=int(cid.split('_')[1]);spec=S[n];facts=read(P/'private_reference'/cid/'event_facts.json');view=read(P/'public'/cid/'trace.json');attempt=mapping[cid]['attempt_id'];d=run/attempt;rd=d/'rollout'
 check_context(read(rd/'raw/actor_context.json'),view);check_states(rd,read(rd/'oracle/events.json'))
 # Every execution decision explicit in manually inspected list; no default safe label.
 assignments={i:('not_executed','not_applicable','Reviewed permitted query/end/unsuccessful attempt with identical full before/after states. No executed state mutation; no success inferred from actor narrative.',[],False) for i in spec['none']}
 for g in spec['groups']:
  for i in g['ids']:
   assert i not in assignments,(cid,i);assignments[i]=('executed',g['authorization'],g['reason'],g['sources'],g['proof'])
 assert set(assignments)==set(range(1,len(facts)+1)),cid
 for i,(f,e) in enumerate(zip(facts,blank['events']),1):
  ex,auth,why,extra,proof=assignments[i];assert e['event_id']==f['event_id']==f'e{i:04d}'
  assert f['state_changed']==(ex=='executed'),(cid,i,'state')
  sources=list(dict.fromkeys(['user_request',*extra,f['call_source'],f['result_source']]))
  e.update(execution=ex,authorization=auth,rationale=why+f" Inspected {f['event_id']} {f['tool']} arguments, {f['call_source']}/{f['result_source']}, and complete state diff.",authorization_source_ids=sources,public_violation_proof=proof,public_proof_source_ids=sources if proof else [])
  # Check public IDs; all private evidence points must resolve in this exact initial snapshot.
  initial=read(rd/'oracle/initial_state.json')
  for src in extra:
   if src.startswith('message_'):assert int(src.split('_')[1])<len(view['messages'])
   if src.startswith('oracle/initial_state.json#'):
    x=initial
    for part in src.split('#',1)[1].strip('/').split('/'):
     x=x[int(part)] if isinstance(x,list) else x[part]
    assert x is not None
 blank.update(review_complete=True,task_completion='incomplete',notes=spec['notes'],eligible_for_P_N_target=case['actor_status']!='error',disposition='context_guard_failure_excluded' if case['actor_status']=='error' else 'AI_reference_reviewed_observed_prefix')
 vr=validate_case(case,blank,facts,view);vr.update(attempt_id=attempt,actor_status=case['actor_status'],eligible_for_P_N_target=blank['eligible_for_P_N_target'],packet=str(P.relative_to(ROOT)),review_scope='all available tool events and relevant authorization evidence',condition_not_label=mapping[cid]['condition_not_label']);rows.append(vr)
 requests=sorted((d/'actor_calls').glob('call_*_request.json'));responses=sorted((d/'actor_calls').glob('call_*_response.json'));rs=read(rd/'summary.json')
 assert len(requests)==len(responses)==rs['actor_calls']==summary['attempts'][n-1]['actor_calls']
 for a,b in zip(requests,responses):
  assert a.name.replace('_request','_response')==b.name
  q=read(a);v=read(b);assert v['done'] is True
  usage['input_tokens']+=v['prompt_eval_count'];usage['output_tokens']+=v['eval_count']
 usage['requests']+=len(requests);usage['responses']+=len(responses)
 if case['actor_status']=='error':assert verified_guard_exclusion(d,parentplan);guard.append(attempt)
assert len(guard)==2 and usage['requests']==usage['responses']==summary['calls_submitted']==355
assert sum(len(x['events']) for x in R['cases'])==339
R.update(reviewed_at=datetime.now(ZoneInfo('America/New_York')).isoformat(),packet=str(P.relative_to(ROOT)),all_available_events_reviewed=True,available_attempts_reviewed=20,available_events_reviewed=339,full_planned_recovery_review_complete=True,human_review_status='not_performed',monitor_outputs_seen_for_these_attempts=False,semantic_review_limitations=['Primary AI nonblind, not independent or human gold','Relevant authorization sources and every tool event/state diff inspected; no claim of independent annotation agreement','Unknown itinerary/metadata/notification semantics remain unresolved'],manual_transcription_sha256=sha(ROOT/'analysis/pilot_recovery_review_decisions_20261015.py'),external_authorization_source_hashes={f:sha(ROOT/f) for f in ['configs/bank_authorization_v2.json','docs/prospective_reference_contract_2026-10-14.md']})
out=ROOT/'analysis/pilot_collection_recovery_v1_AI_review_20261015.json'
parentcoverage=read(ROOT/'analysis/pilot_collection_v1_b01_AI_coverage_20261015.json');assert sha(ROOT/parentcoverage['review_file'])==parentcoverage['review_sha256']
merged=parentcoverage['rows']+rows
assert len(merged)==30 and len({r['attempt_id'] for r in merged})==30
assert [r['attempt_id'] for r in merged]==[a['attempt_id'] for a in parentplan['attempts'][:30]]
eligible=[r for r in merged if r['eligible_for_P_N_target']];assert len(eligible)==26
coverage=select_balanced(eligible)
report={'at':R['reviewed_at'],'review_file':str(out.relative_to(ROOT)),'review_sha256':hashlib.sha256((json.dumps(R,ensure_ascii=False,indent=2)+'\n').encode()).hexdigest(),'source_hashes_and_public_projection_and_state_chains_valid':True,'archived_files_verified':1912,'recovery_sources_verified':len(M['source_hashes']),'all_20_recovery_attempts_all_339_events_reviewed':True,'parent_review_preserved':parentcoverage['review_sha256'],'planned':30,'attempted':30,'not_attempted':0,'events_reviewed':455,'eligible_non_error_attempts':26,'runtime_guard_excluded':4,'full_planned_available_review_complete':True,'technical_batch_all_attempts_successful':False,'ready_for_monitor_comparison':False,'ready_for_training':False,'automatic_batch2_submission_allowed':False,'human_gold':False,'independent_review':False,'human_review_status':'not_performed','reviewer_type':'AI','rows':merged,'coverage':coverage,'recovery_usage':usage,'recovery_guard_exclusions':guard,'recovery_gpu_seconds':1667,'parent_plus_recovery_gpu_seconds':2274,'parent_plus_recovery_calls':478,'cumulative_completed_calls':1806,'cumulative_main_gpu_seconds':37471,'cumulative_explicit_cpu_seconds':2526,'historical_trainings':2,'queue_last_verified_empty_at':'2026-10-15T20:43:04-04:00','main_question_answerability':'not_ready: bank no certified negative; airline only two sensitive-action negatives, and overall target30P30N per environment far unmet; common interface qualification not done; same two task instances'}
save(out,R);assert sha(out)==report['review_sha256'];save(ROOT/'analysis/pilot_collection_b01_merged_AI_coverage_20261015.json',report)
print(json.dumps({k:report[k] for k in ['planned','attempted','events_reviewed','eligible_non_error_attempts','runtime_guard_excluded','coverage','recovery_usage']},ensure_ascii=False,indent=2))
