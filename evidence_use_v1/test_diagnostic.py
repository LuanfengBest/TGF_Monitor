"""Offline checks for coherent intervention, prompt isolation and resource limits."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from . import protocol as p
from .run import budget_check, validate_output

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "project/evidence_use_diagnostic_2026-11-07"


class DiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.requests = json.loads((BUNDLE / "requests.json").read_text())
        cls.targets = {r["request_id"]: r for r in json.loads((BUNDLE / "targets_LOCAL_ONLY.json").read_text())}
        cls.cfg = json.loads((BUNDLE / "config.json").read_text())

    def test_positions_and_reserve(self):
        self.assertEqual(len(self.requests), 136)
        self.assertEqual(len({r["request_id"] for r in self.requests}), 136)
        self.assertEqual(sum(r["max_output_tokens"] for r in self.requests), 323584)
        self.assertEqual(sum(r["model_slot"] == "monitor" for r in self.requests), 114)

    def test_source_cards_and_coherent_interventions(self):
        labels = {}
        for req in self.requests:
            target = self.targets[req["request_id"]]
            data = json.loads(req["prompt"].split("PUBLIC INPUT:\n", 1)[1])
            checked = p.check_record(data["record"])
            self.assertEqual(checked["violation"], target["reference_violation"])
            labels[(target["index"], target["variant"])] = checked["violation"]
            self.assertNotIn("reference_violation", data)
            self.assertNotIn("reference_label", json.dumps(data))
            if target["condition"] == "source_card":
                cards = json.loads(data["qa"]["answer"])["original_source_excerpts"]
                for card in cards:
                    self.assertIn(card["quote"], p.sources(data["record"])[card["source_id"]]["text"])
                question_record = json.loads(data["qa"]["question"].split("\nPUBLIC ORIGINAL RECORD:\n", 1)[1])
                self.assertEqual(question_record["record"], data["record"])
        for index in p.INDICES:
            self.assertEqual(labels[(index, "original")], labels[(index, "irrelevant")])
            if index not in (0, 1):
                self.assertNotEqual(labels[(index, "original")], labels[(index, "critical")])
        self.assertEqual({i: labels[(i, "critical")] for i in (2, 3, 4, 5, 10, 11)},
                         {2: False, 3: True, 4: False, 5: True, 10: False, 11: True})

    def test_readout_and_failure_status(self):
        req = self.requests[0]
        unit = json.loads(req["prompt"].split("PUBLIC INPUT:\n", 1)[1])["evidence_units"][0]["evidence_id"]
        value = {"score": 0, "evidence": [{"claim": "A test claim.", "evidence_id": unit}], "rationale": "Test only.", "unknown_reason": None}
        if req["explicit_verdict"]:
            value["authorization_violation"] = False
        raw = {"text": json.dumps(value), "finish_reason": "stop"}
        self.assertEqual(validate_output(raw, req)[0], "valid")
        raw["finish_reason"] = "length"
        self.assertEqual(validate_output(raw, req)[0], "truncated_or_nonstop")
        raw.update(finish_reason="stop", text='{"score":0}')
        self.assertEqual(validate_output(raw, req)[0], "invalid_schema")
        value["evidence"][0]["evidence_id"] = "not-an-original-source"
        raw["text"] = json.dumps(value)
        self.assertEqual(validate_output(raw, req)[0], "invalid_schema")

    def test_budget_stops_before_dispatch(self):
        req = self.requests[0]
        limits = self.cfg["limits"]
        budget_check(0, 0, req, limits, 60)
        for calls, reserve, remaining in ((136, 0, 60), (0, 323584, 60), (0, 0, 0)):
            with self.assertRaises(RuntimeError):
                budget_check(calls, reserve, req, limits, remaining)

    def test_cancellation_does_not_erase_budget(self):
        req = next(r for r in self.requests if r["request_id"] == "monitor.05.original.source_card.s17")
        record = json.loads(req["prompt"].split("PUBLIC INPUT:\n", 1)[1])["record"]
        result = p.check_record(record)
        self.assertEqual([r["gross"] for r in result["operations"]], ["170.00", "170.00", "350.00"])
        broken = deepcopy(record)
        next(m for m in broken["messages"] if m["source_id"] == "m00006")["content"] = next(m for m in record["messages"] if m["source_id"] == "m00006")["content"].replace("350.00", "349.00")
        self.assertTrue(p.check_record(broken)["violation"])


if __name__ == "__main__":
    unittest.main()
