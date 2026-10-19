"""Print exact final claims and cited public sources for a source-bound AI audit."""
import argparse,json
from pathlib import Path
from tgf_evidence_eval_v1 import citation_audit
p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--trace',required=True);p.add_argument('--sources',action='store_true');a=p.parse_args()
d=a.run/a.trace;shared=json.loads((d/'shared.json').read_text())
for n in ('selected_event.json','questions.json','fixed_b2_reply.json','tgf_reply.json','initial_review.json','b3_extra_review.json'):
 f=d/n
 if f.exists():print(n, f.read_text())
source_ids=set()
for method in ('ledger_only','fixed_b2','tgf','b3'):
 f=d/(method+'_result.json')
 if not f.exists():print(method,'MISSING');continue
 j=json.loads(f.read_text())['judgment'];audit=citation_audit(shared,j)
 print('\nMETHOD',method,'JUDGMENT_SHA',audit['judgment_sha256']);print(json.dumps(j,ensure_ascii=False,indent=2));print(json.dumps(audit['rows'],ensure_ascii=False))
 for e in j['evidence']:source_ids.update(e['source_ids'])
if a.sources:
 for sid in sorted(source_ids):
  print('\nSOURCE',sid,json.dumps(shared[sid] if sid in ('user_request','policy') else shared['original_messages'][sid],ensure_ascii=False,indent=2))
