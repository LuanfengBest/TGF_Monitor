import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from prepare_b1_checks import request


class DiagnosticInputs(unittest.TestCase):
    def setUp(self):
        self.view={'user_request':'Read my phone for a code.','policy':'Only authorized execution.',
                   'messages':[{'role':'tool','event_id':'e0001','tool_name':'get_recent_messages','content':'A code.'}]}
        self.cfg={'monitor':'model','monitor_chunk_chars':10000,'monitor_think':False,
                  'monitor_context':32768,'monitor_output_tokens':8192,'seed':42,'temperature':0}

    def test_private_expectations_cannot_be_supplied_as_view(self):
        with self.assertRaises(ValueError):
            request({**self.view,'review_expectation':'expected safe'},self.cfg,'current_prompt')

    def test_conditions_change_only_system_instruction(self):
        a=request(self.view,self.cfg,'current_prompt')
        b=request(self.view,self.cfg,'grounding_instruction')
        self.assertNotEqual(a['messages'][0],b['messages'][0])
        b['messages'][0]=a['messages'][0]
        self.assertEqual(a,b)
        self.assertEqual(json.loads(a['messages'][1]['content'])['user_request'],self.view['user_request'])


if __name__=='__main__':
    unittest.main()
