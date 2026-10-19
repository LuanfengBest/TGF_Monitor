"""Offline reservation, input freeze and hard runtime budget boundary tests."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import pilot_smalltasks_v1 as c
import pilot_collection_recovery_v1 as recovery
class SmallTaskTests(unittest.TestCase):
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
    def test_freeze_rejects_budget_and_attempt_changes(self):
        actual_read=c.actor.read;plan=actual_read(c.PLAN)
        for key,val in [('max_gpu_seconds',3601),('max_actor_calls',1201),('monitor_calls',1),('training_runs',1),('automatic_retries',1),('max_attempts',31)]:
            bad=deepcopy(plan);bad[key]=val
            with patch.object(c.actor,'read',side_effect=lambda path:bad if path==c.PLAN else actual_read(path)):
                with self.assertRaises(ValueError):c.verify()
        bad=deepcopy(plan);bad['attempts'][0]['seed']+=1
        with patch.object(c.actor,'read',side_effect=lambda path:bad if path==c.PLAN else actual_read(path)):
            with self.assertRaises(ValueError):c.verify()
    def test_original_assets_and_narrow_request(self):
        from pilot_smalltasks_adapter_v1 import load_small,require_small_ready
        from prospective_actor_v6 import canonical_state,digest
        plan=c.actor.read(c.PLAN);parent=c.actor.read(c.original.PLAN)
        for a in plan['attempts'][:6]:
            small=load_small(a);old=c.actor.load_original(a['candidate_id'])
            self.assertEqual(digest(canonical_state(small.environment.model_dump(mode='json'))),digest(canonical_state(old.environment.model_dump(mode='json'))))
            self.assertEqual(small.schemas,old.schemas);self.assertEqual(small.policy,old.policy);self.assertNotEqual(small.user_request,old.user_request)
            self.assertEqual(require_small_ready(small,parent['registry']),'development')
            small.user_request+=' New authorization'
            with self.assertRaises(ValueError):require_small_ready(small,parent['registry'])
    def test_rollout_change_is_loading_and_provenance_only(self):
        import ast
        root=Path(__file__).resolve().parents[1]
        old=(root/'scripts/prospective_actor_reminder_v1.py').read_text()
        new=(root/'scripts/prospective_actor_smalltasks_v1.py').read_text()
        new=new.replace('c = load_small(attempt)',"c = load_original(attempt['candidate_id'])").replace('require_small_ready(c, registry)',"require_original_ready(c, registry['candidates'])").replace("'collector_version': 'focused_original_assets_v1', 'task_id': c.task_id,","'collector_version': 'upstream_reminder_v1',")
        fn=lambda src:next(n for n in ast.parse(src).body if isinstance(n,ast.FunctionDef) and n.name=='rollout')
        self.assertEqual(ast.dump(fn(old),include_attributes=False),ast.dump(fn(new),include_attributes=False))
    def test_fake_rollout_uses_public_task_only(self):
        from pilot_smalltasks_adapter_v1 import load_small
        plan=c.actor.read(c.PLAN);parent=c.actor.read(c.original.PLAN);a=plan['attempts'][0];expected=load_small(a)
        class Client:
            count=0
            def chat(self,model,context,**kwargs):
                self.observed=deepcopy(context);self.count+=1
                return {'done':True,'done_reason':'stop','eval_count':5,'message':{'role':'assistant','tool_calls':[{'function':{'name':'end_task','arguments':{}}}]}}
        cl=Client()
        with tempfile.TemporaryDirectory() as tmp,patch.object(c.actor,'dispatch',return_value=('end_task',None)):
            self.assertEqual(c.actor.rollout(a,parent,parent['registry'],Path(tmp)/'out',cl),'ended')
        self.assertEqual(cl.observed,[{'role':'system','content':parent['actor_system']},{'role':'user','content':expected.user_request}])
        self.assertNotIn(a['secondary_objective'],str(cl.observed))
if __name__=='__main__':unittest.main()
