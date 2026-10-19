import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import monitor_v2_baseline_v1 as mod
from candidate_monitor_view_v1 import event_bundles
from test_candidate_monitor_view_v1 import view

class FakeCounter:
    def check(self,*args):return 20

class FakeClient:
    outputs=[]
    def __init__(self,*args):self.timeout=30
    def metadata(self,*args):return {'version':{'version':'0.0.0'},'tags':{'models':[{'name':'m','digest':'d'}]}}
    def api(self,*args):
        v=self.outputs.pop(0)
        if isinstance(v,Exception):raise v
        return v

class RuntimeTests(unittest.TestCase):
    def run_fake(self,outputs):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);root=Path(tmp.name)
        (root/'results').mkdir();item=event_bundles(view())[0]
        for i in range(3):(root/f'i{i}.json').write_text(json.dumps(item))
        plan={'model':'m','model_digest':'d','backend_installation_hashes':{},'runner_deadline_seconds':1000,
              'max_http_seconds':20,'max_calls':3,'max_consecutive_output_failures':2,'num_predict':100,
              'num_ctx':32768,'seed':42,'sampling':{},'inputs':[{'input_id':f'i{i}','path':f'i{i}.json','expected_prompt_tokens':20} for i in range(3)]}
        cfg=root/'plan.json';cfg.write_text(json.dumps(plan));FakeClient.outputs=outputs
        with patch.object(mod,'ROOT',root),patch.object(mod,'PLAN',cfg),patch.object(mod,'verify'),patch.object(mod,'NativeCounter',FakeCounter),patch.object(mod,'BoundedClient',FakeClient):
            try:mod.run(root/'out')
            except TimeoutError:pass
        return root,json.loads((root/'out/summary.json').read_text())

    def test_two_parse_failures_stop_without_retry_or_third_request(self):
        response={'done':True,'done_reason':'stop','prompt_eval_count':20,'eval_count':3,'response':'invalid'}
        root,s=self.run_fake([response,response])
        self.assertEqual(s['status'],'stopped_output_failures');self.assertEqual(len(s['calls']),2)
        self.assertFalse((root/'out/calls/i2_request.json').exists())
        self.assertTrue((root/'out/calls/i0_response.json').exists())

    def test_transport_failure_preserves_request_unknown_usage_and_no_retry(self):
        root,s=self.run_fake([TimeoutError('test bounded transport')])
        self.assertEqual(s['status'],'failed');self.assertEqual(len(s['calls']),1)
        self.assertTrue(s['calls'][0]['final_usage_unknown'])
        self.assertTrue((root/'out/calls/i0_request.json').exists())
        self.assertFalse((root/'out/calls/i1_request.json').exists())

if __name__=='__main__':unittest.main()
