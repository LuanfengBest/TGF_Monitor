"""Offline reconstruction with the actual approved recovery budget and payload check."""
import argparse,json
from pathlib import Path
import prospective_four_arm_v2_runtime_recovery as recovery
from analyze_prospective_four_arm_v2 import analyze

def main():
 p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
 run=args.run.resolve();recovery.verify();policy=recovery.base.read(run/'runtime_policy.json');assert policy==recovery.POLICY
 decision=recovery.base.read(run/'runtime_decision.json');assert decision==recovery.approved()
 result=analyze(run)
 assert result['stage_summary']['calls']<=policy['new_call_cap']
 old=recovery.base.ROOT/'results/prospective_four_arm_v2_29587789/calls/call_0001_request.json'
 new=run/'calls/call_0001_request.json'
 if new.exists():assert new.read_bytes()==old.read_bytes(),'Recovery changed first inference payload'
 result.update(runtime_policy=policy,first_request_identical_to_failed_attempt=new.exists(),
  old_failed_attempt_counted_separately=True,first_call_native_timing=(recovery.base.read(run/'calls/call_0001_usage.json') if (run/'calls/call_0001_usage.json').exists() else None))
 recovery.base.create(args.output,result)
 print(json.dumps({'status':result['stage_summary']['status'],'calls':result['stage_summary']['calls'],'costs':result['costs'],'rows':[{'trace_id':x['trace_id'],'completed':x['completed_methods'],'selected_event':x['selected_event']} for x in result['rows']]},ensure_ascii=False))
if __name__=='__main__':main()
