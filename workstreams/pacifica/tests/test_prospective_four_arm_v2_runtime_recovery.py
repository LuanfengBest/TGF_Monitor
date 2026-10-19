import sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import prospective_four_arm_v2_runtime_recovery as r

class RecoveryTests(unittest.TestCase):
    def test_only_time_fields_change_and_source_is_unchanged(self):
        original=r.base.read(r.base.PLAN);before=r.base.digest(original);new=r.runtime_plan(original)
        self.assertEqual({k for k in new if new[k]!=original[k]},set(r.POLICY['changed_fields']))
        self.assertEqual(r.base.digest(original),before)
        self.assertEqual(new['items'],original['items'])
        self.assertEqual(new['source_hashes'],original['source_hashes'])
    def test_total_budget_covers_failure(self):
        original=r.base.read(r.base.PLAN)
        self.assertLessEqual(r.POLICY['failed_gpu_seconds']+r.POLICY['new_gpu_seconds'],original['gpu_seconds'])
        self.assertLessEqual(r.POLICY['failed_calls']+r.POLICY['new_call_cap'],original['max_calls'])
    def test_no_decision_cannot_launch(self):
        with patch.object(r,'DECISION',Path('/nonexistent/tgf_human_decision.json')):
            with self.assertRaises(FileNotFoundError):r.approved()
    def test_frozen_inputs_and_failed_receipts_match(self):
        self.assertEqual(len(r.verify()['items']),5)

if __name__=='__main__':unittest.main()
