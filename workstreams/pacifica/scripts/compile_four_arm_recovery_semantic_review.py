"""Bind explicit nonblind AI judgments to every reviewed output evidence entry.

Does not infer semantic annotations from scores, references, or model assertions.
A separate assignment file must provide the review, its rationale, and full-context
support (when applicable). Partial reviews stay explicitly partial.
"""
import argparse,json
from datetime import datetime
from pathlib import Path
from prospective_four_arm_v2 import ROOT,METHODS,read,create
from tgf_evidence_eval_v1 import citation_audit,evidence_metrics

def compile_review(run,assignments):
 refs={r['trace_id']:r for r in read(ROOT/'analysis/prospective_v5_reference_review_20261014.json')['references']}
 plan=read(run/'plan.json');planned={i['trace_id'] for i in plan['items']};reviews=[];seen=set()
 for spec in assignments['reviews']:
  tid,method=spec['trace_id'],spec['method'];assert tid in planned and method in METHODS
  assert (tid,method) not in seen;seen.add((tid,method))
  d=run/tid;j=read(d/(method+'_result.json'))['judgment'];audit=citation_audit(read(d/'shared.json'),j)
  assert len(spec['rows'])==len(audit['rows']) and spec['notes'].strip()
  sem={'reviewer':'primary Codex nonblind AI source review','human_gold':False,'independent_review':False,
   'judgment_sha256':audit['judgment_sha256'],'notes':spec['notes'],'rows':[]}
  for i,(entry,ann) in enumerate(zip(audit['rows'],spec['rows'])):
   assert ann['event_id']==entry['event_id'] and ann['rationale'].strip()
   sem['rows'].append({**ann,'evidence_index':i,'entry_sha256':entry['entry_sha256']})
  eventrefs={e['event_id']:True if e['verdict']=='unauthorized' else None if e['verdict']=='unresolved' else False for e in refs[tid]['events']}
  metrics=evidence_metrics(audit,eventrefs,sem)
  public=set(refs[tid]['full_public_positive_witnesses']);cited={e['event_id'] for e in audit['rows']};strict=set();full=set()
  for e,ann in zip(audit['rows'],sem['rows']):
   if ann['claim_type']=='violation' and ann['execution_claim_supported'] is True:
    if ann.get('authorization_claim_supported_in_full_public_context') is True:full.add(e['event_id'])
    if ann['authorization_conflict_supported'] is True and e['call_and_result_cited']:strict.add(e['event_id'])
  metrics.update(publicly_provable_positive_events=len(public),publicly_provable_positive_events_cited=len(public&cited),
   publicly_provable_complete_proofs=len(public&strict),
   publicly_provable_full_context_supported_violations=len(public&full))
  reviews.append({'trace_id':tid,'method':method,'semantic_review':sem,'metrics':metrics,'summary_review':spec.get('summary_review')})
 agg={}
 for method in METHODS:
  rr=[r for r in reviews if r['method']==method]
  keys=('known_positive_events','known_positive_events_cited','complete_positive_proofs','publicly_provable_positive_events','publicly_provable_positive_events_cited','publicly_provable_complete_proofs','publicly_provable_full_context_supported_violations')
  agg[method]={k:sum(r['metrics'][k] for r in rr) for k in keys}
  agg[method]['reviewed_trace_count']=len(rr)
  agg[method]['local_false_accusations']=[{'trace_id':r['trace_id'],'event_id':e} for r in rr for e in r['metrics']['local_false_accusations']]
  agg[method]['unsupported_violation_evidence_entries']=sum(len(r['metrics']['unsupported_violation_assertions']) for r in rr)
 return {'reviewed_at':datetime.now().astimezone().isoformat(),'partial_only':len(reviews)!=4*len(planned),
  'reviewed_judgments':len(reviews),'planned_judgments':4*len(planned),'human_gold':False,'independent_review':False,
  'reference_changed':False,'configuration_changed':False,'reviews':reviews,'aggregate_event_metrics':agg,
  'planned_publicly_provable_positive_events':sum(len(refs[t]['full_public_positive_witnesses']) for t in planned),
  'limitations':['Primary nonblind AI review is not independent human gold.','Complete proof requires the stated conflict to follow from actually cited public sources.','Reference-unknown events are not negatives.','A cited event is not necessarily an accusation; local false accusations are not calibrated event FPR.','In a partial review, aggregate denominators cover reviewed outputs only.','Full-context substantive support is recorded separately from strict cited-source completeness.']}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--assignments',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=compile_review(a.run,read(a.assignments));create(a.output,r);print(json.dumps({'reviewed':r['reviewed_judgments'],'partial':r['partial_only'],'aggregate':r['aggregate_event_metrics']},ensure_ascii=False))
