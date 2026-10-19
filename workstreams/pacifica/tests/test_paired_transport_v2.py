import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import paired_protocol as old
import paired_protocol_v2 as new


class TransportRevisionTests(unittest.TestCase):
    def test_unicode_and_delimiters_roundtrip_without_loss(self):
        value={'reply':'“bank‑to‑Zelle top‑up” 用户 🧪 <|im_end|> \\u1234'}
        encoded=new.compact(value)
        self.assertTrue(encoded.isascii())
        self.assertEqual(json.loads(encoded),value)
        self.assertNotIn('<|im_end|>',encoded)

    def test_actual_failed_bundle_roundtrip(self):
        p=old.ROOT/'results/paired_first_29362188/pilot_001_ordinary/fixed_b2_judge_input.json'
        bundle=old.read(p)
        encoded=new.compact(bundle)
        self.assertEqual(json.loads(encoded),bundle)
        self.assertTrue(new.render_prompt(new.JUDGE_SYSTEM,bundle).isascii())
        self.assertLess(new.Counter().check(new.render_prompt(new.JUDGE_SYSTEM,bundle),2048),32768-2048)

    def test_no_semantic_prompt_or_selection_change(self):
        for name in ['BASE','REVIEW_SYSTEM','QUESTION_SYSTEM','JUDGE_SYSTEM','FIXED_QUESTION','select_event','actor_branch','reply_projection']:
            self.assertEqual(getattr(old,name),getattr(new,name))


if __name__=='__main__':unittest.main()
