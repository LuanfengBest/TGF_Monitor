"""Freeze all six single-field interventions before any new model outputs."""
import datetime,sys
from pathlib import Path
import initial_review_ablation_v1 as p
def main():
 if p.PLAN.exists():raise FileExistsError(p.PLAN)
 old=p.read(p.ROOT/'configs/prospective_four_arm_v1.json');items=[];sources=set(old['source_hashes'])
 sources.update(p.read(p.ROOT/'analysis/prospective_four_arm_archive_manifest_20261014.json')['file_hashes'])
 counter=p.prior.Counter()
 for olditem in old['items']:
  tid=olditem['trace_id'];base=Path('results/prospective_four_arm_v1_29571002')/tid
  original=base/'tgf_judge_input.json';new=Path('data/initial_review_ablation_v1')/tid/'judge_input.json'
  original_input=p.read(p.ROOT/original);derived=p.remove_initial_review(original_input);p.create(p.ROOT/new,derived)
  item={'trace_id':tid,'original_input_path':str(original),'input_path':str(new),'shared_path':str(base/'shared.json'),
   'original_result_path':str(base/'tgf_result.json'),'original_input_digest':p.digest(original_input),'input_digest':p.digest(derived),
   'expected_prompt_tokens':counter.check(p.prior.render_prompt(p.prior.JUDGE_SYSTEM,derived),2048)}
  items.append(item);sources.add(str(new))
 for module in tuple(sys.modules.values()):
  f=getattr(module,'__file__',None)
  if f:
   path=Path(f).resolve()
   if path.is_relative_to(p.ROOT/'scripts') and path.suffix=='.py':sources.add(str(path.relative_to(p.ROOT)))
 sources.update(['configs/prospective_four_arm_v1.json','configs/tgf_evidence_eval_v1.json','analysis/prospective_four_arm_archive_manifest_20261014.json',
  'analysis/prospective_four_arm_full_semantic_review_20261014.json','scripts/initial_review_ablation_v1.sbatch','scripts/submit_initial_review_ablation_v1.py',
  'scripts/freeze_initial_review_ablation_v1.py','tests/test_initial_review_ablation_v1.py','docs/initial_review_ablation_protocol_2026-10-14.md'])
 plan={'protocol':'initial_review_ablation_v1','frozen_at':datetime.datetime.now().astimezone().isoformat(),'split':'development','items':items,
  'intervention':'remove only top-level initial_review; all other fields identical','primary_diagnostic':'prospective4_003_bank_transfer_2_ordinary/e0006 execution acknowledgement',
  'max_calls':6,'gpu_seconds':900,'runner_deadline_seconds':800,'per_call_seconds':150,'judge_output_tokens':2048,'automatic_retries':0,
  'monitor_context':32768,'models':{'qwen3:32b':old['models']['qwen3:32b']},'api_reported_version':old['api_reported_version'],
  'human_gold':False,'training_runs':0,'source_hashes':{n:p.sha(p.ROOT/n) for n in sorted(sources)}}
 p.verify(plan);p.create(p.PLAN,plan)
 print({'sources':len(sources),'plan_sha256':p.sha(p.PLAN),'input_tokens':[i['expected_prompt_tokens'] for i in items]})
if __name__=='__main__':main()
