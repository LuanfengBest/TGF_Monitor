"""Safety gates for the bounded CPU audit, without generating experiment cases."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import prepare_monitor_v2_audit_v1 as audit

class AuditFreezeTests(unittest.TestCase):
    def fixture(self, root):
        source = root/'pinned.txt';source.write_text('frozen')
        plan = {'specs': [list(x) for x in audit.SPECS], 'max_mutation_events': 12,
                'model_calls': 0, 'actor_rollouts': 0, 'training_approved': False,
                'cpu_audit_approved': True, 'frozen_at': 'before-generation',
                'file_hashes': {'pinned.txt': audit.sha(source)}, 'families': {
                    'bank_cumulative_spend_pool': {'family_id': 'pool', 'split': 'train'},
                    'bank_batch_quorum': {'family_id': 'quorum', 'split': 'validation'},
                    'airline_duplicate_retention': {'family_id': 'retention', 'split': 'validation'}}}
        p = root/'plan.json';p.write_text(json.dumps(plan))
        return p, plan, source

    def test_changed_frozen_source_prevents_any_generation(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);p,plan,source=self.fixture(root)
            with patch.object(audit,'ROOT',root),patch.object(audit,'PLAN',p):
                self.assertTrue(audit.verify_plan())
                source.write_text('modified')
                with self.assertRaisesRegex(ValueError,'Frozen file changed'):
                    audit.verify_plan()

    def test_cross_split_family_or_expanded_model_permission_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);p,plan,_=self.fixture(root)
            with patch.object(audit,'ROOT',root),patch.object(audit,'PLAN',p):
                plan['families']['bank_batch_quorum']['family_id']='pool';p.write_text(json.dumps(plan))
                with self.assertRaisesRegex(ValueError,'Same family'):
                    audit.verify_plan()
                plan['families']['bank_batch_quorum']['family_id']='quorum'
                plan['model_calls']=1;p.write_text(json.dumps(plan))
                with self.assertRaisesRegex(ValueError,'cannot authorize'):
                    audit.verify_plan()

    def test_existing_partial_run_is_not_overwritten_or_retried(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);p,plan,_=self.fixture(root);out=root/'out';out.mkdir();marker=out/'reservation.json';marker.write_text('keep')
            with patch.object(audit,'ROOT',root),patch.object(audit,'PLAN',p),patch.object(audit,'OUT',out),patch.object(audit,'PRIVATE',root/'private.json'),patch.object(audit,'execute_case') as execute:
                with self.assertRaisesRegex(ValueError,'no automatic retry'):
                    audit.generate()
                execute.assert_not_called()
            self.assertEqual(marker.read_text(),'keep')

if __name__ == '__main__':unittest.main()
