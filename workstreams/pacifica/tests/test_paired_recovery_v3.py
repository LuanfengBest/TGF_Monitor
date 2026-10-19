from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from paired_protocol_v3 import PLAN, read, sha_file
from verify_paired_v3 import verify, frozen_prefix
from run_paired_v3 import recover_trace


class RecoveryTests(unittest.TestCase):
    def test_entire_saved_prefix_reconstructs(self):
        result=verify(prefix_only=True)
        self.assertTrue(result['passed'])
        self.assertEqual(result['calls_including_reused'],8)
        self.assertEqual(result['new_calls'],0)

    def test_changed_frozen_artifact_is_rejected(self):
        plan=deepcopy(read(PLAN))
        key=next(iter(plan['recovery']['prefix_files_sha256']))
        plan['recovery']['prefix_files_sha256'][key]='0'*64
        with self.assertRaisesRegex(ValueError,'Reused artifact changed'):
            frozen_prefix(plan)

    def test_recovery_only_requests_missing_judge_and_preserves_source(self):
        plan=read(PLAN)
        before={p:sha_file(ROOT/p) for p in plan['recovery']['prefix_files_sha256']}
        client=Mock()
        client.monitor.return_value={'verdict':'unresolved','unauthorized_action_score':50,
            'evidence':[],'summary':'UNIT TEST ONLY','uncertainties':[]}
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/plan['attempts'][0]['trace_id']
            recover_trace(client,plan['attempts'][0],out,plan)
            client.monitor.assert_called_once()
            self.assertEqual(client.monitor.call_args.args[-1],'tgf_judge')
            client.actor.assert_not_called()
            self.assertEqual(read(out/'summary.json')['status'],'completed')
        self.assertEqual(before,{p:sha_file(ROOT/p) for p in before})


if __name__=='__main__':unittest.main()
