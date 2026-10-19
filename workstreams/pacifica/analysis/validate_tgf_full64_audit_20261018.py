"""Read-only actual-artifact acceptance; no model calls, source writes or imports."""
from pathlib import Path
import json,hashlib,collections
R=Path(__file__).resolve().parents[1];D=R/'analysis/tgf_full48_authorization_20261018'
def j(p):return json.loads(p.read_text())
def ls(p):return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
def h(p):return hashlib.sha256(p.read_bytes()).hexdigest()
a=j(D/'full_AI_authorization_review.json');events=ls(D/'event_authorization_review.jsonl');src=ls(D/'events_with_execution_status.jsonl');idx=ls(R/'analysis/tgf_full_handoff_20261018/raw_record_index.jsonl');checks=j(D/'state_consistency_checks.json')
assert len(a['traces'])==len(idx)==len(checks)==64
assert {t['id'] for t in a['traces']}=={x['id'] for x in idx}=={x['id'] for x in checks}
assert len(events)==3817 and {e['event_key'] for e in events}=={e['event_key'] for e in src}
assert all(not t['human_gold'] and not t['independent_review'] and t['all_structured_events_reviewed'] for t in a['traces'])
assert a['contract_sha256']==h(R/'docs/tgf_full48_authorization_review_contract_2026-10-18.md')
for x in idx:assert h(R/x['source_file'])==x['source_sha256'],x['id']
by=collections.defaultdict(list)
for e in events:by[e['trace_id']].append(e)
for t in a['traces']:
 es=by[t['id']];assert len(es)==t['event_count']
 assert t['label']==('P' if any(e['authorization']=='violation' for e in es) else 'unknown' if any(e['authorization']=='unknown' for e in es) else 'N')
 assert t['public_provable_positive']==any(e['public_provable_violation'] for e in es if e['authorization']=='violation')
 assert all(e['execution']=='executed' for e in es if e['authorization'] in ['violation','unknown'])
 assert not(t['strict_candidate'] and (not t['technical_end_gate'] or t['label']=='unknown'))
 if t['refusal_no_actions']:assert len(es)==0 and not t['hard_negative_observed']
for x in checks:
 assert all(v is True or isinstance(v,int) and v>=0 for v in x['checks'].values())
assert sum(t['unique_conversation_representative'] for t in a['traces'])==52
assert sum(t['strict_candidate'] and t['hard_negative_observed'] for t in a['traces'])==2
assert not a['ready_for_confirmatory_comparison'] and not a['ready_for_training']
assert len({e['trace_id'] for e in events})==48
print(json.dumps({'status':'passed','source_files_verified':64,'records':64,'active_records':48,'events':3817,'unique_conversations':52,'strict_hardN_candidates':2,'human_gold':False,'independent_review':False,'ready_for_confirmatory_comparison':False,'labels':dict(collections.Counter(t['label'] for t in a['traces']))},ensure_ascii=False))
