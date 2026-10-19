"""CPU-only audit of update semantics; not a cancellation implementation."""
from pathlib import Path
import hashlib
import json
import sys
ROOT=Path(__file__).resolve().parents[1]
AGENT=ROOT/'third_party/MonitorBench/datasets/dual_objective/agent'
sys.path.insert(0,str(AGENT))
from environment_classes.bank_accounts import BankAccount,Transaction
from tools.financial_transfer import update_scheduled_transaction


def main():
    rows=[]
    for args in [{'amount':150},{'amount':0},{'recurring':False}]:
        account=BankAccount(balance=1000,iban='SIMULATED-OWNER',transactions=[],scheduled_transactions=[
            Transaction(id=1,sender='SIMULATED-OWNER',recipient='SIMULATED-VENDOR',amount=100,subject='fixture',date='2026-10-20',recurring=True)])
        before=account.model_dump(mode='json')
        result=update_scheduled_transaction(account,id=1,**args)
        after=account.model_dump(mode='json')
        changed=before!=after
        assert changed==(args=={'amount':150})
        assert len(account.scheduled_transactions)==1
        rows.append({'arguments':{'id':1,**args},'visible_result':result,'audit_only_state_changed':changed,
                     'audit_only_resulting_schedule':after['scheduled_transactions'][0]})
    out=ROOT/'analysis/bank_update_contract_probe_20261013.json'
    with out.open('x') as f:
        json.dump({'scope':'Local pinned simulator mechanics; no actor rollout, authorization label or live transaction',
             'source_sha256':hashlib.sha256((AGENT/'tools/financial_transfer.py').read_bytes()).hexdigest(),
             'model_calls':0,'training_examples':0,'probes':rows,
             'conclusion':'update_scheduled_transaction is not cancellation. Its truthiness checks ignore amount=0 and recurring=False while returning updated. Do not implement revocation/reversal coverage by assuming either argument cancels an existing schedule.'},f,indent=2);f.write('\n')
    print(json.dumps({'probes':len(rows),'changed':[r['audit_only_state_changed'] for r in rows],'output':str(out)}))


if __name__=='__main__':main()
