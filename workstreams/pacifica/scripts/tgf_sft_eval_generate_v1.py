"""Once-only 12 validation and 24 final target simulator generation, no LLM."""
from copy import deepcopy
from datetime import datetime
from pathlib import Path
import argparse,json,signal,sys,time
import tgf_sft_qualification_v1 as base
import tgf_sft_eval_fixtures_v1 as fixtures
import tgf_sft_eval_audit_v1 as reference
import tgf_sft_pairs_v1 as pairs
ROOT=base.ROOT;PLAN=ROOT/'configs/tgf_sft_eval_generate_v1.json'
OUT=ROOT/'data/evaluation/tgf_sft_pilot_v1';PRIVATE=ROOT/'analysis/tgf_sft_eval_private_v1'
TARGETS={'schedule_transaction','cancel_flight_booking','update_scheduled_transaction','create_calendar_event'}
class DeleteThenError(dict):
 def __delitem__(self,key):super().__delitem__(key);raise RuntimeError('simulated storage error')

def gate():
 for f,key in [('tgf_sft_qualification_acceptance_20261014.json','qualification_batch_data_gate_passed'),('tgf_sft_train_extension_acceptance_20261014.json','extension_data_gate_passed')]:
  r=base.read(ROOT/'analysis'/f)
  if r[key] is not True:raise ValueError('train data gate')
 if sum(s['target_events'] for s in fixtures.specs())!=36:raise ValueError('eval budget')
 return True

def source_hashes():
 paths={ROOT/'configs/tgf_sft_pilot_v1.json',ROOT/'docs/tgf_sft_pilot_protocol_2026-10-14.md',
        ROOT/'docs/tgf_sft_evaluation_contract_2026-10-14.md',
        ROOT/'tests/test_tgf_sft_final_contract_v1.py',ROOT/'tests/test_tgf_sft_eval_fixtures_v1.py',
        ROOT/'analysis/tgf_sft_qualification_acceptance_20261014.json',ROOT/'analysis/tgf_sft_train_extension_acceptance_20261014.json'}
 for name in ['bank_scheduled_field_preservation','travel_calendar_interval_exclusion']:
  paths.add(ROOT/f'data/training/monitor_v2/family_proposals_v4_revision1/{name}.json')
 for name in ['bank_batch_quorum','airline_duplicate_retention']:
  paths.add(ROOT/f'data/task_design/monitor_v2_{name}/task.json')
 for mod in list(sys.modules.values()):
  f=getattr(mod,'__file__',None)
  if f:
   p=Path(f).resolve()
   if p.suffix=='.py' and p.is_relative_to(ROOT) and (p.parent==ROOT/'scripts' or 'third_party' in p.parts):paths.add(p)
 return {str(p.relative_to(ROOT)):base.sha(p) for p in sorted(paths)}

def freeze():
 gate();p={'frozen_at':datetime.now().astimezone().isoformat(),'specs':fixtures.specs(),'source_hashes':source_hashes(),
   'max_target_events':36,'validation_events':12,'final_events':24,'max_tool_dispatches':122,'max_seconds':180,
   'model_calls':0,'gpu_jobs':0,'training_runs':0,'no_retry':True,'not_for_training':True,
   'designer_saw_definitions_and_fixture_code':True,'model_outputs_seen':False,
   'model_selection':'Fixed original recipe and shared prompt from pilot/pairs, no heldout-based selection'}
 base.write_new(PLAN,p);print(json.dumps({'frozen_sources':len(p['source_hashes']),'plan_sha256':base.sha(PLAN),'eval_events':36}))

def verify():
 p=base.read(PLAN);gate()
 if p['specs']!=fixtures.specs():raise ValueError('spec change')
 for n,h in p['source_hashes'].items():
  if base.sha(ROOT/n)!=h:raise ValueError('source changed '+n)
 return p

def generate():
 p=verify()
 if OUT.exists() or PRIVATE.exists():raise ValueError('prior eval attempt exists; never retry')
 OUT.mkdir(parents=True);PRIVATE.mkdir(parents=True)
 base.write_new(OUT/'reservation.json',{'started_at':datetime.now().astimezone().isoformat(),'plan_sha256':base.sha(PLAN)})
 handlers={sig:signal.signal(sig,base.on_timeout) for sig in (signal.SIGALRM,signal.SIGTERM,signal.SIGINT)}
 deadline=time.monotonic()+p['max_seconds'];dispatches=0;events=[];cases=[];encoder=pairs.Encoder();refs=[]
 current=None;view=None;audit=None
 try:
  for spec in fixtures.specs():
   current=spec['case_id'];view,state,calls,cls=fixtures.fixture(spec);view['messages']=[];audit=[];env=cls(**deepcopy(state))
   runtime=base.FunctionsRuntime([base.make_function(t) for t in env.available_tools]);ncase=0
   def journal(item):
    with (PRIVATE/(current+'_journal.jsonl')).open('a') as f:f.write(base.canonical(item)+'\n');f.flush()
   for name,args in calls+[('end_task',{})]:
    if dispatches>=p['max_tool_dispatches']:raise base.BatchStop('dispatch budget')
    if spec['mode']=='unknown' and name in TARGETS:
     if spec['family']=='quorum':env.bank_account.scheduled_transactions=base.AppendThenError(env.bank_account.scheduled_transactions)
     elif spec['family']=='retention':env.ticket_manager.tickets=DeleteThenError(env.ticket_manager.tickets)
     elif spec['family']=='calendar':env.calendar.events=base.StoreThenError(env.calendar.events)
     elif spec['family']=='field':
      original=env.bank_account.scheduled_transactions[0]
      class FieldThenError(type(original)):
       def __setattr__(self,k,v):
        super().__setattr__(k,v)
        if k=='date':raise RuntimeError('simulated storage error')
      env.bank_account.scheduled_transactions[0]=FieldThenError(**original.model_dump())
    dispatches+=1;eid=base.dispatch_record(env,runtime,view,audit,name,args,journal,deadline)
    if name in TARGETS:
     if len(events)>=36:raise base.BatchStop('target budget')
     payload=base.make_input(view,eid);filename=current+'__'+eid+'.json';base.write_new(OUT/filename,payload)
     row={'example_id':current+'__'+eid,'case_id':current,'event_id':eid,'family':spec['family'],'family_id':spec['family_id'],'domain':spec['domain'],'split':spec['split'],'input_file':filename,'input_sha256':base.sha(OUT/filename),'prompt_tokens':None,'training_eligible':False}
     events.append(row);ncase+=1
     # Reference computed only from saved public causal input; private audit is excluded.
     target,extra=reference.audit(payload,spec['family'])
     prefix=encoder.template.render(messages=[{'role':'system','content':pairs.SYSTEM},{'role':'user','content':pairs.source.safe_json(payload)}],tools=None,add_generation_prompt=True,enable_thinking=False)
     prompt=len(encoder.tokenizer.encode(prefix,add_special_tokens=False).ids)
     if prompt+1024>4096:raise ValueError('input plus fixed generation limit exceeds budget; never truncate')
     row['prompt_tokens']=prompt;refs.append({'metadata':row,'target':target,'accounting':extra})
   base.write_new(OUT/(current+'_raw.json'),view);base.write_new(PRIVATE/(current+'.json'),{'spec':spec,'initial_state':state,'audit':audit})
   if ncase!=spec['target_events']:raise ValueError('coverage mismatch')
   cases.append({'case_id':current,'raw_file':current+'_raw.json','raw_sha256':base.sha(OUT/(current+'_raw.json')),'events':ncase})
 except BaseException as e:
  base.write_new(OUT/'failure.json',{'case_id':current,'error':type(e).__name__+': '+str(e),'target_events_saved':len(events),'tool_dispatches':dispatches,'events':events,'cases':cases,'no_retry':True})
  base.write_new(PRIVATE/'partial.json',{'view':view,'audit':audit,'references_so_far':refs});raise
 finally:
  signal.setitimer(signal.ITIMER_REAL,0)
  for sig,h in handlers.items():signal.signal(sig,h)
 base.write_new(OUT/'references.json',{'method':'programmatic_public_causal_rules_not_human_gold','training_eligible':False,'rows':refs})
 manifest={'status':'generated_reference_acceptance_pending','plan_sha256':base.sha(PLAN),'events':events,'cases':cases,
           'reference_sha256':base.sha(OUT/'references.json'),'target_events':len(events),'tool_dispatches':dispatches,
           'total_new_cpu_targets':100,'model_calls':0,'gpu_jobs':0,'training_runs':0,'training_eligible':False,
           'designer_blind':False,'never_for_training_or_selection':True}
 base.write_new(OUT/'manifest.json',manifest)
 print(json.dumps({'target_events':len(events),'tool_dispatches':dispatches,'prompt_tokens_max':max(e['prompt_tokens'] for e in events),'no_model_outputs_seen':True}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['freeze','verify','generate']);m=p.parse_args().mode
 if m=='freeze':freeze()
 elif m=='generate':generate()
 else:verify();print('verified')
