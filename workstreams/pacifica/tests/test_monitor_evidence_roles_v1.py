import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from monitor_evidence_roles_v1 import catalog, validate_claims


def bundle(iid):
    return json.loads((ROOT/f'data/diagnostics/monitor_selection_v1/inputs/{iid}.json').read_text())


def check(b, role, sid):
    return validate_claims(b, [{'role': role, 'source_ids': [sid]}])


class RoleTests(unittest.TestCase):
    def test_recipient_comparison_cannot_create_permission(self):
        b = bundle('c08_short')
        self.assertTrue(check(b, 'action_arguments', 'm0000.metadata')['role_contract_valid'])
        self.assertFalse(check(b, 'permission', 'm0000.metadata')['role_contract_valid'])
        r = check(b, 'action_arguments', 'm0000.metadata')
        original = next(s['text'] for s in b['sources'] if s['source_id'] == 'm0000.metadata')
        self.assertEqual(r['evidence'][0]['quote'], original)
        self.assertFalse(r['authorization_semantics_verified'])

    def test_target_success_not_prior_balance_evidence(self):
        b = bundle('c03_full')
        self.assertTrue(check(b, 'execution_result', 'm0017.content.000')['role_contract_valid'])
        self.assertFalse(check(b, 'precondition', 'm0017.content.000')['role_contract_valid'])
        self.assertTrue(check(b, 'precondition', 'm0007.content.000')['role_contract_valid'])
        self.assertTrue(check(b, 'precondition', 'm0015.content.000')['role_contract_valid'])
        self.assertFalse(check(b, 'precondition', 'm0019.content.000')['role_contract_valid'])

    def test_actor_claim_and_missing_source_never_qualify(self):
        b = bundle('c03_short')
        for role in ['permission', 'precondition', 'amount_basis', 'action_arguments', 'execution_result']:
            self.assertFalse(check(b, role, 'm0016.thinking.000')['role_contract_valid'])
            self.assertFalse(check(b, role, 'missing')['role_contract_valid'])
        with self.assertRaises(ValueError):
            validate_claims(b, [{'role': 'permission', 'source_ids': ['user_request', 'user_request']}])

    def test_arithmetic_basis_is_not_observed_payment(self):
        b = bundle('c01_full')
        self.assertTrue(check(b, 'amount_basis', 'm0001.content.016')['role_contract_valid'])
        records = catalog(b)
        target = next(s for s, v in records.items() if 'action_arguments' in v['eligible_roles'])
        self.assertFalse(check(b, 'amount_basis', target)['role_contract_valid'])
        self.assertFalse(check(b, 'amount_basis', 'm0001.content.016')['arithmetic_inputs_grounded'])
        # The frozen short excerpt omits this message's metadata. Do not
        # silently borrow provenance from the full view to make it pass.
        short = bundle('c01_short')
        self.assertFalse(check(short, 'amount_basis', 'm0001.content.016')['role_contract_valid'])


if __name__ == '__main__':
    unittest.main()
