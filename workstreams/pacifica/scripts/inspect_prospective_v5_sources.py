"""Persist audit support and print event evidence for nonblind review; never construct monitor inputs."""
import json
from pathlib import Path
from audit_bank_alias_v3 import audit_rollout
from audit_bank_v2 import changes
from tgf_public_trace_v1 import shared_bundle

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'results/prospective_actor_v5_29585413'
def read(p):return json.loads(Path(p).read_text())
def main():
 spec=read(ROOT/'configs/bank_authorization_v2.json')
 for case in sorted(BASE.glob('prospective5_*')):
  run=case/'rollout'
  if not (run/'summary.json').exists():continue
  print('\nCASE',case.name,json.dumps(read(run/'summary.json')))
  view=read(run/'monitor_view.json');print('USER',view['user_request'])
  try:
   bundle=shared_bundle(view);ledger={e['event_id']:e for e in bundle['ledger']}
  except ValueError as exc:
   # Quarantined traces remain unmodified. Oracle events are diagnosis only.
   print('QUARANTINED_PUBLIC_VIEW',str(exc));ledger={}
  audit=audit_rollout(run,spec) if 'bank_transfer' in case.name else None
  audit_rows={e['event_id']:e for e in audit['events']} if audit else {}
  if audit:
   path=ROOT/'analysis'/(case.name+'_bank_audit_20261014.json')
   if path.exists():
    assert read(path)==audit, 'Existing audit differs; preserve and investigate'
   else:
    with path.open('x') as f:json.dump(audit,f,ensure_ascii=False,indent=2)
  for e in read(run/'oracle/events.json'):
   eid=e['event_id'];before=run/f'oracle/{eid}_before.json';after=run/f'oracle/{eid}_after.json'
   delta=changes(read(before),read(after)) if before.exists() and after.exists() else None
   row=audit_rows.get(eid,{})
   print(json.dumps({'event':eid,'tool':e['tool'],'arguments':e['arguments'],'returned':e['status'],'result':e['result'],'sources':[ledger[eid]['call_source'],ledger[eid]['result_source']] if eid in ledger else None,
      'state_changes':delta,'programmatic_verdict':row.get('verdict'),'reasons':row.get('reasons')},ensure_ascii=False))
if __name__=='__main__':main()
