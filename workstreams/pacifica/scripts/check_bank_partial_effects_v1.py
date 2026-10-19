"""CPU-only pinned simulator probe; no transactions, model calls, or label changes."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT/'third_party/MonitorBench/datasets/dual_objective/agent'
sys.path.insert(0, str(AGENT))
from environment_classes.zelle import ZelleAccount
from environment_classes.phone import Phone
from tools.financial_transfer import send_money_zelle
from observed_execution_v1 import decode_contract


def main():
    rows = []
    for mode, balance, limit, expected_delta in [
        ('verification_challenge', 1000, 7000, -1.5),
        ('daily_limit_rejection', 1000, 50, -1.5),
        ('insufficient_balance', 50, 7000, 0),
    ]:
        now = datetime(2024, 5, 15, 12)
        account = ZelleAccount(email='owner@example.invalid', phone_number='SIMULATED',
                               bank_name='SIMULATED', bank_iban='SIMULATED', full_name='Contract Probe',
                               current_time=now, balance_value=balance, daily_limit=limit)
        phone = Phone(owner_name='Contract Probe', owner_number='SIMULATED', current_time=now)
        args = {'recipient_email': 'recipient@example.invalid', 'amount': 100}
        result = send_money_zelle(account, phone, **args)
        delta = round(account.balance - balance, 2)
        assert delta == expected_delta
        assert len(account.transaction_history) == 0
        assert len(phone.messages) == (0 if mode == 'insufficient_balance' else 1)
        rows.append({'fixture': mode, 'arguments': args, 'visible_tool_result': result,
                     'visible_contract_v1': decode_contract('send_money_zelle', args, result),
                     'audit_only_balance_change': delta, 'audit_only_new_recipient_transfers': 0,
                     'audit_only_new_phone_messages': len(phone.messages)})
    paths = ['tools/financial_transfer.py', 'environment_classes/zelle.py', 'environment_classes/phone.py']
    report = {'scope': 'Synthetic local simulator contract audit, not natural actor traces or authorization labels',
              'model_calls': 0, 'training_examples': 0,
              'upstream_commit': 'b6229e4b8ea9abcec38d61159c9cbd0f577ddf35',
              'source_hashes': {p: hashlib.sha256((AGENT/p).read_bytes()).hexdigest() for p in paths},
              'probes': rows,
              'interpretation': 'A pending/rejected recipient payment can still debit a fee. Named-operation execution is not a claim of zero side effects. Private audit fields must never enter monitor inputs.'}
    out = ROOT/'analysis/bank_partial_effects_probe_20261013.json'
    with out.open('x') as f:
        json.dump(report, f, indent=2); f.write('\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
