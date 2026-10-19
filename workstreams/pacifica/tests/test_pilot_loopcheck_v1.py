"""Offline reservation, input freeze and hard runtime budget boundary tests."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import pilot_loopcheck_v1 as c
import pilot_collection_recovery_v1 as recovery
class LoopcheckTests(unittest.TestCase):
    def test_submission_and_execution_locks(self):
        for suffix in ['submission','reservation']:
            with tempfile.TemporaryDirectory() as tmp:
                def artifact(s):return Path(tmp)/(s+'.json')
                artifact(suffix).write_text('{}')
                with patch.object(c,'verify'),patch.object(c,'artifact',side_effect=artifact),patch.object(c.subprocess,'run') as proc:
                    with self.assertRaises(ValueError):c.submit()
                    proc.assert_not_called()
    def test_active_queue_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            def artifact(s):return Path(tmp)/(s+'.json')
            artifact('preflight').write_text(json.dumps({'status':'passed','plan_sha256':'same'}))
            with patch.object(c,'verify'),patch.object(c,'artifact',side_effect=artifact),patch.object(c.actor,'sha',return_value='same'),patch.object(c.subprocess,'check_output',return_value='123 RUNNING'),patch.object(c.subprocess,'run') as proc:
                with self.assertRaises(ValueError):c.submit()
                proc.assert_not_called();self.assertFalse(artifact('submission').exists())
    def test_ambiguous_submit_never_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            def artifact(s):return Path(tmp)/(s+'.json')
            artifact('preflight').write_text(json.dumps({'status':'passed','plan_sha256':'same'}))
            with patch.object(c,'verify'),patch.object(c,'artifact',side_effect=artifact),patch.object(c.actor,'sha',return_value='same'),patch.object(c.subprocess,'check_output',return_value=''),patch.object(c.subprocess,'run',side_effect=TimeoutError('unit-test-only')) as proc:
                with self.assertRaises(TimeoutError):c.submit()
                self.assertEqual(json.loads(artifact('submission').read_text())['status'],'unknown_outcome_do_not_retry')
                with self.assertRaises(ValueError):c.submit()
                self.assertEqual(proc.call_count,1)
    def test_guard_and_backend_unchanged(self):
        self.assertIs(c.verified_guard_exclusion,recovery.verified_guard_exclusion)
        self.assertIs(c.actor.DeadlineOllama,c.original.actor.DeadlineOllama)
    def test_freeze_verification_rejects_bad_scope(self):
        # This test can run before the real plan freeze; no external files or GPU required.
        auth={'user_message':'好的，就按这个方案推进，先修复采集循环并做12条可行性检查，最多60 GPU分钟。数据门槛没过就停下来告诉我，别急着跑TGF比较或微调，同时把10月17日的汇报材料整理好。'}
        plan={'source_hashes':{},'authorization':'test.json','max_gpu_seconds':3600,'max_actor_calls':480,'runner_deadline_seconds':3450,'automatic_retries':0,'max_new_jobs':1,'max_attempts':12,'monitor_calls':0,'training_runs':0,'max_no_tool_reminders':5,'parent_plan_sha256':'same','attempts':[]}
        for i in range(12):
            f=('bank_transfer_2','american_airlines_2')[i%2]
            plan['attempts'].append({'attempt_id':f'loopcheck1_{i+1:03d}_{f}_ordinary','candidate_id':f,'condition':'ordinary','seed':26001+i,'secondary_objective':'unchanged'})
        def verify(p):
            def read(path):return p if path==c.PLAN else {} if path==c.original.PLAN else auth
            with patch.object(c.actor,'read',side_effect=read),patch.object(c.original,'verify',return_value={}),patch.object(c.actor,'sha',return_value='same'),patch.object(c.actor,'load_original') as loader:
                loader.return_value.secondary_objective='unchanged';return c.verify()
        verify(plan)
        for key,val in [('max_gpu_seconds',3601),('max_actor_calls',481),('monitor_calls',1),('training_runs',1),('automatic_retries',1),('max_no_tool_reminders',6)]:
            bad=deepcopy(plan);bad[key]=val
            with self.assertRaises(ValueError):verify(bad)
        for key,val in [('condition','injected'),('seed',26002),('secondary_objective','new')]:
            bad=deepcopy(plan);bad['attempts'][0][key]=val
            with self.assertRaises(ValueError):verify(bad)
if __name__=='__main__':unittest.main()
