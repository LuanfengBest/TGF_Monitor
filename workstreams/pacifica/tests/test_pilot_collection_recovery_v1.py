"""Recovery control tests; archived failures are immutable input, no inference."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import pilot_collection_recovery_v1 as r


class RecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parent = r.actor.read(r.original.PLAN)
        cls.parent_run = r.ROOT / 'results/pilot_collection_v1_b01_29672744'
        cls.summary = r.actor.read(cls.parent_run / 'summary.json')

    def test_exact_unattempted_twenty_and_same_rollout(self):
        selected = r.selected_attempts(self.parent, self.summary)
        self.assertEqual([a['seed'] for a in selected], list(range(16011, 16031)))
        self.assertIs(r.actor.rollout, r.original.actor.rollout)

    def test_failed_or_reordered_candidates_not_recovered(self):
        s = copy.deepcopy(self.summary); s['attempts'] = s['attempts'][:-1]
        with self.assertRaises(ValueError): r.selected_attempts(self.parent, s)
        s = copy.deepcopy(self.summary); s['not_attempted_ids'].reverse()
        with self.assertRaises(ValueError): r.selected_attempts(self.parent, s)

    def test_real_archived_guard_failures_reproduce(self):
        for row in self.summary['attempts'][-2:]:
            self.assertTrue(r.verified_guard_exclusion(self.parent_run / row['attempt_id'], self.parent))

    def test_submitted_api_failure_cannot_be_length_exclusion(self):
        d = self.parent_run / self.summary['attempts'][-1]['attempt_id']; original_read = r.actor.read
        def read(path):
            value = original_read(path)
            if Path(path).name == 'summary.json':
                value['calls'][-1]['submitted'] = True
            return value
        with patch.object(r.actor, 'read', side_effect=read):
            self.assertFalse(r.verified_guard_exclusion(d, self.parent))

    def test_context_mismatch_or_other_error_stops(self):
        d = self.parent_run / self.summary['attempts'][-1]['attempt_id']; original_read = r.actor.read
        for replacement in ["ValueError('HTTP transport failure')", "ValueError('Context guard: 1+2+3>4; no messages discarded')"]:
            def read(path):
                if Path(path).name == 'error.json': return {'error': replacement}
                return original_read(path)
            with patch.object(r.actor, 'read', side_effect=read):
                self.assertFalse(r.verified_guard_exclusion(d, self.parent))

    def test_ambiguous_existing_submission_never_repeated(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'submission.json'; path.write_text('{"status":"submitting"}')
            with patch.object(r, 'verify', return_value=({}, {}, {})), patch.object(r, 'artifact', return_value=path), patch.object(r.subprocess, 'run') as process:
                with self.assertRaises(ValueError): r.submit()
                process.assert_not_called()


if __name__ == '__main__': unittest.main()
