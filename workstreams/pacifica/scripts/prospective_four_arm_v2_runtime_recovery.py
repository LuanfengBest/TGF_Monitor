"""Proposed one-time runtime recovery; requires an explicit human decision receipt.

The v2 experiment and failed job are immutable. Only per-request and stage time
limits change. All model payloads, five inputs, methods and inference code reuse v2.
This file does not submit jobs. No recovery is currently authorized or launched.
"""
import argparse, hashlib, json, os, signal, time
from pathlib import Path
import prospective_four_arm_v2 as base

POLICY = {
    'protocol':'prospective_four_arm_v2_runtime_recovery_v1',
    'failed_job':'29587789',
    'source_plan_sha256':'ec230207e2c990b0fd8de873e8f2ff97b5ef73d9d3687821cebc150315fed44d',
    'failed_gpu_seconds':166,'failed_calls':1,
    'new_call_cap':42,'new_gpu_seconds':2520,'runner_deadline_seconds':2330,
    'per_call_seconds':450,'automatic_retries':0,'training_runs':0,
    'changed_fields':['per_call_seconds','runner_deadline_seconds'],
}
DECISION=base.ROOT/'results/prospective_four_arm_v2_runtime_recovery_decision.json'
RESERVATION=base.ROOT/'results/prospective_four_arm_v2_runtime_recovery.reservation.json'

def runtime_plan(source):
    assert POLICY['failed_calls']+POLICY['new_call_cap']<=source['max_calls']
    assert POLICY['failed_gpu_seconds']+POLICY['new_gpu_seconds']<=source['gpu_seconds']
    plan=dict(source)
    for field in POLICY['changed_fields']: plan[field]=POLICY[field]
    return plan

def verify():
    assert base.sha(base.PLAN)==POLICY['source_plan_sha256']
    source=base.verify(base.read(base.PLAN))
    closed=base.read(base.ROOT/'results/prospective_four_arm_v2_29587789_closeout.json')
    line=next(x.split('|') for x in closed['sacct'].splitlines() if x.startswith('29587789|'))
    assert line[1]=='FAILED' and int(line[3])==POLICY['failed_gpu_seconds']
    failed=base.ROOT/'results/prospective_four_arm_v2_29587789'
    assert base.read(failed/'summary.json')['calls']==1
    assert not list((failed/'calls').glob('*_response.json'))
    assert not list(failed.glob('prospective5_*/*_result.json'))
    return source

def approved():
    decision=base.read(DECISION)
    assert decision['status']=='human_authorized_once'
    assert decision['policy']==POLICY
    assert decision['entrypoint_sha256']==base.sha(__file__)
    assert decision['user_instruction'].strip() and decision['authorized_at']
    return decision

class Client(base.Client):
    def __init__(self,out,plan):
        super().__init__(out,plan)
        self.maximum=POLICY['new_call_cap']

def run(out):
    source=verify();decision=approved();plan=runtime_plan(source)
    base.create(RESERVATION,{'job_id':os.environ['SLURM_JOB_ID'],'policy':POLICY,'output':str(out)})
    out.mkdir(parents=True,exist_ok=False)
    base.create(out/'plan.json',source)
    base.create(out/'runtime_policy.json',POLICY)
    base.create(out/'runtime_decision.json',decision)
    signal.signal(signal.SIGALRM,lambda *a:(_ for _ in ()).throw(TimeoutError('Recovery per-call deadline')))
    client=Client(out/'calls',plan);attempts=[];status='failed';error=None
    try:
        for model in ('qwen3:32b','gpt-oss:20b'):
            meta=client.metadata(model);base.save(out/(model.replace(':','_')+'_metadata.json'),meta)
            assert meta['version']['version']==source['api_reported_version']
            assert {m['name']:m['digest'] for m in meta['tags']['models']}[model]==source['models'][model]['digest']
            assert hashlib.sha256(meta['show']['template'].encode()).hexdigest()==source['models'][model]['template_sha256']
        failures=0
        for index,item in enumerate(source['items']):
            row={'trace_id':item['trace_id'],'status':'started'};attempts.append(row);base.save(out/'attempts.json',attempts)
            try:
                gate=base.run_trace(client,item,out/item['trace_id'],plan)
                if not all(gate.values()):raise ValueError('Trace integrity failed')
                row['status']='completed';failures=0
            except Exception as exc:
                row.update(status='failed',error=repr(exc));failures+=1
                if index==0 or failures>=2:raise
            finally:base.save(out/'attempts.json',attempts)
        status='completed_with_failures' if any(a['status']!='completed' for a in attempts) else 'completed'
    except BaseException as exc:error=repr(exc);raise
    finally:
        signal.alarm(0)
        base.save(out/'summary.json',{'status':status,'error':error,'calls':client.count,'attempts':attempts,
            'planned_ids':[i['trace_id'] for i in source['items']],'training_runs':0,
            'runtime_recovery':POLICY,'semantic_results':'pending','costs_successful_calls_only':client.costs})
        for model in ('qwen3:32b','gpt-oss:20b'):
            try:client.unload(model)
            except Exception:pass

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['verify','run']);parser.add_argument('--output',type=Path);args=parser.parse_args()
    if args.command=='verify':verify();print(json.dumps({'offline_verified':True,'authorized':DECISION.exists(),'policy':POLICY}))
    else:
        if args.output is None:parser.error('--output required')
        run(args.output)
