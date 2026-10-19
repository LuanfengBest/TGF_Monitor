import sys
from pathlib import Path
import unittest
from jinja2 import Environment
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from monitor_candidate_v1 import ROOT, SYSTEM, Counter, compact, render, render_text, payload, read

class CandidateTests(unittest.TestCase):
    def test_official_template_for_every_input(self):
        template=Environment().from_string((ROOT/'data/tokenizers/qwen3_5_9b/chat_template.jinja').read_text())
        def fail(msg): raise ValueError(msg)
        for e in read(ROOT/'configs/monitor_selection_v1.json')['inputs']:
            bundle=read(ROOT/e['path'])
            actual=template.render(messages=[{'role':'system','content':SYSTEM},{'role':'user','content':compact(bundle)}],
                                   add_generation_prompt=True,enable_thinking=True,raise_exception=fail)
            self.assertEqual(render(bundle),actual)
    def test_capacity_rejects_overflow(self):
        c=Counter()
        with self.assertRaises(ValueError): c.check('hello',32768)
    def test_special_tokens_and_unicode(self):
        c=Counter();p=render_text('system','银行 café—€ 😀 <tool_response>x</tool_response>')
        self.assertEqual(c.tokenizer.decode(c.tokenizer.encode(p,add_special_tokens=False).ids,skip_special_tokens=False),p)
    def test_no_hidden_inputs_in_request(self):
        p={'model':'qwen3.5:9b','num_ctx':32768,'seed':42,'sampling':{'temperature':1.0}}
        req=payload(p,render({'sources':[{'source_id':'user_request','text':'hello'}]}),6144)
        self.assertEqual(set(req),{'model','prompt','raw','stream','think','keep_alive','options'})
        self.assertTrue(req['think']);self.assertNotIn('/think',req['prompt'])

if __name__=='__main__': unittest.main()
