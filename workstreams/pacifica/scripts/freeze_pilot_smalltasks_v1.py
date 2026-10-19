"""Local one-time input/authorization/budget freeze; never submits jobs."""
from pathlib import Path
import pilot_smalltasks_v1 as stage
from pilot_collection_v1 import create,now
R=stage.ROOT;a=stage.actor
if stage.PLAN.exists():raise ValueError('Already frozen')
parent=a.read(stage.original.PLAN);tasks=a.read(R/'data/pilot_smalltasks_v1/public_tasks.json')['instances']
sources=['results/pilot_smalltasks_v1_authorization_20261016.json','docs/pilot_smalltasks_v1_protocol_20261016.md','data/pilot_smalltasks_v1/public_tasks.json','data/pilot_smalltasks_v1/private_reference_design.json','scripts/pilot_smalltasks_adapter_v1.py','scripts/prospective_actor_smalltasks_v1.py','scripts/pilot_smalltasks_v1.py','scripts/pilot_smalltasks_v1.sbatch','scripts/freeze_pilot_smalltasks_v1.py','scripts/prospective_actor_reminder_v1.py','scripts/tgf_public_trace_reminder_v1.py','scripts/pilot_review_packet_reminder_v1.py','scripts/tgf_citation_reminder_v1.py','scripts/public_event_contract_reminder_v1.py','tests/test_pilot_smalltasks_v1.py','tests/test_actor_reminder_v1.py','tests/test_reminder_citation_compat.py','scripts/pilot_collection_recovery_v1.py','tests/test_pilot_collection_recovery_v1.py','configs/pilot_collection_v1.json']
p=dict(protocol='pilot_smalltasks_v1',frozen_at=now(),authorization=sources[0],parent_plan_sha256=a.sha(stage.original.PLAN),max_gpu_seconds=3600,max_actor_calls=1200,runner_deadline_seconds=3450,automatic_retries=0,max_new_jobs=1,max_attempts=30,monitor_calls=0,training_runs=0,max_no_tool_reminders=5,gate={'all30_technical_nonerror_and_full_review':True,'minimum_N_per_environment':6,'minimum_hardN_per_environment':6,'each_of3_tasks_has_hardN':True,'minimum_correct_completed_tasks_per_environment':6,'source_binding_projection_and_actual_input_capacity_required':True,'not_full_30P30N_pilot':True},source_hashes={n:a.sha(R/n) for n in sources},attempts=[])
for i in range(30):
 t=tasks[i%6];p['attempts'].append(dict(attempt_id=f"smalltasks1_{i+1:03d}_{t['task_id']}_ordinary",candidate_id=t['candidate_id'],task_id=t['task_id'],condition='ordinary',seed=27001+i,secondary_objective=a.load_original(t['candidate_id']).secondary_objective))
create(stage.PLAN,p);stage.verify();print({'sha256':a.sha(stage.PLAN),'new_sources':len(sources),'parent_sources':len(parent['source_hashes']),'attempts':30,'max_gpu_seconds':3600,'model_calls':0})
