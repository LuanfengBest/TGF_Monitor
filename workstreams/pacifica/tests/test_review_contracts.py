import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from review_contracts import selection_contract,audit_contract,decode_event_map


class ReviewContracts(unittest.TestCase):
    def setUp(self):
        self.bundle={'target_events':[{'event_id':'e1'},{'event_id':'e2'}],
                     'governing_sources':[{'record_id':'user_request#000'}],
                     'retrieved_records':[{'record_id':'r1'}]}
        self.row={'execution':'failed_or_not_executed','execution_check':'Tool returned failure.',
                  'recipient_check':'unknown','amount_check':'unknown','source_ids':['r1'],
                  'verdict':'no_observed_violation','unauthorized_action_score':0,'rationale':'No executed payment.'}

    def test_omitted_event_never_defaults_to_safe(self):
        with self.assertRaisesRegex(ValueError,'Missing or extra event key'):
            decode_event_map({'audits_by_event':{'e1':self.row}},self.bundle)

    def test_extra_event_and_unknown_source_rejected(self):
        with self.assertRaises(ValueError):
            decode_event_map({'audits_by_event':{'e1':self.row,'e2':self.row,'e3':self.row}},self.bundle)
        with self.assertRaisesRegex(ValueError,'unavailable original record'):
            decode_event_map({'audits_by_event':{'e1':{**self.row,'source_ids':['e1']},'e2':self.row}},self.bundle)

    def test_contracts_only_expose_the_actual_input_ids(self):
        s=selection_contract([{'record_id':'r1'}],self.bundle['target_events'])
        self.assertEqual(s['properties']['selections']['items']['properties']['record_id']['enum'],['r1'])
        a=audit_contract(self.bundle)['properties']['audits_by_event']
        self.assertEqual(a['required'],['e1','e2'])
        self.assertEqual(a['properties']['e1']['properties']['source_ids']['items']['enum'],['user_request#000','r1'])
        result=decode_event_map({'audits_by_event':{'e2':self.row,'e1':self.row}},self.bundle)
        self.assertEqual([r['event_id'] for r in result],['e1','e2'])


if __name__=='__main__':unittest.main()
