"""Boundary checks: original candidates, honest prior failure, duplicate prevention."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import pilot_collection_continuation_b02 as c
import pilot_collection_recovery_v1 as r
class ContinuationTests(unittest.TestCase):
    def setUp(self):
        self.parent=c.actor.read(c.original.PLAN)
        self.prior=c.actor.read(c.ROOT/'analysis/pilot_collection_b01_merged_AI_coverage_20261015.json')
    def test_original_batch_and_same_actor_and_guard(self):
        cases=c.original.attempts_for(self.parent,2)
        self.assertEqual([a['seed'] for a in cases],list(range(16031,16061)))
        self.assertIs(c.actor.rollout,r.actor.rollout)
        self.assertIs(c.verified_guard_exclusion,r.verified_guard_exclusion)
    def test_complete_available_review_does_not_launder_failures(self):
        c.validate_prior(self.prior,self.parent)
        for key,val in [('technical_batch_all_attempts_successful',True),('ready_for_monitor_comparison',True),('full_planned_available_review_complete',False),('runtime_guard_excluded',0),('events_reviewed',454)]:
            p=copy.deepcopy(self.prior);p[key]=val
            with self.assertRaises(ValueError):c.validate_prior(p,self.parent)
    def test_missing_or_reordered_case_rejected(self):
        p=copy.deepcopy(self.prior);p['rows'].reverse()
        with self.assertRaises(ValueError):c.validate_prior(p,self.parent)
        p=copy.deepcopy(self.prior);p['rows'].pop()
        with self.assertRaises(ValueError):c.validate_prior(p,self.parent)
    def test_either_old_or_new_reservation_blocks_submission(self):
        for old in [False,True]:
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)
                def artifact(s):return root/('new_'+s+'.json')
                def batch_path(b,s):return root/('old_'+s+'.json')
                (batch_path(2,'reservation') if old else artifact('submission')).write_text('{}')
                with patch.object(c,'verify'),patch.object(c,'artifact',side_effect=artifact),patch.object(c.original,'batch_path',side_effect=batch_path),patch.object(c.subprocess,'run') as process:
                    with self.assertRaises(ValueError):c.submit()
                    process.assert_not_called()
    def test_ambiguous_submission_retains_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            def artifact(s):return root/('new_'+s+'.json')
            def batch_path(b,s):return root/('old_'+s+'.json')
            artifact('preflight').write_text(json.dumps({'status':'passed','plan_sha256':'same'}))
            with patch.object(c,'verify'),patch.object(c,'artifact',side_effect=artifact),patch.object(c.original,'batch_path',side_effect=batch_path),patch.object(c.actor,'sha',return_value='same'),patch.object(c.subprocess,'check_output',return_value=''),patch.object(c.subprocess,'run',side_effect=TimeoutError('timeout')):
                with self.assertRaises(TimeoutError):c.submit()
            self.assertTrue(batch_path(2,'reservation').exists())
            self.assertEqual(json.loads(artifact('submission').read_text())['status'],'unknown_outcome_do_not_retry')
if __name__=='__main__':unittest.main()
