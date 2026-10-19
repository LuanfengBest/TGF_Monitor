import copy
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from monitor_interface_v3 import parse_response, repair_input, BANK_EFFECT


class InterfaceTests(unittest.TestCase):
    def setUp(self):
        self.obj={'execution':'executed','authorization':'supported','executed_unauthorized':False}
        self.text=json.dumps(self.obj)
        self.payload={'target_event_id':'e1','user_request':'public','policy':'public',
            'messages':[{'role':'assistant','tool_calls':[{'id':'c1','function':{'name':'schedule_transaction','arguments':{}}}]},
                        {'role':'tool','tool_call_id':'c1','tool_name':'schedule_transaction','event_id':'e1','content':'public'}],
            'tool_effect_contract':{'scope':'email'}}

    def test_equal_lossless_wrappers_and_bare_json(self):
        for s in (self.text,'```json\n'+self.text+'\n```','```\n'+self.text+'\n```'):
            self.assertEqual(parse_response(s)['prediction'],self.obj)

    def test_no_prose_extraction_truncation_or_duplicate_key_repair(self):
        for s in ('Here is the result: '+self.text,self.text[:-1],self.text[:-1]+',"execution":"uncertain"}'):
            with self.assertRaises(ValueError):parse_response(s)

    def test_inconsistency_reported_without_overwriting_verdict(self):
        obj=self.obj|{'executed_unauthorized':None}
        r=parse_response(json.dumps(obj))
        self.assertFalse(r['core_internally_consistent']);self.assertIsNone(r['prediction']['executed_unauthorized'])

    def test_repair_changes_only_generic_tool_contract(self):
        old=copy.deepcopy(self.payload);new=repair_input(old,{'scope':'email'})
        self.assertEqual(new['tool_effect_contract'],BANK_EFFECT)
        self.assertEqual(old,self.payload)
        for k in new:
            if k!='tool_effect_contract':self.assertEqual(new[k],old[k])

    def test_private_fields_unknown_tools_and_mismatched_binding_rejected(self):
        for mode in ('private','unknown','binding','future'):
            p=copy.deepcopy(self.payload)
            if mode=='private':p['verifier']='must not enter model input'
            elif mode=='unknown':p['messages'][0]['tool_calls'][0]['function']['name']='other';p['messages'][1]['tool_name']='other'
            elif mode=='binding':p['messages'][1]['tool_call_id']='wrong'
            else:p['messages'].append({'role':'assistant','content':'future'})
            with self.assertRaises(ValueError):repair_input(p,{})


if __name__=='__main__':unittest.main()
