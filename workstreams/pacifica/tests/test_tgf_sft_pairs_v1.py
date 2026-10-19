from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import tgf_sft_pairs_v1 as p


class PairedProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.originals = p.source.candidates()
        cls.encoder = p.Encoder()

    def test_all_prompts_identical_and_no_arm_or_reference_metadata(self):
        for original in self.originals:
            pair = p.paired_rows(original)
            for row in pair:
                row['metadata']['sentinel'] = 'PRIVATE_METADATA_SENTINEL'
            encoded = [self.encoder.encode(r) for r in pair]
            prefixes = [e['input_ids'][:e['prompt_tokens']] for e in encoded]
            self.assertEqual(prefixes[0], prefixes[1])
            self.assertNotIn('PRIVATE_METADATA_SENTINEL', self.encoder.tokenizer.decode(prefixes[0]))
            self.assertTrue(p.verify_pair(*pair))

    def test_loss_decodes_exact_answer_and_eos_for_both_arms(self):
        for original in self.originals:
            for row in p.paired_rows(original):
                encoded = self.encoder.encode(row)
                selected = [i for i in encoded['labels'] if i != -100]
                self.assertEqual(selected[-1], self.encoder.eos)
                self.assertEqual(json.loads(self.encoder.tokenizer.decode(selected[:-1])), row['target'])
                self.assertEqual(encoded['labels'][:encoded['prompt_tokens']], [-100] * encoded['prompt_tokens'])
                self.assertTrue(all(x == -100 for x in encoded['labels'][encoded['prompt_tokens'] + encoded['answer_tokens']:]))

    def test_unknown_and_boolean_strictness(self):
        ordinary, evidence = p.paired_rows(self.originals[4])
        ordinary['target']['executed_unauthorized'] = False
        with self.assertRaises(ValueError): self.encoder.encode(ordinary)
        with self.assertRaises(ValueError): p.verify_pair(ordinary, evidence)
        ordinary, _ = p.paired_rows(self.originals[0])
        ordinary['target']['executed_unauthorized'] = 0
        with self.assertRaises(ValueError): self.encoder.encode(ordinary)

    def test_input_change_private_fields_and_target_change_fail(self):
        ordinary, evidence = p.paired_rows(self.originals[0])
        ordinary['input']['private_state'] = {'answer': False}
        with self.assertRaises(ValueError): self.encoder.encode(ordinary)
        with self.assertRaises(ValueError): p.verify_pair(ordinary, evidence)
        ordinary, evidence = p.paired_rows(self.originals[0])
        ordinary['target']['rationale'] = 'Unsupported replacement'
        with self.assertRaises(ValueError): p.verify_pair(ordinary, evidence)

    def test_split_and_training_flags_cannot_be_promoted(self):
        for field, value in [('split', 'validation'), ('training_eligible', True)]:
            original = deepcopy(self.originals[0]); original['metadata'][field] = value
            with self.assertRaises(ValueError): p.paired_rows(original)
            row = p.paired_rows(self.originals[0])[0]; row['metadata'][field] = value
            with self.assertRaises(ValueError): self.encoder.encode(row)

    def test_no_silent_truncation(self):
        for row in p.paired_rows(self.originals[0]):
            with self.assertRaisesRegex(ValueError, 'never truncate'):
                self.encoder.encode(row, max_sequence_tokens=10)


if __name__ == '__main__':
    unittest.main()
