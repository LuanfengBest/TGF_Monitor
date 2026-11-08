"""Scientific contrast, provenance, failure, and resource-bound checks."""
from collections import Counter, defaultdict
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from . import run
from .prepare import OUT, CONDITIONS, public_check, read, specification


class ValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.requests = read(OUT / "requests.json")
        cls.targets = {r["request_id"]: r for r in read(OUT / "targets_LOCAL_ONLY.json")}
        cls.records = read(OUT / "public_records.json")

    def test_complete_balanced_design_and_bounded_cost(self):
        self.assertEqual(len(self.requests), 120)
        self.assertEqual(len({r["request_id"] for r in self.requests}), 120)
        self.assertEqual(Counter(r["model_slot"] for r in self.requests), {"monitor": 60, "actor": 60})
        self.assertEqual(sum(r["max_output_tokens"] for r in self.requests), 368640)
        self.assertEqual(len({r["block"] for r in self.targets.values()}), 6)
        self.assertEqual(len({r["case_id"] for r in self.targets.values()}), 12)
        self.assertEqual(Counter(r["reference_violation"] for r in self.targets.values()), {True: 60, False: 60})
        for model in ("monitor", "actor"):
            for condition in CONDITIONS:
                targets = [r for r in self.targets.values() if r["model_slot"] == model and r["condition"] == condition]
                self.assertEqual(Counter((r["environment"], r["reference_violation"]) for r in targets),
                                 {("bank", True): 3, ("bank", False): 3, ("airline", True): 3, ("airline", False): 3})

    def test_only_answer_treatment_changes(self):
        groups = defaultdict(dict)
        for request in self.requests:
            target = self.targets[request["request_id"]]
            groups[target["case_id"], target["model_slot"]][target["condition"]] = request
        for group in groups.values():
            self.assertEqual(set(group), set(CONDITIONS))
            bases, atoms, extra = [], [], {}
            for condition, request in group.items():
                prefix, payload = request["prompt"].split("PUBLIC INPUT:\n", 1)
                payload = json.loads(payload)
                pieces = payload["qa"].pop("answer").split("\nAdditional statement:\n")
                atoms.append(pieces[0])
                if len(pieces) > 1:
                    extra[condition] = json.loads(pieces[1])
                bases.append((prefix, payload, request["schema"], request["seed"], request["max_output_tokens"]))
                for key in ("reference_violation", "private_reference", "correct_assertion", "incorrect_assertion", "expected_label"):
                    self.assertNotIn(key, request["prompt"])
                repeated = json.loads(payload["qa"]["question"].split("\nPUBLIC ORIGINAL RECORD:\n", 1)[1])
                self.assertEqual(repeated, {k: payload[k] for k in ("record", "ledger", "call_citation_texts")})
            self.assertEqual(len(set(atoms)), 1)
            self.assertTrue(all(v == bases[0] for v in bases))
            self.assertEqual(extra["incorrect_assertion"], {"authorization_violation": not extra["correct_assertion"]["authorization_violation"]})
            comparison = deepcopy(extra["comparison_only"])
            comparison.pop("numeric_comparison")
            self.assertEqual(comparison, extra["running_total"])

    def test_public_receipts_private_states_and_reference_agree(self):
        equality, below, above = 0, 0, 0
        for record in self.records:
            checked = public_check(record["public"])
            result = read(OUT / "simulator_records" / record["case_id"] / "result_private.json")
            self.assertEqual(result["reference"]["label"], int(checked["violation"]))
            self.assertEqual(result["origin_kind"], "scripted_cpu_fixture")
            self.assertEqual(result["model_calls"], 0)
            self.assertFalse(result["formal_test_eligible"])
            self.assertTrue(result["journal"]["complete"])
            self.assertTrue(all(e["status"] == "committed" for e in result["journal"]["events"]))
            total, cap = Decimal(checked["total"]), Decimal(checked["cap"])
            equality += total == cap; below += total < cap; above += total > cap
            self.assertTrue(all(Decimal(row["amount"]) < cap for row in checked["rows"]))
            self.assertTrue(all(Decimal(row["cumulative"]) <= cap for row in checked["rows"][:-1]))
        self.assertEqual((equality, below, above), (4, 2, 6))

    def test_public_check_rejects_wrong_receipt_or_route(self):
        for domain in ("bank", "airline"):
            record = deepcopy(next(r["public"] for r in self.records if r["environment"] == domain))
            receipt = next(m for m in record["messages"] if m["role"] == "tool")
            receipt["content"] = receipt["content"].replace("83.25", "84.25")
            with self.assertRaises(AssertionError):
                public_check(record)
        record = deepcopy(next(r["public"] for r in self.records if r["environment"] == "airline"))
        next(m for m in record["messages"] if m["source_id"] == "m00002")["content"] = record["messages"][1]["content"].replace("Seattle to Denver", "Seattle to Boston")
        with self.assertRaises(AssertionError):
            public_check(record)

    def test_reference_is_not_extracted_from_treatment_assertion(self):
        for request in self.requests:
            target = self.targets[request["request_id"]]
            data = json.loads(request["prompt"].split("PUBLIC INPUT:\n", 1)[1])
            self.assertEqual(public_check(data["record"])["violation"], target["reference_violation"])
            if target["condition"] == "incorrect_assertion":
                claim = json.loads(data["qa"]["answer"].split("\nAdditional statement:\n")[1])
                self.assertNotEqual(claim["authorization_violation"], target["reference_violation"])

    def test_budget_missing_invalid_and_truncated_outputs(self):
        request = self.requests[0]
        data = json.loads(request["prompt"].split("PUBLIC INPUT:\n", 1)[1])
        valid = {"score": 0, "evidence": [{"claim": "A test citation", "evidence_id": data["evidence_units"][0]["evidence_id"]}],
                 "rationale": "A test explanation.", "unknown_reason": None}
        raw = {"finish_reason": "stop", "text": json.dumps(valid)}
        self.assertEqual(run.validate_output(raw, request)[0], "valid")
        self.assertEqual(run.validate_output(dict(raw, finish_reason="length"), request), ("truncated_or_nonstop", None))
        bad = deepcopy(valid); bad["rationale"] = "x" * 801
        self.assertEqual(run.validate_output(dict(raw, text=json.dumps(bad)), request), ("invalid_schema", None))
        unknown = deepcopy(valid); unknown.update(score=None, unknown_reason="Original execution evidence is missing.")
        self.assertEqual(run.validate_output(dict(raw, text=json.dumps(unknown)), request)[0], "unknown")
        limits = read(OUT / "config.json")["limits"]
        for calls, reserved, seconds in ((120, 0, 100), (0, 368640, 100), (0, 0, 0)):
            with self.assertRaises(RuntimeError):
                run.budget_check(calls, reserved, request, limits, seconds)

    def test_manifest_tampering_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); bundle = root / "bundle"; bundle.mkdir()
            source = root / "input.json"; source.write_text("frozen")
            (bundle / "manifest.json").write_text(json.dumps({"files": {"input.json": run.sha(source)}}))
            with patch.object(run, "ROOT", root), patch.object(run, "BUNDLE", bundle):
                run.verify_manifest()
                source.write_text("changed")
                with self.assertRaises(ValueError):
                    run.verify_manifest()

    def test_analysis_keeps_all_failure_positions(self):
        from .analyze import score_position, summarize
        rows = [score_position(r, self.targets[r["request_id"]], None) for r in self.requests]
        summary = summarize(rows)
        all_groups = [r for r in summary if r["environment"] == "all"]
        self.assertEqual(sum(r["planned"] for r in all_groups), 120)
        self.assertTrue(all(r["valid"] == r["correct"] == r["false_negative"] == r["false_positive"] == 0 for r in all_groups))
        self.assertTrue(all(r["failures"] == {"missing": 12} for r in all_groups))


if __name__ == "__main__":
    unittest.main()
