import ast
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import sft_three_arm_runtime_v2 as r


def functions(name):
    return {x.name: x for x in ast.parse((ROOT / 'scripts' / name).read_text()).body
            if isinstance(x, ast.FunctionDef)}


class BudgetRecoveryTests(unittest.TestCase):
    def test_scientific_functions_identical(self):
        a, b = functions('sft_three_arm_runtime_v1.py'), functions('sft_three_arm_runtime_v2.py')
        for name in ('safe_json', 'padded_record', 'data_gate', 'load_base', 'fresh_adapter',
                     'tensor_batch', 'verify_tokenizer', 'finite_grad', 'make_optimizer',
                     'adapter_identity', 'inference', 'evaluate'):
            self.assertEqual(ast.dump(a[name]), ast.dump(b[name]), name)
        # Only the leading training gate changed. All data selection, shuffling,
        # optimizer updates, checkpointing and failure handling remain identical.
        def after_gate(node):
            return node.body[next(i for i,x in enumerate(node.body)
                                  if isinstance(x, ast.Assign)
                                  and any(isinstance(y, ast.Name) and y.id == 'trainrows' for y in x.targets)):]
        self.assertEqual([ast.dump(x) for x in after_gate(a['train'])],
                         [ast.dump(x) for x in after_gate(b['train'])])

    def test_actual_proof_passes_new_budget(self):
        old = r.qualification_gate()
        self.assertEqual(old['status'], 'failed')
        self.assertFalse(old['training_eligible'])
        self.assertEqual(old['job_id'], '29594960')

    def test_only_original_time_gate_failure_can_be_requalified(self):
        original = r.read
        def altered(path):
            obj = deepcopy(original(path))
            if str(path).endswith('preflight/receipt.json'):
                obj['error'] = 'CUDA out of memory'
            return obj
        with patch.object(r, 'read', side_effect=altered):
            with self.assertRaises(AssertionError):
                r.qualification_gate()

    def test_unapproved_or_smaller_budget_rejected(self):
        original = r.read
        for field, value in [('approved', False), ('training_minutes_each', 45)]:
            def altered(path, field=field, value=value):
                obj = deepcopy(original(path))
                if str(path).endswith('sft_runtime_budget_approval_20261014.json'):
                    obj[field] = value
                return obj
            with patch.object(r, 'read', side_effect=altered):
                with self.assertRaises(AssertionError):
                    r.qualification_gate()

    def test_gradient_or_initialization_failure_still_rejected(self):
        original = r.read
        for field, value in [('gradient_norm', 0), ('initialization_sha256', 'wrong')]:
            def altered(path, field=field, value=value):
                obj = deepcopy(original(path))
                if str(path).endswith('preflight/receipt.json'):
                    obj['arms'][0][field] = value
                return obj
            with patch.object(r, 'read', side_effect=altered):
                with self.assertRaises(AssertionError):
                    r.qualification_gate()


if __name__ == '__main__':
    unittest.main()
