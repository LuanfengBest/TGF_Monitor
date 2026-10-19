import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from run_contract_probe import decode_selection, identity_context, source_union


class ContractProbe(unittest.TestCase):
    def test_identity_table_is_original_tool_content_only(self):
        base = {'record_id':'message_0001.content#000','role':'tool',
                'tool_name':'search_files','text':'name,iban\nA,X'}
        rows = [base, {**base,'role':'assistant'},
                {**base,'record_id':'message_0001.metadata#000'}]
        self.assertEqual(identity_context(rows), [base])

    def test_shared_identity_source_is_citeable_but_unknown_sources_are_rejected(self):
        bundle = {'records':[{'record_id':'r1'}], 'identity_context':[{'record_id':'map1'}],
                  'observed_events':[{'event_id':'pay1'}]}
        obj = {'selections':[{'record_id':'map1','event_ids':['pay1']}], 'limitations':'none'}
        self.assertEqual(decode_selection(obj,bundle), [{'record_id':'map1','event_id':'pay1'}])
        obj['selections'][0]['record_id'] = 'outside'
        with self.assertRaises(ValueError): decode_selection(obj,bundle)

    def test_empty_mapping_and_repeating_limitations_cannot_pass(self):
        bundle = {'records':[{'record_id':'r1'}], 'observed_events':[{'event_id':'pay1'}]}
        with self.assertRaises(ValueError):
            decode_selection({'selections':[{'record_id':'r1','event_ids':[]}], 'limitations':'none'},bundle)
        with self.assertRaises(ValueError):
            decode_selection({'selections':[], 'limitations':'Repeated text ' * 100},bundle)


if __name__ == '__main__': unittest.main()
