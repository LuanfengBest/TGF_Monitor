import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from index_visible_evidence import build_index, split_offsets


class EvidenceIndex(unittest.TestCase):
    def test_yaml_record_boundaries_preserve_unicode_and_all_characters(self):
        text='- id: 1\n  body: '+('甲'*2200)+'\n- id: 2\n  body: "second"\n'
        spans=split_offsets(text)
        self.assertEqual(len(spans),2)
        self.assertEqual(''.join(text[a:b] for a,b in spans),text)
        self.assertIn('id: 2',text[spans[1][0]:spans[1][1]])

    def test_user_request_has_distinct_source_from_actor_thinking(self):
        index=build_index({'user_request':'Permission here.','policy':'Policy.',
                          'messages':[{'role':'assistant','thinking':'A plan.','content':''}]})
        sources={r['source_id']:r['text'] for r in index['records']}
        self.assertEqual(sources['user_request'],'Permission here.')
        self.assertEqual(sources['message_0000.thinking'],'A plan.')
        self.assertNotIn('Permission here.',sources['message_0000.json'])


if __name__=='__main__':
    unittest.main()
