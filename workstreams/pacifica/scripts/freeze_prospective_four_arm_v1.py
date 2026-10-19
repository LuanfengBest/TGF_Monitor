"""One-time actual-input freeze after source/qualification review, before monitor inference."""
import sys,datetime
from pathlib import Path
import prospective_four_arm_v1 as p
def main():
 if p.PLAN.exists():raise FileExistsError(p.PLAN)
 gate=p.read(p.ROOT/'analysis/prospective_v4_qualification_20261014.json');assert gate['stage_qualified']
 items=[]
 for tid in gate['technical_eligible_ids']:
  base=Path('results/prospective_actor_v4_29570452')/tid/'rollout'
  view=base/'monitor_view.json';context=base/'raw/actor_context.json'
  items.append({'trace_id':tid,'view_path':str(view),'actor_context_path':str(context),
   'view_digest':p.digest(p.read(p.ROOT/view)),'actor_context_digest':p.digest(p.read(p.ROOT/context))})
 old=p.read(p.ROOT/'configs/paired_v3_plan.json');actor=p.read(p.ROOT/'configs/prospective_actor_v4.json')
 sources=set()
 for module in tuple(sys.modules.values()):
  f=getattr(module,'__file__',None)
  if f:
   path=Path(f).resolve()
   if path.is_relative_to(p.ROOT/'scripts') and path.suffix=='.py':sources.add(str(path.relative_to(p.ROOT)))
 sources.update(p.read(p.ROOT/'analysis/prospective_v4_archive_manifest_20261014.json'))
 sources.update(['configs/paired_v3_plan.json','configs/prospective_actor_v4.json',
  'analysis/prospective_v4_archive_manifest_20261014.json','analysis/prospective_v4_reference_review_20261014.json','analysis/prospective_v4_qualification_20261014.json','analysis/prospective_v4_integrity_20261014.json',
  'scripts/review_prospective_v4_20261014.py','scripts/prospective_four_arm_v1.sbatch','scripts/submit_prospective_four_arm_v1.py','scripts/freeze_prospective_four_arm_v1.py',
  'tests/test_prospective_four_arm_v1.py','docs/prospective_four_arm_execution_2026-10-14.md',
  'tools/ollama_tokenizer/provenance.json','tools/ollama_tokenizer/bin/tokenizer-linux-amd64',p.read(p.ROOT/'tools/ollama_tokenizer/provenance.json')['vocabulary']])
 plan={'protocol':'prospective_four_arm_v1','frozen_at':datetime.datetime.now().astimezone().isoformat(),'split':'development','items':items,
  'qualification_path':'analysis/prospective_v4_qualification_20261014.json','max_calls':54,'gpu_seconds':2700,'runner_deadline_seconds':2500,'per_call_seconds':150,
  'models':{'qwen3:32b':{'digest':old['models']['qwen3:32b']['digest'],'template_sha256':old['template_sha256']},'gpt-oss:20b':{'digest':actor['actor_digest'],'template_sha256':actor['actor_template_sha256']}},
  'api_reported_version':'0.0.0','actor_context':131072,'actor_think':'low','actor_seed':42,'actor_temperature':0.6,'answer_output_tokens':1024,
  'monitor_context':32768,'review_output_tokens':4096,'question_output_tokens':256,'judge_output_tokens':2048,'extra_review_output_tokens':256,
  'automatic_retries':0,'training_runs':0,'human_gold':False,'source_hashes':{n:p.sha(p.ROOT/n) for n in sorted(sources)}}
 p.verify(plan);p.create(p.PLAN,plan)
 print({'plan_sha256':p.sha(p.PLAN),'sources':len(sources),'items':len(items)})
if __name__=='__main__':main()
