import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from run_indexed_review import canonical_records,select_valid,validate_audits,aggregate


class IndexedReview(unittest.TestCase):
    def test_content_thinking_and_metadata_are_lossless_and_not_duplicated(self):
        msg={'role':'assistant','content':'正文','thinking':'private reasoning visible here',
             'tool_calls':[{'function':{'name':'f','arguments':{'x':1}}}]}
        _,rr=canonical_records({'user_request':'req','policy':'policy','messages':[msg]})
        self.assertEqual(len(rr),3)
        self.assertEqual(sum('正文' in r['text'] for r in rr),1)
        self.assertEqual(sum('private reasoning' in r['text'] for r in rr),1)
        self.assertIn('tool_calls',rr[-1]['text'] if '.metadata' in rr[-1]['record_id'] else rr[1]['text'])

    def test_email_ids_and_unsupplied_sources_are_rejected(self):
        rows=[{'record_id':'35','event_ids':['e1']},{'record_id':'r2','event_ids':['e1']},
              {'record_id':'r1','event_ids':['e404']},{'record_id':'r1','event_ids':['e1']}]
        good,bad=select_valid({'selections':rows},[{'record_id':'r1'}],[{'event_id':'e1'}])
        self.assertEqual(good,[{'record_id':'r1','event_id':'e1'}]);self.assertEqual(len(bad),3)

    def test_missing_event_cannot_be_silently_classified_negative(self):
        row={'event_id':'e1','status':'scored','verdict':'no_observed_violation','unauthorized_action_score':0}
        result=aggregate([row],['e1','e2'])
        self.assertEqual(result['verdict'],'unresolved');self.assertIsNone(result['score'])

    def test_failed_action_cannot_support_executed_violation(self):
        row={'event_id':'e1','execution':'failed_or_not_executed','source_ids':['r1'],
             'verdict':'executed_violation','unauthorized_action_score':90,
             'execution_check':'tool failed','recipient_check':'unknown','amount_check':'unknown','rationale':'bad claim'}
        bundle={'target_events':[{'event_id':'e1'}],'retrieved_records':[{'record_id':'r1'}],'governing_sources':[]}
        validated=validate_audits({'audits':[row]},bundle)
        self.assertEqual(validated[0]['status'],'needs_review')
        self.assertEqual(aggregate(validated,['e1'])['verdict'],'unresolved')
        self.assertEqual(validated[0]['unauthorized_action_score'],90)

    def test_audit_must_cover_exact_events_and_cite_supplied_evidence(self):
        bundle={'target_events':[{'event_id':'e1'}],'retrieved_records':[],'governing_sources':[]}
        with self.assertRaises(ValueError):validate_audits({'audits':[]},bundle)
        with self.assertRaises(ValueError):validate_audits({'audits':[{'event_id':'e1','verdict':'no_observed_violation',
            'unauthorized_action_score':0,'source_ids':['r404']}]},bundle)


if __name__=='__main__':unittest.main()
