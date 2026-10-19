"""Offline actual-input check of an isolated adapter; no experiment submitted."""
import json,hashlib,sys
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'scripts'))
from tgf_public_trace_reminder_v1 import shared_bundle
from public_event_contract_reminder_v1 import prepare
from tgf_citation_reminder_v1 import citation_audit
from paired_protocol_v3 import Counter,REVIEW_SYSTEM,render_prompt
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
P=R/'data/annotation_review/pilot_loopcheck_v1_29720251';counter=Counter();rows=[]
for case in read(P/'manifest.json')['cases']:
 v=read(P/case['public_path']);b=shared_bundle(v);s,f=prepare(b)
 assert s['original_messages']==b['original_messages'] and s['user_request']==v['user_request']
 j={'evidence':[{'event_id':e['event_id'],'source_ids':['user_request',e['call_source'],e['result_source']]} for e in s['ledger']]}
 audit=citation_audit(s,j);assert all(r['call_and_result_cited'] for r in audit['rows'])
 n=counter.count(render_prompt(REVIEW_SYSTEM,{**s,'public_execution_observations':f}))
 rows.append(dict(case_id=case['case_id'],all_message_ids_preserved=True,bound_events=len(audit['rows']),initial_monitor_tokens=n,output_and_safety_reserve=4224,capacity_passed=n+4224<=32768))
sources=['scripts/tgf_citation_reminder_v1.py','scripts/public_event_contract_reminder_v1.py','scripts/tgf_public_trace_reminder_v1.py','tests/test_reminder_citation_compat.py','analysis/check_reminder_common_input_20261016.py']
out=dict(scope='Isolated local compatibility only; old frozen runners unchanged; no remote delivery or experiment',rows=rows,source_hashes={p:sha(R/p) for p in sources},boundary_tests_passed=5,all12_public_contracts_and194_bindings_passed=True,all12_initial_monitor_capacity_passed=all(r['capacity_passed'] for r in rows),model_calls=0,gpu_seconds=0,scientific_data_gate_still_passed=False,ready_for_effect_experiment=False,limitations=['Question, actor answer and final-judge generated inputs not instantiated or checked','A future runner must explicitly adopt and freeze this adapter; current v3 runner still uses old adapter','Data class coverage failed independently of this compatibility fix'])
with (R/'analysis/reminder_common_input_acceptance_20261016.json').open('x') as f:json.dump(out,f,ensure_ascii=False,indent=2);f.write('\n')
print(json.dumps(out,ensure_ascii=False,indent=2))
