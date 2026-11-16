"""No-model checks for causal isolation, immutable inputs, caps, and stop rules."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from airline_dev_v1.fixture import Factory
from prospective_monitoring.campaign import FatalStageFailure
from . import protocol as p
from . import prepare as prep
from .campaign import Campaign
from .report import analyze, report


class DiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.bundle = Path(cls.tmp.name) / "bundle"
        prep.prepare(cls.bundle, prep.OUTPUT / "AUTHORIZATION.json")
        cls.cfg, cls.cases, _ = prep.load_bundle(cls.bundle)
        cls.refs = prep.read(cls.bundle / "references_PRIVATE.json")
        cls.factory = Factory()
        cls.fixture_dir = Path(cls.tmp.name) / "fixture"
        cls.result = Campaign(cls.bundle, cls.fixture_dir, cls.factory).run()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_all_slots_and_actual_seed_wiring(self):
        self.assertEqual(self.result["dispatched_calls"], 288)
        self.assertEqual(len(self.result["cases"]), 48)
        self.assertEqual(self.factory.started, ["monitor", "actor", "monitor"])
        self.assertEqual(self.factory.closed, self.factory.started)
        for seed in p.SEEDS:
            requests = [r for r in self.factory.requests if r["seed"] == seed]
            self.assertEqual(len(requests), 144)
            self.assertEqual(sum(r["stage"] == "judge" for r in requests), 72)
            self.assertEqual(sum(r["stage"] == "actor" for r in requests), 48)
            self.assertEqual(sum(r["stage"] == "review" for r in requests), 24)
        for f in (self.fixture_dir / "calls").iterdir():
            archived = prep.read(f / "request.json")["request"]
            i = int(f.name[1:5])
            self.assertEqual(archived["seed"], self.result["cases"][i]["seed"])
        self.assertEqual(sum(r["max_output_tokens"] for r in self.factory.requests), 786432)
        self.assertEqual(sum(r["model"] == self.cfg["models"]["monitor"] for r in self.factory.requests), 192)

    def test_label_free_shared_anchor_and_isolation(self):
        for case in self.cases:
            a = p.anchor(case)
            successes = [e for e in case["ledger"] if e["tool"] == "buy_flight_ticket" and e["question_candidate"]]
            target = successes[0] if case["family_id"] == "airline_forward_change_cancel" else successes[-1]
            self.assertEqual(a, {k: target[k] for k in ("call_source", "result_source")})
            notes = [{"notes": []}]
            prompts = [p.judge_prompt(case, "A", notes=notes)]
            for arm in ("B", "C"):
                q = p.question(case, arm)
                req = p.actor_request(case, q)
                self.assertEqual(req["conversation"], case["conversation"])
                self.assertEqual(req["tools"], [])
                req["conversation"].append({"role": "user", "content": "mutated branch"})
                self.assertNotEqual(req["conversation"], p.actor_request(case, q)["conversation"])
                prompts.append(p.judge_prompt(case, arm, qa={"question": q, "answer": "fixture"}))
                wrong = "C" if arm == "B" else "B"
                with self.assertRaises(ValueError):
                    p.judge_prompt(case, wrong, qa={"question": q, "answer": "fixture"})
            payloads = [json.loads(x.split("PUBLIC INPUT:\n", 1)[1]) for x in prompts]
            for data in payloads:
                self.assertEqual(data["marked_operation"], a)
                self.assertEqual(data["record"], case["public"])
                self.assertEqual(data["evidence_units"], p.evidence_units(case))
                self.assertFalse(set(data) & {"arm", "seed", "case_id", "label", "condition", "family_id", "old_score", "conversation"})
            self.assertEqual(len({x.split("PUBLIC INPUT:\n", 1)[0] for x in prompts}), 1)

    def test_failed_worker_retains_every_unstarted_position(self):
        def fail(backend, request, raw):
            backend.closed = True
            raise TimeoutError("fixture hard failure")
        factory = Factory(fail)
        run = Path(self.tmp.name) / "failure"
        result = Campaign(self.bundle, run, factory).run()
        counts = [v["status"] for r in result["cases"] for v in r["arms"].values()]
        self.assertEqual(len(counts), 144)
        self.assertEqual(counts.count("missing"), 143)
        self.assertEqual(counts.count("timeout"), 1)
        self.assertEqual(result["dispatched_calls"], 1)
        self.assertEqual(factory.started, ["monitor"])
        self.assertEqual(result["output_tokens_or_failed_reserve"], 2048)

    def synthetic_rows(self):
        return [{"case_id": r["case_id"], "seed": s, "arm": a, "status": "ok", "score": 90 if r["label"] else 0,
            "costs": [{"model": self.cfg["models"][m], "input_tokens": 100, "output_tokens": 10,
                       "inference_seconds": 1, "usage_complete": True} for m in (["monitor", "monitor"] if a == "A" else ["actor", "monitor"])]}
            for r in self.refs for s in p.SEEDS for a in p.ARMS]

    def test_gates_ceiling_and_real_stable_improvement(self):
        rows = self.synthetic_rows()
        self.assertEqual(analyze(rows, self.refs, self.cfg)["decision"], "controls_at_ceiling_dataset_nondiscriminating_stop")
        positives = [r for r in self.refs if r["label"]]
        picked = []
        for ref in positives:
            if all(x["family_id"] != ref["family_id"] for x in picked):
                picked.append(ref)
            if len(picked) == 2:
                break
        chosen = {r["case_id"] for r in picked}
        for row in rows:
            if row["case_id"] in chosen and row["arm"] in {"A", "B"}:
                row["score"] = 0
        self.assertTrue(analyze(rows, self.refs, self.cfg)["numerical_candidate"])
        broken = deepcopy(rows)
        next(r for r in broken if r["case_id"] in chosen and r["arm"] == "B" and r["seed"] == 29)["score"] = 90
        self.assertFalse(analyze(broken, self.refs, self.cfg)["numerical_candidate"])
        bad_fp = deepcopy(rows)
        negative = next(r["case_id"] for r in self.refs if not r["label"])
        next(r for r in bad_fp if r["case_id"] == negative and r["arm"] == "C")["score"] = 90
        self.assertFalse(analyze(bad_fp, self.refs, self.cfg)["resource_gates"]["no_new_false_alarms"])
        costly = deepcopy(rows)
        for row in costly:
            if row["arm"] == "C":
                row["costs"][0]["output_tokens"] *= 2
        self.assertFalse(analyze(costly, self.refs, self.cfg)["resource_gates"]["per_model_costs_within_110_percent"])
        incomplete = deepcopy(rows)
        incomplete[0].update(status="unknown", score=None)
        self.assertEqual(analyze(incomplete, self.refs, self.cfg)["decision"], "inconclusive_stop_no_rerun")
        with self.assertRaises(ValueError):
            analyze(rows[:-1], self.refs, self.cfg)

    def test_fixture_cannot_be_reported_as_model_evidence(self):
        with self.assertRaisesRegex(ValueError, "Bound live"):
            report(self.bundle, self.fixture_dir)

    def test_one_shot_submission_claim_consumed_on_ambiguous_response(self):
        from . import submit
        where = Path(self.tmp.name) / "submission"
        where.mkdir()
        with patch.object(submit, "ROOT", where), patch.object(submit, "REMOTE_ROOT", where), \
             patch.dict("os.environ", {"USER": "cpsc4880_rz377"}), \
             patch.object(submit.subprocess, "run", side_effect=TimeoutError("ambiguous")) as invoke:
            receipt = submit.submit(self.bundle)
            self.assertEqual(receipt["status"], "submission_outcome_unknown")
            with self.assertRaises(FileExistsError):
                submit.submit(self.bundle)
            self.assertEqual(invoke.call_count, 1)


if __name__ == "__main__":
    unittest.main()
