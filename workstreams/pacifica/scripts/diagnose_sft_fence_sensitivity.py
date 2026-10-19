"""Posthoc lossless-wrapper sensitivity. Does not change frozen primary results."""
import copy
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from score_sft_three_arm_v2 import strict_parse, core_metrics, exact, CORE

ROOT = Path(__file__).resolve().parents[1]


def unwrap(text):
    s = text.strip()
    if s.startswith('```json\n') and s.endswith('\n```'):
        return s[8:-4], True
    return text, False


def main():
    primary_path = ROOT / 'analysis/sft_three_arm_v2_core_results.json'
    plan = json.loads((ROOT / 'analysis/sft_fence_diagnostic_plan_20261015.json').read_text())
    assert hashlib.sha256(primary_path.read_bytes()).hexdigest() == plan['frozen_primary_sha256']
    core = json.loads(primary_path.read_text())
    audit = json.loads((ROOT / 'analysis/sft_three_arm_v2_semantic_review_20261015.json').read_text())
    sem = {(r['example_id'],r['arm']): r for r in audit['rows']}
    records = copy.deepcopy(core['records'])
    for r in records:
        p = ROOT / f"results/sft_three_arm_v2/evaluation/{r['arm']}/{r['example_id']}_response.json"
        assert hashlib.sha256(p.read_bytes()).hexdigest() == r['response_sha256']
        raw = json.loads(p.read_text())['output']
        normalized, changed = unwrap(raw)
        r['outer_wrapper_removed'] = changed
        r['primary_prediction_unchanged'] = r['prediction']
        try:
            r['prediction'] = strict_parse(normalized)
            r['error'] = None
        except (ValueError, TypeError) as exc:
            r['prediction'], r['error'] = None, str(exc)
        s = sem[r['example_id'],r['arm']]
        r['diagnostic_substantive_supported_decision'] = bool(r['prediction'] and
            all(exact(r['reference'][k],r['prediction'][k]) for k in CORE) and
            all(s[k] == 'supported' for k in ['factual_claims_supported','execution_reason_supported','authorization_reason_supported']))
    groups = defaultdict(list)
    for r in records:
        m = r['metadata']; groups[r['arm'],m['split'],m['domain'],m['family']].append(r)
    metrics = [{'arm':k[0],'split':k[1],'domain':k[2],'family':k[3],**core_metrics(rr),
        'diagnostic_substantive_supported_decision':sum(r['diagnostic_substantive_supported_decision'] for r in rr)} for k,rr in groups.items()]
    aggregate = []
    for arm in ['base','ordinary_sft','evidence_sft']:
        for split in ['final_test','validation']:
            mm = [m for m in metrics if m['arm']==arm and m['split']==split]
            keys = ['planned','valid_core_json','core_all3_correct','TP','TN','FP','positive_n','negative_n','unknown_n','unknown_retained','known_abstentions','missing_or_parse_failed','diagnostic_substantive_supported_decision']
            aggregate.append({'arm':arm,'split':split,**{k:sum(m[k] for m in mm) for k in keys}})
    for arm in ['ordinary_sft','evidence_sft']:
        assert all(r['prediction'] == r['primary_prediction_unchanged'] for r in records if r['arm']==arm)
    assert sum(r['outer_wrapper_removed'] for r in records) == 36
    assert all(r['prediction'] is not None for r in records if r['arm']=='base')
    assert hashlib.sha256(primary_path.read_bytes()).hexdigest() == plan['frozen_primary_sha256']
    result={'status':'posthoc_diagnostic_complete_not_replacement_for_primary','plan':plan,'new_model_calls':0,'metrics':metrics,'aggregate_counts_not_pooled_G2':aggregate,'records':records,'primary_sha256_unchanged':plan['frozen_primary_sha256']}
    with (ROOT/'analysis/sft_fence_sensitivity_20261015.json').open('x') as f:
        json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps(aggregate,indent=2))


if __name__ == '__main__':
    main()
