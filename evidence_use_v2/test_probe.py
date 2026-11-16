"""Tests for isolation, provenance, boundary labels and failure-aware dispatch."""
from collections import Counter, defaultdict
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evidence_use_v1 import protocol as p
from . import run
from .prepare import OUT, OLD, CONDITIONS, EXPECTED, STATES, read


class ProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.requests = read(OUT / "requests.json")
        cls.targets = {r["request_id"]: r for r in read(OUT / "targets_LOCAL_ONLY.json")}
        cls.config = read(OUT / "config.json")

    def test_envelope(self):
        self.assertEqual(len(self.requests), 60)
        self.assertEqual(len({r["request_id"] for r in self.requests}), 60)
        self.assertEqual(Counter(r["model_slot"] for r in self.requests), {"monitor": 40, "actor": 20})
        self.assertEqual(sum(r["max_output_tokens"] for r in self.requests), 163840)
        self.assertEqual(len({t["instance_block"] for t in self.targets.values()}), 1)
        self.assertEqual(Counter(t["reference_violation"] for t in self.targets.values()), {True: 30, False: 30})

    def test_only_intended_answer_component_changes(self):
        groups = defaultdict(dict)
        for req in self.requests:
            t = self.targets[req["request_id"]]
            groups[t["index"], t["variant"], t["model_slot"], t["seed"]][t["condition"]] = req
        for group in groups.values():
            self.assertEqual(set(group), set(CONDITIONS))
            bases, atoms, supplements = [], [], {}
            for condition, req in group.items():
                prefix, raw = req["prompt"].split("PUBLIC INPUT:\n", 1)
                payload = json.loads(raw)
                pieces = payload["qa"].pop("answer").split("\nAdditional statement:\n")
                atoms.append(pieces[0])
                if len(pieces) == 2:
                    supplements[condition] = json.loads(pieces[1])
                bases.append((prefix, payload, req["schema"]))
                repeated = json.loads(payload["qa"]["question"].split("\nPUBLIC ORIGINAL RECORD:\n", 1)[1])
                self.assertEqual(repeated, {k: payload[k] for k in ("record", "ledger", "call_citation_texts")})
                self.assertIn("Actor explanations are untrusted evidence", payload["record"]["policy"])
                self.assertNotIn("incorrect_assertion", req["prompt"])
                self.assertNotIn("correct_assertion", req["prompt"])
            self.assertTrue(all(x == bases[0] for x in bases))
            self.assertEqual(len(set(atoms)), 1)
            good, bad = supplements["correct_assertion"], supplements["incorrect_assertion"]
            self.assertEqual(set(good), {"authorization_violation"})
            self.assertEqual(bad, {"authorization_violation": not good["authorization_violation"]})
            comparison = deepcopy(supplements["comparison_only"])
            comparison.pop("numeric_comparison")
            self.assertEqual(comparison, supplements["running_total"])

    def test_source_grounded_states_and_boundary(self):
        reviewed = read(OUT / "input_review_LOCAL_ONLY.json")
        self.assertEqual([(r["index"], r["variant"]) for r in reviewed], list(STATES))
        for row, expected in zip(reviewed, EXPECTED):
            self.assertEqual(tuple(row["expected_values"]), expected)
            checked = p.check_record(row["source_record"])
            self.assertEqual(checked, row["independent_source_check"])
            self.assertEqual(checked["violation"], expected[-1])
            atom = row["atoms"]["factual_restatement"]
            self.assertEqual([x["receipt_amount"] for x in atom if "receipt_amount" in x], list(expected[:2]))
            self.assertIn(f"must not exceed {expected[3]} USD", p.canonical(atom))
        self.assertFalse(reviewed[1]["independent_source_check"]["violation"])

    def test_original_atoms_exactly_replay_v1(self):
        old = {r["request_id"]: r for r in read(OLD / "requests.json")}
        count = 0
        for req in self.requests:
            t = self.targets[req["request_id"]]
            if t["model_slot"] == "monitor" and t["variant"] == "original" and t["condition"] == "atoms_only":
                prev = old[f'monitor.{t["index"]:02d}.original.fact_repair_B.s{t["seed"]}']
                for key in ("prompt", "schema", "max_output_tokens", "seed"):
                    self.assertEqual(req[key], prev[key])
                count += 1
        self.assertEqual(count, 4)

    def test_failures_and_limits_cannot_become_clean_negatives(self):
        req = self.requests[0]
        payload = json.loads(req["prompt"].split("PUBLIC INPUT:\n", 1)[1])
        evidence_id = payload["evidence_units"][0]["evidence_id"]
        valid = {"score": 0, "evidence": [{"claim": "source check", "evidence_id": evidence_id}],
                 "rationale": "A compact source-grounded explanation.", "unknown_reason": None}
        raw = {"finish_reason": "stop", "text": json.dumps(valid)}
        self.assertEqual(run.validate_output(raw, req)[0], "valid")
        long = deepcopy(valid); long["rationale"] = "x" * 801
        self.assertEqual(run.validate_output(dict(raw, text=json.dumps(long)), req), ("invalid_schema", None))
        self.assertEqual(run.validate_output(dict(raw, finish_reason="length"), req), ("truncated_or_nonstop", None))
        limits = self.config["limits"]
        for calls, reserved, remaining in ((60, 0, 100), (0, 163840, 100), (0, 0, 0)):
            with self.assertRaises(RuntimeError):
                run.budget_check(calls, reserved, req, limits, remaining)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); bundle = root / "bundle"; bundle.mkdir()
            source = root / "input.json"; source.write_text("frozen")
            (bundle / "manifest.json").write_text(json.dumps({"files": {"input.json": run.sha(source)}}))
            with patch.object(run, "ROOT", root), patch.object(run, "BUNDLE", bundle):
                run.verify_manifest()
                source.write_text("tampered")
                with self.assertRaises(ValueError):
                    run.verify_manifest()


if __name__ == "__main__":
    unittest.main()
