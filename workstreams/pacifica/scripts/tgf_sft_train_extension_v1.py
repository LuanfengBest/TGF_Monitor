"""The sole 44-event train extension, gated by the 20-event qualification receipt."""
from copy import deepcopy
from datetime import datetime
import argparse,json,signal,time
from pathlib import Path
import tgf_sft_qualification_v1 as base
from monitor_sft_candidates_v1 import obj_sha
ROOT=base.ROOT
PLAN=ROOT/'configs/tgf_sft_train_extension_v1.json'
OUT=ROOT/'data/annotation_review/tgf_sft_train_extension_v1'
PRIVATE=ROOT/'analysis/tgf_sft_train_extension_v1_private'
GATE=ROOT/'analysis/tgf_sft_qualification_acceptance_20261014.json'

def specs():
    rows=[]
    for domain,modes in [('bank',base.BANK_MODES*2+('legal','exact_cap')),
                         ('travel',base.TRAVEL_MODES*2+('legal','unknown'))]:
        for mode in modes:
            i=len(rows)+1
            rows.append({'case_id':f't{i:03d}','domain':domain,'family_id':base.FAMILIES[domain],
                         'split':'train','mode':mode,'seed':20042+i,
                         'expected_target_events':2 if mode in ('refusal_then_next','success_then_over_cap') else 1})
    return rows

def gate():
    r=base.read(GATE)
    if r['qualification_batch_data_gate_passed'] is not True or r['allows_bounded_train_expansion'] is not True:
        raise ValueError('Qualification not passed')
    if base.sha(ROOT/'data/training/tgf_sft_qualification_v1/candidates.jsonl')!=r['candidate_sha256']:raise ValueError('Qualified data changed')
    old=base.read(base.OUT/'manifest.json')
    if old['target_events']!=20 or sum(s['expected_target_events'] for s in specs())!=44:raise ValueError('64-event train budget mismatch')
    return r

def freeze():
    gate();base.verify()
    paths=set(base.source_hashes())|{str(Path(__file__).relative_to(ROOT)),str(GATE.relative_to(ROOT)),
        'tests/test_tgf_sft_train_extension_v1.py','configs/tgf_sft_qualification_v1.json',
        'data/annotation_review/tgf_sft_qualification_v1/manifest.json',
        'data/training/tgf_sft_qualification_v1/candidates.jsonl'}
    plan={'frozen_at':datetime.now().astimezone().isoformat(),'specs':specs(),
          'source_hashes':{p:base.sha(ROOT/p) for p in sorted(paths)},
          'max_target_events':44,'max_tool_dispatches':160,'max_wall_seconds':180,
          'per_dispatch_seconds':5,'no_automatic_retry':True,'split':'train','new_families':0,
          'model_calls':0,'gpu_jobs':0,'training_runs':0,'training_eligible':False}
    base.write_new(PLAN,plan);return {'frozen_sources':len(paths),'target_events':44,'plan_sha256':base.sha(PLAN)}

def verify():
    gate();p=base.read(PLAN)
    if p['specs']!=specs():raise ValueError('Spec changed')
    for path,h in p['source_hashes'].items():
        if base.sha(ROOT/path)!=h:raise ValueError('Source changed '+path)
    return p

def generate():
    plan=verify()
    if OUT.exists() or PRIVATE.exists():raise ValueError('Prior attempt exists; no retry')
    OUT.mkdir(parents=True);PRIVATE.mkdir(parents=True)
    base.write_new(OUT/'reservation.json',{'started_at':datetime.now().astimezone().isoformat(),'plan_sha256':base.sha(PLAN)})
    oldhashes={e['input_sha256'] for e in base.read(base.OUT/'manifest.json')['events']}
    hashes=set();deadline=time.monotonic()+plan['max_wall_seconds'];cases=[];events=[];dispatches=0
    handlers={sig:signal.signal(sig,base.on_timeout) for sig in (signal.SIGALRM,signal.SIGTERM,signal.SIGINT)}
    current=None;view=None;audit=None
    try:
        for spec in specs():
            current=spec['case_id'];view,state,calls=base.build_fixture(spec);view['messages']=[];audit=[]
            cls=base.BankMechanismEnvironment if spec['domain']=='bank' else base.ProjectionEnvironment
            env=cls(**deepcopy(state));runtime=base.FunctionsRuntime([base.make_function(t) for t in env.available_tools]);case_events=[]
            def journal(item):
                with (PRIVATE/(current+'_journal.jsonl')).open('a') as f:f.write(base.canonical(item)+'\n');f.flush()
            for name,args in calls+[('end_task',{})]:
                if dispatches>=plan['max_tool_dispatches']:raise base.BatchStop('Dispatch budget')
                if spec['mode']=='unknown' and name in ('schedule_transaction','send_email'):
                    if spec['domain']=='bank':env.bank_account.scheduled_transactions=base.AppendThenError(env.bank_account.scheduled_transactions)
                    else:env.inbox.emails=base.StoreThenError(env.inbox.emails)
                dispatches+=1;eid=base.dispatch_record(env,runtime,view,audit,name,args,journal,deadline)
                if name in ('schedule_transaction','send_email'):
                    if len(events)>=44:raise base.BatchStop('Target budget')
                    payload=base.make_input(view,eid);name_out=current+'__'+eid+'.json';base.write_new(OUT/name_out,payload)
                    h=base.sha(OUT/name_out)
                    if h in hashes or h in oldhashes:raise ValueError('Exact duplicate input')
                    hashes.add(h);row={'example_id':current+'__'+eid,'case_id':current,'event_id':eid,
                        'input_file':name_out,'input_sha256':h,'domain':spec['domain'],'family_id':spec['family_id'],
                        'split':'train','training_eligible':False}
                    events.append(row);case_events.append(row)
            base.write_new(OUT/(current+'_raw.json'),view)
            base.write_new(PRIVATE/(current+'.json'),{'spec':spec,'initial_state':state,'audit':audit})
            if len(case_events)!=spec['expected_target_events']:raise ValueError('Coverage mismatch')
            cases.append({'case_id':current,'raw_file':current+'_raw.json','raw_sha256':base.sha(OUT/(current+'_raw.json')),'target_events':len(case_events)})
    except BaseException as e:
        base.write_new(OUT/'failure.json',{'case_id':current,'error':type(e).__name__+': '+str(e),'events':events,'cases':cases,'tool_dispatches':dispatches,'no_retry':True})
        base.write_new(PRIVATE/'partial.json',{'view':view,'audit':audit});raise
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        for sig,h in handlers.items():signal.signal(sig,h)
    result={'status':'generated_pending_label_audit','plan_sha256':base.sha(PLAN),'cases':cases,'events':events,
        'target_events':len(events),'tool_dispatches':dispatches,'train_events_total_with_qualification':64,
        'independent_new_families':0,'scripted_not_actor_rollouts':True,'model_calls':0,'gpu_jobs':0,'training_runs':0,'training_eligible':False}
    base.write_new(OUT/'manifest.json',result)
    return {k:result[k] for k in ('status','target_events','tool_dispatches','train_events_total_with_qualification')}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['freeze','verify','generate']);m=p.parse_args().mode
    r={'freeze':freeze,'verify':verify,'generate':generate}[m]();print(json.dumps(r if m!='verify' else {'verified':True}))
