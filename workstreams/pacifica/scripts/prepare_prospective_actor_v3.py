"""One-time freeze of six prospective original-task attempts; no inference."""
import json
import sys
from datetime import datetime
from pathlib import Path
import prospective_actor_v3 as p


def main():
    if p.PLAN.exists():
        raise ValueError('Plan already frozen; use verify, never regenerate')
    old=p.read(p.ROOT/'configs/candidate_actor_pilot_v1.json')
    meta=p.read(p.ROOT/'results/candidate_actor_pilot_v1_smoke_29479301/metadata.json')
    registry={'candidates':{}}
    attempts=[]
    for index,(name,condition,seed) in enumerate([
        ('bank_transfer_2','ordinary',701),('american_airlines_2','ordinary',801),
        ('bank_transfer_2','injected',702),('american_airlines_2','injected',802),
        ('bank_transfer_2','injected',703),('american_airlines_2','injected',803)]):
        c=p.load_original(name)
        registry['candidates'][name]={'family_id':'monitorbench_'+name+'_original',
            'split':'development','generation_approved':True,
            'independent_family':False,'held_out_final_test':False,
            'asset_digests':{k:p.digest(v) for k,v in {'request':c.user_request,'policy':c.policy,
                'schemas':c.schemas,'initial_state':p.canonical_state(c.environment.model_dump(mode='json')),
                'secondary_objective':c.secondary_objective}.items()}}
        attempts.append({'attempt_id':f'prospective_{index+1:03d}_{name}_{condition}',
                         'candidate_id':name,'condition':condition,'seed':seed,
                         'secondary_objective':c.secondary_objective})
    sources=set()
    for module in tuple(sys.modules.values()):
        file=getattr(module,'__file__',None)
        if file:
            path=Path(file).resolve()
            if path.is_relative_to(p.ROOT/'scripts') or path.is_relative_to(p.AGENT):
                if path.suffix=='.py':sources.add(path)
    # Original fixture assets may be loaded lazily by tools; freeze all local assets.
    for path in (p.AGENT/'universe_related_stuff').rglob('*'):
        if path.is_file() and path.suffix in ('.yaml','.yml','.json','.csv','.txt'):
            sources.add(path)
    for name in ['configs/prospective_actor_v1.json','results/prospective_preflight_failure_20261014.json','configs/prospective_actor_v2_dependencies.json','configs/prospective_actor_v2_requirements.lock','scripts/prospective_runtime_v2.py','scripts/prospective_runtime_v2.sbatch','docs/prospective_runtime_revision_2026-10-14.md','scripts/prospective_actor_v3.sbatch','scripts/prospective_actor_v2.py','configs/prospective_actor_v2.json','results/prospective_runtime_v2_receipt.json','results/prospective_v2_asset_diagnostic.json','docs/prospective_runtime_revision2_2026-10-14.md','scripts/prospective_preflight_v3.py','scripts/tgf_evidence_eval_v1.py',
                 'tests/test_prospective_actor_v3.py','tests/test_tgf_evidence_eval_v1.py',
                 'docs/prospective_pilot_protocol_2026-10-14.md',
                 'configs/candidate_actor_pilot_v1.json',
                 'results/candidate_actor_pilot_v1_smoke_29479301/metadata.json']:
        sources.add(p.ROOT/name)
    plan={'protocol':'prospective_original_actor_v3','frozen_at':datetime.now().astimezone().isoformat(),
          'max_new_actor_attempts':6,'max_actor_calls':240,'gpu_jobs':1,'gpu_seconds':2100,
          'runtime_cpu_jobs_total':1,'runtime_cpu_job_used':'29560911','new_installations':0,'new_cpu_jobs':0,'bounded_readonly_preflight_seconds':120,'runtime_retries':0,
          'runner_deadline_seconds':1950,'actor_max_seconds':300,'per_call_seconds':90,
          'actor_max_turns':40,'max_tool_events':100,'actor_context':131072,
          'actor_output_tokens':2048,'actor_think':'low','temperature':0.6,
          'actor':old['actor'],'actor_digest':old['actor_digest'],
          'actor_template_sha256':p.sha_text(meta['show']['template']),
          'api_reported_version':meta['version']['version'],
          'backend_installation_hashes':old['backend_installation_hashes'],
          'registry':registry,'attempts':attempts,'automatic_retries':0,
          'monitor_calls':0,'training_runs':0,'reference_status':'event_review_required',
          'source_hashes':{str(f.relative_to(p.ROOT)):p.sha(f) for f in sorted(sources)}}
    p.verify(plan)
    with p.PLAN.open('x') as f:json.dump(plan,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps({'plan_sha256':p.sha(p.PLAN),'source_files':len(sources),
                      'attempts':6,'new_model_calls':0}))


if __name__=='__main__':main()
