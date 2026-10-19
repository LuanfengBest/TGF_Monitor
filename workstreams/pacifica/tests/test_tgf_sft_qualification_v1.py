from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import tgf_sft_qualification_v1 as q


class QualificationPlanTests(unittest.TestCase):
    def test_population_budgets_and_family_isolation(self):
        specs = q.specs()
        self.assertEqual(len(specs), 18)
        self.assertEqual(sum(s['expected_target_events'] for s in specs), 20)
        self.assertEqual({s['split'] for s in specs}, {'train'})
        self.assertEqual(len({s['case_id'] for s in specs}), 18)
        self.assertEqual(len({s['family_id'] for s in specs}), 2)

    def test_deterministic_derivation_and_no_source_mutation(self):
        before = {str(p): q.sha(p) for p in [q.POOL_TASK, q.TRAVEL_TASK, q.TRAVEL_FIXTURE]}
        for spec in q.specs():
            self.assertEqual(q.build_fixture(spec), q.build_fixture(spec))
        self.assertEqual(before, {p: q.sha(p) for p in before})

    def test_bank_fixture_and_boundary_design(self):
        for spec in q.specs()[:8]:
            view, state, calls = q.build_fixture(spec)
            q.BankMechanismEnvironment(**deepcopy(state))
            initial = state['bank_account']['scheduled_transactions'][0]['amount']
            amount = calls[3][1]['amount']
            import re
            cap = int(re.search(r'exceed USD (\d+)', view['user_request'])[1])
            if spec['mode'] == 'exact_cap': self.assertEqual(initial + amount, cap)
            if spec['mode'] == 'over_cap': self.assertGreater(initial + amount, cap)
            if spec['mode'] == 'refusal_then_next':
                self.assertFalse(calls[3][1]['override'])
                self.assertLessEqual(initial + amount, cap)
                self.assertLessEqual(initial + calls[4][1]['amount'], cap)

    def test_travel_cases_bind_new_identity_and_original_schema(self):
        for spec in q.specs()[8:]:
            view, state, calls = q.build_fixture(spec)
            q.ProjectionEnvironment(**deepcopy(state))
            rows = json.loads(state['cloud_drive']['initial_files'][0]['content'])
            self.assertIn(rows[0]['itinerary_id'], view['user_request'])
            self.assertNotIn('TRIP-P', view['user_request'])
            self.assertEqual(calls[0], ('get_file_by_id', {'file_id': '1'}))
            self.assertEqual(calls[1][0], 'send_email')
            self.assertEqual(set(view), {'user_request', 'policy'})

    def test_unsupported_domain_rejected(self):
        spec = deepcopy(q.specs()[0]); spec['domain'] = 'validation'
        with self.assertRaises(ValueError): q.build_fixture(spec)


if __name__ == '__main__': unittest.main()
