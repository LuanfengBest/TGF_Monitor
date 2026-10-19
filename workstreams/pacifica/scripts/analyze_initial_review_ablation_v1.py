"""Reconstruct intervention identity, complete plan denominators, scores and costs."""
import argparse,json,hashlib
from pathlib import Path
import jsonschema
import initial_review_ablation_v1 as p
from tgf_evidence_eval_v1 import citation_audit,evidence_metrics,paired_score_metrics
def analyze(run):
 run=run.resolve();plan=p.verify(p.read(p.PLAN));assert p.read(run/'plan.json')==plan
 meta=p.read(run/'monitor_metadata.json');model='qwen3:32b'
 assert meta['version']['version']==plan['api_reported_version']
 assert {m['name']:m['digest'] for m in meta['tags']['models']}[model]==plan['models'][model]['digest']
 assert hashlib.sha256(meta['show']['template'].encode()).hexdigest()==plan['models'][model]['template_sha256']
 calls=[];counter=p.prior.Counter()
 for file in sorted((run/'calls').glob('*_request.json')):
  request=p.read(file);identity=p.read(Path(str(file).replace('_request.json','_identity.json')))
  tid,kind=identity['name'].split('/');assert kind=='judge_without_initial_review'
  item=next(i for i in plan['items'] if i['trace_id']==tid);bundle,shared=p.verify_item(item)
  prompt=p.prior.render_prompt(p.prior.JUDGE_SYSTEM,bundle);n=counter.check(prompt,2048)
  expected={'model':model,'prompt':prompt,'raw':True,'stream':False,'keep_alive':'15m','options':{'num_ctx':32768,'num_predict':2048,'seed':42,'temperature':0},'format':p.prior.judge_schema(shared)}
  assert request==expected and identity['endpoint']=='generate' and identity['expected_prompt_tokens']==n==item['expected_prompt_tokens']
  response_path=Path(str(file).replace('_request.json','_response.json'));usage_path=Path(str(file).replace('_request.json','_usage.json'))
  row={'trace_id':tid,'request':str(file.relative_to(p.ROOT)),'has_response':response_path.exists(),'has_usage':usage_path.exists()}
  if response_path.exists():
   response=p.read(response_path);assert response['prompt_eval_count']==n;row['done_reason']=response.get('done_reason')
   result=run/tid/'result.json'
   if result.exists():assert json.loads(response['response'])==p.read(result)['judgment']
  if usage_path.exists():row['usage']=p.read(usage_path)
  calls.append(row)
 summary=p.read(run/'summary.json');assert len(calls)==summary['calls']<=6
 refs={r['trace_id']:r for r in p.read(p.ROOT/'analysis/prospective_v4_reference_review_20261014.json')['references']}
 records=[]
 for item in plan['items']:
  tid=item['trace_id'];bundle,shared=p.verify_item(item)
  paths={'tgf_original':p.ROOT/item['original_result_path'],'without_initial_review':run/tid/'result.json'}
  for method,path in paths.items():
   rec={'trace_id':tid,'method':method,'reference_label':refs[tid]['label'],'response_status':'missing','schema_valid':False}
   if path.exists():
    result=p.read(path);j=result['judgment'];jsonschema.validate(j,p.prior.judge_schema(shared));audit=citation_audit(shared,j)
    erefs={e['event_id']:True if e['verdict']=='unauthorized' else None if e['verdict']=='unresolved' else False for e in refs[tid]['events']}
    rec.update(response_status='completed',schema_valid=True,score=j['unauthorized_action_score'],judgment=j,citations=audit,evidence_metrics=evidence_metrics(audit,erefs))
   records.append(rec)
  copied=run/tid/'judge_input.json'
  if copied.exists():assert p.read(copied)==bundle
 metrics={}
 for family in sorted({r['family'] for r in refs.values()}):
  ids=[i['trace_id'] for i in plan['items'] if refs[i['trace_id']]['family']==family]
  metrics[family]=paired_score_metrics(ids,{t:None if refs[t]['label'] is None else bool(refs[t]['label']) for t in ids},[r for r in records if r['trace_id'] in ids],methods=('tgf_original','without_initial_review'))
 usages=[c['usage'] for c in calls if c['has_usage']]
 costs={'new_monitor_calls':len(calls),'new_actor_calls':0,'calls_with_usage':len(usages),'calls_without_usage':len(calls)-len(usages),'known_input_tokens':sum(u['prompt_eval_count'] for u in usages),'known_output_tokens':sum(u['eval_count'] for u in usages),'api_usd':None,'reused_original_calls_charged_again':False}
 return {'plan_sha256':p.sha(p.PLAN),'source_hashes_verified':len(plan['source_hashes']),'summary':summary,'costs':costs,'calls':calls,'records':records,'metrics_by_family':metrics,'semantic_review':'pending','split':'development','human_gold':False,'primary_diagnostic':'003/e0006','intervention':'only final-judge initial_review omitted; upstream selection/question unchanged','training_runs':0}
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--run',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
 r=analyze(a.run);p.create(a.output,r)
 print(json.dumps({'costs':r['costs'],'scores':[(x['trace_id'],x['method'],x.get('score')) for x in r['records']]}))
