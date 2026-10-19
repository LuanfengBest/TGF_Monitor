"""Freeze actual new public inputs only after the entire generation/reference audit.

Does not submit or call models. The audit is completed before any monitor output;
all technically eligible traces are included, irrespective of their safety labels.
"""
import argparse
import datetime
import json
from pathlib import Path
import prospective_four_arm_v3 as p


def verify_reference(reference, planned, run_path):
    assert reference['planned_trace_ids']==planned
    assert reference['review_complete'] is True and reference['human_gold'] is False
    assert reference['reviewed_before_any_monitor_output'] is True
    assert [r['trace_id'] for r in reference['traces']]==planned
    for row in reference['traces']:
        events=p.read(run_path/row['trace_id']/'rollout/oracle/events.json')
        assert row['review_complete'] is True
        assert [e['event_id'] for e in row['events']]==[e['event_id'] for e in events]
        assert row['event_count']==len(events)
    assert reference['all_event_count']==sum(r['event_count'] for r in reference['traces'])
    for name,hash_value in reference['source_hashes'].items():
        assert p.sha(p.ROOT/name)==hash_value


def freeze(run_path, qualification_path):
    run_path=run_path.resolve();qualification_path=qualification_path.resolve()
    gen=p.read(p.ROOT/'configs/prospective_actor_v6.json')
    assert p.read(run_path/'plan.json')==gen
    gate=p.read(qualification_path)
    assert gate['actor_plan_sha256']==p.sha(p.ROOT/'configs/prospective_actor_v6.json')
    assert gate['stage_qualified'] is True and gate['reference_review_complete'] is True
    assert gate['reviewed_before_any_monitor_output'] is True
    assert gate['human_gold'] is False
    assert not (p.ROOT/'results/prospective_four_arm_v3_submission.json').exists()
    assert not (p.ROOT/'results/prospective_four_arm_v3.reservation.json').exists()
    planned=[a['attempt_id'] for a in gen['attempts']]
    assert [a['trace_id'] for a in gate['attempts']]==planned
    eligible=[a['trace_id'] for a in gate['attempts'] if a['technical_eligible'] is True]
    assert eligible==gate['technical_eligible_ids'] and eligible
    assert gate['max_following_calls']==len(eligible)*9
    assert all(a.get('exclusion_reason') for a in gate['attempts'] if not a['technical_eligible'])
    # Keep the private reviewed labels outside every model input.
    references=p.ROOT/gate['reference_path']
    assert p.sha(references)==gate['reference_sha256']
    reference=p.read(references)
    verify_reference(reference,planned,run_path)
    items=[];input_paths=[]
    for tid in eligible:
        d=run_path/tid/'rollout'
        view=d/'monitor_view.json';ctx=d/'raw/actor_context.json'
        item={'trace_id':tid,'view_path':str(view.relative_to(p.ROOT)),
              'actor_context_path':str(ctx.relative_to(p.ROOT)),
              'view_digest':p.digest(p.read(view)), 'actor_context_digest':p.digest(p.read(ctx))}
        p.verify_input(item);items.append(item);input_paths.extend([view,ctx])
    old=p.read(p.ROOT/'configs/prospective_four_arm_v2.json')
    plan={k:old[k] for k in ('models','api_reported_version','actor_context','actor_think',
                            'actor_seed','actor_temperature','answer_output_tokens')}
    plan.update(protocol='prospective_four_arm_v3',frozen_at=datetime.datetime.now().astimezone().isoformat(),
                split='development',items=items,qualification_path=str(qualification_path.relative_to(p.ROOT)),
                final_judge_policy_path=old['final_judge_policy_path'],final_judge_initial_review='omit',
                per_arm_monitor_token_ceiling=98304,per_arm_available_monitor_calls=3,
                actual_compute_equal=False,max_calls=9*len(items),gpu_seconds=2700,
                runner_deadline_seconds=2500,per_call_seconds=450,automatic_retries=0,training_runs=0)
    sources={p.ROOT/n for n in gen['source_hashes']}
    sources.update(p.ROOT/n for n in reference['source_hashes'])
    sources.update(input_paths+[qualification_path,references,p.ROOT/old['final_judge_policy_path'],
                  p.ROOT/'configs/prospective_actor_v6.json',p.ROOT/'configs/prospective_four_arm_v2.json',
                  Path(__file__),p.ROOT/'tests/test_tgf_main_v3_freeze.py',p.ROOT/'scripts/submit_prospective_four_arm_v3.py',
                  p.ROOT/'scripts/prospective_four_arm_v3.sbatch'])
    plan['source_hashes']={str(f.relative_to(p.ROOT)):p.sha(f) for f in sorted(sources)}
    p.verify(plan);p.create(p.PLAN,plan)
    return {'plan_sha256':p.sha(p.PLAN),'items':len(items),'max_calls':plan['max_calls'],
            'gpu_seconds':2700,'model_calls':0,'submitted':False}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--actor-run',type=Path,required=True)
    parser.add_argument('--qualification',type=Path,required=True);a=parser.parse_args()
    print(json.dumps(freeze(a.actor_run,a.qualification)))
