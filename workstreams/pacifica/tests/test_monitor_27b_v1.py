import sys
from pathlib import Path
import unittest
from jinja2 import Environment
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from monitor_27b_v1 import ROOT,PLAN,SYSTEM,Counter,compact,render,payload,read,verify

class Candidate27BTests(unittest.TestCase):
    def test_frozen_templates_and_long_capacity(self):
        plan=read(PLAN);verify(plan);counter=Counter()
        template=Environment().from_string((ROOT/'data/tokenizers/qwen3_5_27b/chat_template.jinja').read_text())
        def fail(msg): raise ValueError(msg)
        for e in plan['inputs']:
            b=read(ROOT/e['path'])
            self.assertEqual(render(b),template.render(messages=[{'role':'system','content':SYSTEM},{'role':'user','content':compact(b)}],add_generation_prompt=True,enable_thinking=True,raise_exception=fail))
            self.assertEqual(counter.check(render(b),plan['num_predict']),plan['capacity'][e['input_id']])
        for c in plan['calibrations']:self.assertEqual(counter.check(c['prompt'],c['num_predict']),c['expected_prompt_tokens'])
        self.assertGreaterEqual(plan['calibrations'][-1]['expected_prompt_tokens'],max(plan['capacity'].values()))
        with self.assertRaises(ValueError):counter.check('hello',32768)
    def test_identity_and_request_isolation(self):
        p=read(PLAN);b=read(ROOT/p['inputs'][0]['path']);req=payload(p,render(b),p['num_predict'])
        self.assertEqual(req['model'],'qwen3.5:27b');self.assertFalse(req['truncate']);self.assertFalse(req['shift'])
        self.assertNotIn('execution_facts',req['prompt']);self.assertNotIn('private_reference',req['prompt'])
        old=read(ROOT/'configs/monitor_candidate_v4.json')
        for key in ['inputs','system_sha256','sampling','capacity','num_predict','seed']:self.assertEqual(p[key],old[key])

if __name__=='__main__':unittest.main()
