"""Read-only integrity/cost/context report; does not assign safety labels or run models."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from ollama_client import digest
from tgf_public_trace_v1 import shared_bundle
from paired_protocol_v3 import Counter, REVIEW_SYSTEM, render_prompt

ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def projected(msg):
    value={k:deepcopy(msg[k]) for k in ('role','content','thinking','tool_calls','tool_name') if k in msg}
    for call in value.get('tool_calls',[]):call.pop('id',None)
    return value

def check_context(context,view):
    if len(context)<2 or context[0].get('role')!='system' or context[1]!={'role':'user','content':view['user_request']}:
        raise ValueError('Original task context mismatch')
    actual=[projected(m) for m in context[2:]]
    public=[projected(m) for m in view['messages'] if m.get('source_type')!='harness_execution_record']
    if actual!=public:raise ValueError('Private/raw to public projection mismatch')

def check_states(run,events):
    previous=read(run/'oracle/initial_state.json')
    rows=[]
    for e in events:
        if not e['dispatched']:
            if e['status']!='not_dispatched':raise ValueError('Dispatch metadata mismatch')
            rows.append({'event_id':e['event_id'],'dispatched':False});continue
        before=read(run/f"oracle/{e['event_id']}_before.json");after=read(run/f"oracle/{e['event_id']}_after.json")
        if previous!=before:raise ValueError('State chain broken '+e['event_id'])
        if e['status']=='returned' and (digest(before)!=e['before_sha256'] or digest(after)!=e['after_sha256']):
            raise ValueError('State hash mismatch')
        previous=after
        rows.append({'event_id':e['event_id'],'dispatched':True,'state_changed':before!=after,'status':e['status']})
    if previous!=read(run/'oracle/final_state.json'):raise ValueError('Final state mismatch')
    return rows

def analyze(out):
    plan=read(ROOT/'configs/prospective_actor_v3.json');summary=read(out/'summary.json')
    if read(out/'plan.json')!=plan:raise ValueError('Run plan mismatch')
    for n,h in plan['source_hashes'].items():
        if sha(ROOT/n)!=h:raise ValueError('Frozen source changed '+n)
    counter=Counter();rows=[];requests=0;usage=[]
    for a in plan['attempts']:
        d=out/a['attempt_id'];run=d/'rollout';row={'attempt_id':a['attempt_id'],'family':a['candidate_id'],'condition_not_label':a['condition'],'status':'not_attempted'}
        if (run/'summary.json').exists():
            s=read(run/'summary.json');row.update(status=s['status'],elapsed_seconds=s['elapsed_seconds'],calls=s['actor_calls'],view_integrity=s['view_integrity'])
            reqs=sorted((d/'actor_calls').glob('*_request.json'));requests+=len(reqs)
            if len(reqs)!=s['actor_calls']:raise ValueError('Submitted/request count mismatch')
            if len(reqs)>40:raise ValueError('Per-attempt call budget exceeded')
            for req in reqs:
                p=read(req)
                if p['model']!=plan['actor'] or p['options']['seed']!=a['seed']:raise ValueError('Request identity mismatch')
                up=Path(str(req).replace('_request.json','_usage.json'))
                if up.exists():usage.append(read(up))
            events=read(run/'oracle/events.json');row['state_events']=check_states(run,events)
            view=read(run/'monitor_view.json');context=read(run/'raw/actor_context.json')
            row['state_chain_verified']=True
            try:
                check_context(context,view);bundle=shared_bundle(view)
                row['public_projection_verified']=True
                row['review_input_tokens']=counter.check(render_prompt(REVIEW_SYSTEM,bundle),4096)
                row['fits_full_monitor_context']=True
            except (ValueError,KeyError,TypeError) as exc:
                row['projection_or_capacity_error']=str(exc);row['fits_full_monitor_context']=False
            row['safety_label']=None;row['reference_status']='pending_event_review'
            row['formal_four_arm_ready']=s['status']=='ended' and row.get('fits_full_monitor_context',False)
        rows.append(row)
    if requests!=summary['calls_submitted'] or requests>plan['max_actor_calls']:raise ValueError('Stage count mismatch')
    return {'stage_status':summary['status'],'plan_sha256':sha(ROOT/'configs/prospective_actor_v3.json'),
        'source_hashes_verified':len(plan['source_hashes']),'planned_attempts':6,'calls_submitted':requests,
        'calls_with_usage':len(usage),'calls_without_final_usage':requests-len(usage),
        'known_input_tokens':sum(x.get('prompt_eval_count',0) for x in usage),
        'known_output_tokens':sum(x.get('eval_count',0) for x in usage),
        'split':'development','human_gold':False,'monitor_calls':0,'training_runs':0,'attempts':rows}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=analyze(a.run)
    with a.output.open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k!='attempts'}))
