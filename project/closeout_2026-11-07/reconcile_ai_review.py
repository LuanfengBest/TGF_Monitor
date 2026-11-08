"""Compare sealed AI labels to frozen references after the review is complete."""
from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal
from collections import Counter
import hashlib
import html
import json
import re

HERE = Path(__file__).resolve().parent
REVIEW = HERE / 'ai_blind_review_2026-11-07'
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
seal = read(REVIEW / 'seal.json')
assert sha(REVIEW / 'anonymous_records.html') == seal['input_sha256']
assert sha(REVIEW / 'review_sealed.json') == seal['output_sha256']
review = read(REVIEW / 'review_sealed.json')
key = {r['review_id']: r['case_id'] for r in read(HERE / 'validation/human_review_key_LOCAL_ONLY.json')}
refs = {r['case_id']: r for r in read(HERE / 'validation/reference_reviews_LOCAL_ONLY.json')}
packet = (REVIEW / 'anonymous_records.html').read_text()
sources = {}
for rid, body in re.findall(r'<section id="(R\d+)">(.*?)</section>', packet, re.S):
    sources[rid] = {html.unescape(b).split(' · ')[0]: html.unescape(p) for b, p in re.findall(r'<div class="source"><b>(.*?)</b><pre>(.*?)</pre></div>', body, re.S)}
assert set(key) == set(sources) == {r['review_id'] for r in review['reviews']} and len(key) == 12
assert review['review_method']['judge_outputs_seen'] is False
assert review['review_method']['author_or_reference_labels_seen'] is False
assert review['review_method']['human_reviewer'] is False
rows, quotes, writes = [], 0, 0
for item in review['reviews']:
    rid = item['review_id']; ref = refs[key[rid]]
    for source in item['decisive_sources']:
        assert source['quote'] in sources[rid][source['source_id']], (rid, source)
        quotes += 1
    checks = ref['public_check']
    assert Decimal(item['total_principal_or_ticket_amount']['amount']) == Decimal(checks['total'])
    assert Decimal(item['applicable_cap']['episode']) == Decimal(checks['cap'])
    assert len(item['execution_audit']) == len(checks['rows'])
    for a,b in zip(item['execution_audit'],checks['rows']):
        assert a['action_source_id'] == b['call_source'] and a['execution_receipt_source_id'] == b['receipt_source']
        assert Decimal(a['amount_usd']) == Decimal(b['amount'])
        assert Decimal(a['gross_episode_cumulative_after_usd']) == Decimal(b['cumulative'])
        assert a['execution_confirmed_in_record'] and a['authorization_in_effect'] and a['identity_matches_authorization']
        writes += 1
    breaches = [r for r in checks['rows'] if Decimal(r['cumulative']) > Decimal(checks['cap'])]
    if breaches:
        assert item['earliest_violating_action']['action_source_id'] == breaches[0]['call_source']
    else:
        assert item['earliest_violating_action'] is None
    expected = 'violation' if ref['reference_violation'] else 'authorized'
    rows.append({'review_id':rid,'case_id':key[rid],'ai_label':item['label'],'author_reference':expected,
                 'agreement':item['label']==expected,'total':checks['total'],'cap':checks['cap'],
                 'source_quotes_checked':len(item['decisive_sources']),'reason':item['reason'],
                 'ambiguities':item['ambiguities']})
result = {'reconciled_at_utc':datetime.now(timezone.utc).isoformat(),'review_sealed_before_reconciliation':True,
          'reviewer_type':'independent-context AI, not human','review_agent':'/root/blind_record_audit',
          'input_sha256':seal['input_sha256'],'sealed_review_sha256':seal['output_sha256'],
          'seal_sha256':sha(REVIEW/'seal.json'),'reference_key_sha256':sha(HERE/'validation/human_review_key_LOCAL_ONLY.json'),
          'reference_reviews_sha256':sha(HERE/'validation/reference_reviews_LOCAL_ONLY.json'),
          'records':12,'agreements':sum(r['agreement'] for r in rows),'label_counts':dict(Counter(r['ai_label'] for r in rows)),
          'exact_source_quotes_verified':quotes,'executed_financial_actions_checked':writes,
          'rows':rows,'reference_labels_changed':False,'experiment_metrics_changed':False,
          'independent_human_review_completed':False,
          'limitations':['Instructional context separation on a shared filesystem, not a hard sandbox.',
                         'One AI reviewer; agreement does not establish independent human gold.',
                         'Only the final 12 constructed records were reviewed, not earlier natural records or Judge rationales.']}
with (REVIEW/'reconciliation.json').open('x') as f:
    json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2))
for r in rows:print(r['review_id'],r['ai_label'],r['reason'])
