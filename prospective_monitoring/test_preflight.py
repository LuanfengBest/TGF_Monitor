"""CPU-only admission failures and deterministic example construction; no models."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from . import preflight as f
from . import campaign
from . import protocol as p
from .task_setup import build_development_manifest


MISSING = [name for name in ("pydantic", "yaml", "docstring_parser", "rich", "openai", "anthropic")
           if importlib.util.find_spec(name) is None]


class AssetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "snapshots" / f.native.PINNED["actor"]["revision"]
        self.root.mkdir(parents=True)
        content = {"config.json": json.dumps({"quantization_config": {"quant_method": "mxfp4"}}).encode(),
                   "model.safetensors.index.json": json.dumps({"weight_map": {"test": "weights.safetensors"}}).encode(),
                   "weights.safetensors": b"tiny fake CPU asset"}
        for name, data in content.items():
            (self.root / name).write_bytes(data)
        self.prior = {"revision": self.root.name, "files": {name: {
            "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "mtime_ns": 1}
            for name, data in content.items()}}

    def verify(self):
        return f.verify_asset_inventory(self.root, "actor", self.prior, time.monotonic() + 10)

    def test_full_bytes_verified_not_old_mtime_and_extra_files_recorded(self):
        (self.root / "generation_config.json").write_text("{}")
        result = self.verify()
        self.assertEqual(result["verification"], "fresh_full_sha256")
        self.assertEqual(result["prior_inventory_files_matched"], 3)
        self.assertEqual(len(result["files"]), 4)
        self.assertFalse(result["files"]["generation_config.json"]["compared_with_prior_receipt"])
        self.assertTrue(Path(result["files"]["weights.safetensors"]["resolved_path"]).is_file())

    def test_same_size_tampered_shard_rejected(self):
        path = self.root / "weights.safetensors"
        path.write_bytes(b"X" * path.stat().st_size)
        with self.assertRaisesRegex(ValueError, "bytes differ"):
            self.verify()

    def test_missing_baseline_shard_rejected(self):
        del self.prior["files"]["weights.safetensors"]
        with self.assertRaisesRegex(ValueError, "inventories differ"):
            self.verify()

    def test_expired_deadline_stops_before_hashing(self):
        with self.assertRaises(TimeoutError):
            f.verify_asset_inventory(self.root, "actor", self.prior, 0)


class SyntheticCompletionTests(unittest.TestCase):
    def test_only_actual_prefix_is_removed_and_channel_recipient_body_preserved(self):
        prefix = [100, 101]
        for completion in ([102, 103, 104, 105], [106, 107, 108]):
            rendered = prefix + completion
            self.assertEqual(f._synthetic_completion_tokens(rendered, prefix), completion)
            self.assertEqual(rendered, prefix + completion)

    def test_changed_or_empty_native_prefix_fails_closed(self):
        for rendered, prefix in (([100, 102, 103], [100, 101]), ([100], []), ([100, 101], [100, 101])):
            with self.assertRaises(ValueError):
                f._synthetic_completion_tokens(rendered, prefix)


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.config = campaign.default_config()
        self.tasks = build_development_manifest(1)["tasks"]
        self.prior = {"ready_for_gpu": True, "assets": {"actor": {}, "monitor": {}}}
        self.snapshots = {"actor": "/not-a-model/actor", "monitor": "/not-a-model/monitor"}

    def run_checks(self):
        return f.run_checks(self.config, self.tasks, self.prior, self.snapshots, self.temp.name)

    def test_runtime_failure_retains_binding_and_no_false_ready(self):
        with patch.object(f.native, "runtime_check", side_effect=ValueError("wrong pinned runtime")), \
             patch.object(f, "verify_asset_inventory") as assets:
            receipt = self.run_checks()
        assets.assert_not_called()
        for key in ("ready_for_live", "runtime_checked", "asset_inventory_checked",
                    "tokenizer_capacity_checked", "grammar_checked", "native_harmony_checked"):
            self.assertIs(receipt[key], False)
        self.assertEqual(receipt["task_manifest_sha256"], p.digest(self.tasks))
        self.assertEqual(receipt["code_sha256"], campaign.source_hashes())
        self.assertIn("wrong pinned runtime", receipt["blocked_reason"])
        self.assertEqual(receipt["model_calls"], 0)

    def test_grammar_failure_never_reuses_old_success(self):
        examples = {"actor": [], "monitor": [], "origin_kind": "scripted_cpu_fixture",
                    "selection_rule": "test mock", "model_calls": 0, "scope": "examples only", "cases": []}
        with patch.object(f.native, "runtime_check", return_value=f.native.PINNED_RUNTIME), \
             patch.object(f.native, "snapshot_check", return_value=Path(self.temp.name)), \
             patch.object(f, "verify_asset_inventory", return_value={"files": {}}) as assets, \
             patch.object(f, "prepare_examples", return_value=examples), \
             patch.object(f, "check_actor_examples", return_value={"native_harmony_render_and_parse_checked": True}), \
             patch.object(f.native, "compile_monitor_schemas", side_effect=ValueError("grammar failed")):
            receipt = self.run_checks()
        self.assertTrue(receipt["runtime_checked"])
        self.assertTrue(receipt["native_harmony_checked"])
        self.assertFalse(receipt["grammar_checked"])
        self.assertFalse(receipt["tokenizer_capacity_checked"])
        self.assertFalse(receipt["ready_for_live"])
        self.assertFalse(receipt["asset_inventory_checked"])
        assets.assert_not_called()
        self.assertIn("grammar failed", receipt["blocked_reason"])

    @unittest.skipIf(bool(MISSING), "Original simulator dependencies unavailable: " + ", ".join(MISSING))
    def test_real_cpu_fixture_examples_cover_revisions_tools_and_all_four_arms(self):
        tasks = build_development_manifest(2)["tasks"]
        result = f.prepare_examples(tasks, self.config, self.temp.name, time.monotonic() + 30)
        self.assertEqual(len(result["cases"]), 8)
        self.assertEqual(result["model_calls"], 0)
        self.assertEqual(result["origin_kind"], "scripted_cpu_fixture")
        self.assertEqual({x["kind"] for x in result["monitor"]}, {
            "T_planner", "C_review_0", "C_review_1", "F_review_0", "P_judge", "C_judge", "F_judge", "T_judge"})
        corrections = [r for r in result["cases"] if r["family_id"] == "bank_forward_correction"]
        self.assertEqual([x["authorization_revisions_delivered"] for x in corrections], [2, 2])
        for example in result["actor"]:
            if example["kind"].endswith("followup"):
                self.assertEqual(example["tools"], [])
                self.assertEqual(example["original_context_sha256"], p.digest(example["conversation"]))
        self.assertTrue((Path(self.temp.name) / "examples_private.json").is_file())


if __name__ == "__main__":
    unittest.main()
