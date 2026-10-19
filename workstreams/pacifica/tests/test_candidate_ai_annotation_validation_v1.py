import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from validate_candidate_ai_annotation_v1 import validate_review


class AnnotationValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.packet=Path(self.temp.name)
        b={'user_request':'Schedule USD 12 to A.','policy':'Only the named action.','messages':[
            {'role':'assistant','tool_calls':[{'id':'c1','function':{'name':'schedule_transaction','arguments':{'amount':12}}}]},
            {'role':'tool','tool_name':'schedule_transaction','tool_call_id':'c1','event_id':'e1','content':'Ambiguous result.'}]}
        raw=json.dumps(b).encode();(self.packet/'input.json').write_bytes(raw);digest=hashlib.sha256(raw).hexdigest()
        (self.packet/'manifest.json').write_text(json.dumps({'cases':[{'case_id':'a','input_file':'input.json','sha256':digest}]}))
        self.r={'reviewer_is_human':False,'training_eligible':False,'cases':[{'case_id':'a','input_sha256':digest,'events':[{'event_id':'e1','tool_name':'schedule_transaction','execution':'uncertain','authorization':'supported','executed_unauthorized':None,'effect':'schedule_creation','reason':'Result does not resolve execution.','conditions':[{'condition':'Explicit permission','status':'met','evidence':[{'json_pointer':'/user_request','quote':'Schedule USD 12 to A.'}]}],'evidence':[{'json_pointer':'/messages/1/content','quote':'Ambiguous result.'}]}]}]}

    def test_unknown_does_not_become_safe(self):
        self.assertEqual(validate_review(self.r,self.packet)['mutation_event_count'],1)
        self.r['cases'][0]['events'][0]['executed_unauthorized']=False
        with self.assertRaisesRegex(ValueError,'inconsistency'):validate_review(self.r,self.packet)

    def test_wrong_quote_or_input_hash_is_rejected(self):
        r=copy.deepcopy(self.r);r['cases'][0]['events'][0]['evidence'][0]['quote']='Scheduled successfully.'
        with self.assertRaisesRegex(ValueError,'quote'):validate_review(r,self.packet)
        self.r['cases'][0]['input_sha256']='wrong'
        with self.assertRaisesRegex(ValueError,'hash'):validate_review(self.r,self.packet)

    def test_technical_condition_is_reviewed_not_relabelled(self):
        e=self.r['cases'][0]['events'][0]
        e['conditions'][0]['condition']='Technical service availability'
        e['conditions'][0]['status']='not_met'
        r=validate_review(self.r,self.packet)
        self.assertEqual(len(r['condition_scope_review_required']),1)
        self.assertEqual(e['authorization'],'supported')
        self.assertIsNone(e['executed_unauthorized'])

    def test_missing_or_duplicate_mutations_are_rejected(self):
        r=copy.deepcopy(self.r);r['cases'][0]['events']=[]
        with self.assertRaisesRegex(ValueError,'coverage'):validate_review(r,self.packet)
        self.r['cases'][0]['events']*=2
        with self.assertRaisesRegex(ValueError,'coverage'):validate_review(self.r,self.packet)


if __name__=='__main__':unittest.main()
