"""Pre-output frozen core counts for all 36 planned outputs; semantic audit follows."""
from collections import defaultdict
import json
from monitor_interface_v3 import parse_response
from score_sft_three_arm_v2 import core_metrics
import monitor_repair_diagnostic_runtime_v1 as run


def main():
    run.verify();refs=run.old.rows(run.DATA/'references.jsonl');records=[]
    for arm in run.ARMS:
        for ref in refs:
            meta=ref['metadata'];eid=meta['example_id'];p=run.OUT/arm/(eid+'_response.json')
            pred=None;error='missing';wrapped=False;consistent=False;raw=None
            if p.exists():
                raw=run.old.read(p)
                try:
                    parsed=parse_response(raw['output']);pred=parsed['prediction'];wrapped=parsed['outer_fence_removed'];consistent=parsed['core_internally_consistent'];error=None
                except (ValueError,TypeError) as e:error=str(e)
            records.append({'arm':arm,'example_id':eid,'metadata':meta,'reference':ref['reference'],'prediction':pred,
                'error':error,'outer_fence_removed':wrapped,'core_internally_consistent':consistent,
                'response_sha256':run.old.sha(p) if p.exists() else None,'usage':{k:raw[k] for k in ['input_tokens','output_tokens','seconds','finished_with_eos']} if raw else None})
    groups=defaultdict(list)
    for r in records:groups[r['arm'],r['metadata']['split'],r['metadata']['domain']].append(r)
    metrics=[{'arm':k[0],'split':k[1],'domain':k[2],**core_metrics(rr),'internally_consistent':sum(r['core_internally_consistent'] for r in rr),'wrapped':sum(r['outer_fence_removed'] for r in rr)} for k,rr in groups.items()]
    result={'status':'core_complete_all36_semantic_pending','metrics':metrics,'records':records,'plan_sha256':run.old.sha(run.PLAN),'tiny_diagnostic_not_population_estimate':True}
    run.old.save(run.ROOT/'analysis/monitor_repair_diagnostic_v1_core_results.json',result)
    print(json.dumps(metrics,indent=2))


if __name__=='__main__':main()
