import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from sft_resumption_data_v1 import DeletePopThenError, mask_check

class RepairAndMaskTests(unittest.TestCase):
    def test_fault_occurs_after_real_deletion(self):
        d = DeletePopThenError({'target': 1, 'survivor': 2})
        with self.assertRaisesRegex(RuntimeError, 'storage error'):
            d.pop('target', None)
        self.assertEqual(d, {'survivor': 2})

    def test_prompt_and_padding_never_supervised(self):
        row = {'prompt_tokens':2,'answer_tokens':2,'sequence_tokens':5,
               'input_ids':[10,11,12,13,14],'labels':[-100,-100,12,13,-100]}
        mask_check(row)
        for index in (0, 4):
            changed = dict(row, labels=row['labels'].copy())
            changed['labels'][index] = row['input_ids'][index]
            with self.assertRaises(ValueError): mask_check(changed)

if __name__ == '__main__': unittest.main()
