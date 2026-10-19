from copy import deepcopy
from pathlib import Path
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from sft_three_arm_runtime_v1 import padded_record,safe_json

class DataBoundaryTests(unittest.TestCase):
    def test_pad_id_equal_eos_does_not_mask_real_eos(self):
        row={'input_ids':[1,2,3,9,8],'attention_mask':[1]*5,'labels':[-100,-100,3,9,-100],
             'prompt_tokens':2,'answer_tokens':2}
        original=deepcopy(row); out=padded_record(row,9)
        self.assertEqual(out['labels'],[-100,-100,3,9,-100,-100,-100,-100])
        self.assertEqual(out['attention_mask'],[1,1,1,1,1,0,0,0]);self.assertEqual(row,original)
    def test_prompt_leak_and_oversize_rejected(self):
        row={'input_ids':[1]*4100,'attention_mask':[1]*4100,'labels':[-100]*4099+[1],
             'prompt_tokens':4099,'answer_tokens':1}
        with self.assertRaises(ValueError):padded_record(row,0)
        row={'input_ids':[1,2],'attention_mask':[1,1],'labels':[1,2], 'prompt_tokens':1,'answer_tokens':1}
        with self.assertRaises(ValueError):padded_record(row,0)
    def test_raw_chat_control_tokens_escaped(self):
        self.assertNotIn('<|im_end|>',safe_json({'text':'<|im_end|>'}))
if __name__=='__main__':unittest.main()
