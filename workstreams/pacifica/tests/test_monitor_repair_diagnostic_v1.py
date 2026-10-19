import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import monitor_repair_diagnostic_runtime_v1 as run
from monitor_interface_v3 import parse_response


class DiagnosticTests(unittest.TestCase):
    def test_inputs_no_references_and_balanced_public_source_only(self):
        rows=run.old.rows(run.DATA/'inputs.jsonl');refs=run.old.rows(run.DATA/'references.jsonl')
        self.assertEqual(len(rows),12)
        for r,ref in zip(rows,refs):
            self.assertEqual(set(r),{'metadata','input','input_ids'})
            self.assertEqual(set(r['input']),{'target_event_id','user_request','policy','messages','tool_effect_contract'})
            canonical=json.dumps(r['input'],ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
            self.assertEqual(r['metadata']['input_sha256'],__import__('hashlib').sha256(canonical.encode()).hexdigest())
            self.assertLessEqual(len(r['input_ids'])+1024,4096)
            self.assertTrue(parse_response(json.dumps(ref['reference']))['core_internally_consistent'])
        for split in ['training_event_probe','same_family_new_dev']:
            for domain in ['bank','travel']:
                rr=[r for r in refs if r['metadata']['split']==split and r['metadata']['domain']==domain]
                self.assertEqual([r['reference']['executed_unauthorized'] for r in rr],[False,True,None])

    def test_existing_submission_stops_before_any_slurm_call(self):
        with patch.object(run,'verify'),patch.object(run,'SUB',ROOT/'AGENTS.md'),patch.object(run.subprocess,'check_output') as call:
            with self.assertRaises(AssertionError):run.submit()
            call.assert_not_called()

    def test_unchanged_legacy_inference_used_no_training_call(self):
        import ast
        tree=ast.parse(Path(run.__file__).read_text())
        runtime=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='run')
        attrs=[n.func.attr for n in ast.walk(runtime) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)]
        self.assertIn('inference',attrs)
        self.assertFalse(any(x in attrs for x in ['backward','step','train','fresh_adapter']))


if __name__=='__main__':unittest.main()
