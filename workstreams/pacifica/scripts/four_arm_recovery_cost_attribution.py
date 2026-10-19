"""Account for executed shared calls and hypothetical standalone arm attribution.

Standalone totals share the same initial review and must never be summed as the
physical batch total. Native wall/load timings describe observed execution only.
"""
import argparse,json
from pathlib import Path
from prospective_four_arm_v2 import create,read,METHODS
SUFFIXES={
 'ledger_only':('initial_review','ledger_only_judge'),
 'fixed_b2':('initial_review','fixed_b2_answer','fixed_b2_judge'),
 'tgf':('initial_review','targeted_question','tgf_answer','tgf_judge'),
 'b3':('initial_review','b3_extra_review','b3_judge'),
}
def aggregate(calls):
 result={}
 for model in sorted({c['model'] for c in calls}):
  rows=[c for c in calls if c['model']==model];us=[c['usage'] for c in rows if c['usage'] is not None]
  result[model]={'requested_calls':len(rows),'usage_receipts':len(us),'unknown_usage_calls':len(rows)-len(us),
    'known_input_tokens':sum(u['prompt_eval_count'] for u in us),'known_output_tokens':sum(u['eval_count'] for u in us),
    'actual_tokens_complete':len(rows)==len(us),'observed_successful_wall_seconds':sum(u['wall_seconds'] for u in us),
    'known_native_load_seconds':sum(u.get('load_duration',0)/1e9 for u in us),
    'known_prompt_processing_seconds':sum(u.get('prompt_eval_duration',0)/1e9 for u in us),
    'known_generation_seconds':sum(u.get('eval_duration',0)/1e9 for u in us)}
 return result

def analyze(run):
 plan=read(run/'plan.json');calls=[]
 for ip in sorted((run/'calls').glob('*_identity.json')):
  req=read(Path(str(ip).replace('_identity.json','_request.json')))
  up=Path(str(ip).replace('_identity.json','_usage.json'))
  calls.append({'name':read(ip)['name'],'model':req['model'],'usage':read(up) if up.exists() else None})
 per_trace={}
 for item in plan['items']:
  tid=item['trace_id'];rows=[c for c in calls if c['name'].startswith(tid+'/')]
  per_trace[tid]={m:aggregate([c for c in rows if c['name'].split('/')[1] in SUFFIXES[m]]) for m in METHODS}
 arms={m:aggregate([c for c in calls if c['name'].split('/')[1] in SUFFIXES[m]]) for m in METHODS}
 return {'physical_batch':aggregate(calls),'standalone_arm_attribution':arms,'per_trace_standalone_attribution':per_trace,
  'standalone_arm_totals_are_not_additive':True,'not_actual_equal_tokens_or_flops':True,
  'latency_not_standalone_wall_time':'Calls execute sequentially with shared initialization, model loads and caching. Do not sum per-arm time as batch wall time or claim a simultaneous randomized latency comparison.',
  'unknown_usage_not_zero':True,'api_usd':None}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=analyze(a.run);create(a.output,r);print(json.dumps(r['physical_batch']))
