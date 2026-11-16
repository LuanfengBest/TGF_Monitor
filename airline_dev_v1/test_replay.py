from copy import deepcopy
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import tempfile
import unittest

from . import protocol as p
from .prepare import prepare, load_bundle, read, sha
from .campaign import ReplayCampaign, validate_receipts
from .fixture import Factory
from .native_backend import ProcessStage, Stage
from .preflight import examples
from .report import predictions, analyze


class ReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.bundle = cls.root / "bundle"
        prepare(cls.bundle)
        cls.cfg, cls.cases, cls.manifest = load_bundle(cls.bundle)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def campaign(self, name, hook=None):
        factory = Factory(hook)
        runner = ReplayCampaign(self.bundle, self.root / name, factory)
        return runner, factory

    def test_cohort_preserves_all_records_and_labels(self):
        refs = read(self.bundle / "references_PRIVATE.json")
        self.assertEqual(len(refs), 24)
        self.assertEqual(sum(r["label"] for r in refs), 6)
        self.assertEqual(len({r["instance_id"] for r in refs}), 12)
        self.assertEqual(len({r["family_id"] for r in refs}), 3)
        self.assertFalse(self.manifest["original_combined_screen_passed"])

    def test_ids_reconstruct_exact_public_source_not_entailment(self):
        for case in self.cases:
            sources = p.base.quote_sources(case["public"])
            for unit in p.evidence_units(case):
                self.assertEqual(unit["text"], sources[unit["source_id"]]["text"][unit["start"]:unit["end"]])
                # Location validation deliberately cannot make a false claim true.
                parsed = p.review(p.canonical({"notes": [{"claim": "Unsupported assertion for test only", "evidence_id": unit["evidence_id"]}]}), case)
                self.assertEqual(parsed["notes"][0]["quote"], unit["text"])
        with self.assertRaises(ValueError):
            p.review('{"notes":[{"claim":"x","evidence_id":"not-in-source"}]}', self.cases[0])
        with self.assertRaises(ValueError):
            p.review('{"notes":[{"claim":"x","evidence_id":"u0000","label":1}]}', self.cases[0])

    def test_private_canaries_excluded_and_questions_isolated(self):
        original = self.cases[0]
        history = deepcopy(original["conversation"])
        history[0]["content"] += " PRIVATE_SYSTEM_CANARY_7754"
        history.append({"role": "assistant", "channel": "analysis", "content": "PRIVATE_COT_CANARY_7754"})
        case = p.prepare_case(original["case_id"], "airline", original["family_id"], history, original["public"]["policy"])
        text = p.review_prompt(case) + p.judge_prompt(case, "P") + p.planner_prompt(case)
        self.assertNotIn("PRIVATE_SYSTEM_CANARY_7754", text)
        self.assertNotIn("PRIVATE_COT_CANARY_7754", text)
        fixed = p.actor_request(case, p.FIXED_QUESTION)
        event = next(e for e in case["ledger"] if e["question_candidate"])
        selected = {"status": "selected", "event_id": event["event_id"], "dimension": "authority_scope"}
        targeted = p.actor_request(case, p.targeted_question(case, selected))
        self.assertEqual(fixed["conversation"], targeted["conversation"])
        self.assertEqual(fixed["original_context_sha256"], targeted["original_context_sha256"])
        self.assertEqual(fixed["tools"], [])
        with self.assertRaises(ValueError):
            p.judge_prompt(case, "T", selected=selected, qa={"question": p.FIXED_QUESTION, "answer": "Cross-arm contamination"})

    def test_full_wiring_240_calls_three_phases_zero_collection(self):
        runner, factory = self.campaign("full")
        summary = runner.run()
        self.assertEqual(summary["dispatched_calls"], 240)
        self.assertEqual(factory.started, ["monitor", "actor", "monitor"])
        self.assertEqual(factory.closed, factory.started)
        self.assertEqual(sum(r["stage"] == "actor" for r in factory.requests), 48)
        self.assertTrue(all(o["status"] == "ok" for c in summary["cases"] for o in c["arms"].values()))
        self.assertEqual(summary["environment_tool_calls"], 0)
        self.assertFalse(summary["live_inference"])
        with self.assertRaises(ValueError):
            runner.run()
        with self.assertRaises(FileExistsError):
            ReplayCampaign(self.bundle, runner.directory, Factory())
        with self.assertRaisesRegex(ValueError, "Fixture"):
            predictions(self.bundle, runner.directory)
        with self.assertRaises(PermissionError):
            runner._collect(None)
        with self.assertRaises(PermissionError):
            runner._call(None, "bad", "collection", {}, (0, "P"))

    def test_all_generated_prompts_match_new_schemas(self):
        import jsonschema
        actor, monitor = examples(self.cases, self.cfg)
        factory = Factory()
        backend = factory("monitor", 10)
        for ex in monitor:
            raw = backend.generate({"stage": ex["stage"], "content": {"prompt": ex["prompt"]}}, 10)
            jsonschema.validate(json.loads(raw["text"]), p.output_schema(ex["stage"], ex["prompt"]))
        self.assertEqual({a["case_id"] for a in actor}, {c["case_id"] for c in self.cases})
        self.assertTrue(all(a["tools"] == [] for a in actor))

    def test_no_question_preserves_T_and_skips_only_T_actor(self):
        def hook(_, req, raw):
            if req["stage"] == "planner":
                raw["text"] = p.canonical({"status": "no_question", "event_id": None, "dimension": None})
            return raw
        runner, factory = self.campaign("no_question", hook)
        summary = runner.run()
        self.assertEqual(summary["dispatched_calls"], 216)
        self.assertEqual(sum(r["stage"] == "actor" for r in factory.requests), 24)
        self.assertTrue(all(r["arms"]["T"]["status"] == "ok" and not r["arms"]["T"]["followup_performed"] for r in summary["cases"]))

    def test_bad_review_is_not_retried_or_converted_to_score(self):
        def hook(_, req, raw):
            if req["stage"] == "review":
                raw["text"] = '{"notes":[{"claim":"bad","evidence_id":"invented"}]}'
            return raw
        runner, factory = self.campaign("bad_reviews", hook)
        summary = runner.run()
        self.assertEqual(summary["dispatched_calls"], 144)
        for row in summary["cases"]:
            for arm in ("C", "F"):
                self.assertEqual(row["arms"][arm]["status"], "invalid")
                self.assertIsNone(row["arms"][arm]["score"])
            self.assertEqual(row["arms"]["P"]["status"], "ok")
            self.assertEqual(row["arms"]["T"]["status"], "ok")

    def test_budget_exhaustion_retains_all_96_slots(self):
        runner, factory = self.campaign("budget")
        runner.config["limits"]["max_calls"] = 2  # Deliberate fixture-only injected failure.
        summary = runner.run()
        self.assertEqual(summary["dispatched_calls"], 2)
        self.assertEqual(sum(len(r["arms"]) for r in summary["cases"]), 96)
        self.assertTrue(all(o["score"] is None for r in summary["cases"] for o in r["arms"].values()))
        self.assertEqual(len(factory.requests), 2)

    def test_dead_worker_stops_other_phases_unknown_cost_preserved(self):
        def hook(backend, req, raw):
            backend.closed = True
            raise TimeoutError("injected worker failure")
        runner, factory = self.campaign("dead_worker", hook)
        summary = runner.run()
        self.assertEqual(factory.started, ["monitor"])
        self.assertEqual(summary["dispatched_calls"], 1)
        costs = [c for r in summary["cases"] for o in r["arms"].values() for c in o["costs"]]
        self.assertEqual(len(costs), 1)
        self.assertFalse(costs[0]["usage_complete"])
        self.assertEqual(sum(o["status"] == "missing" for r in summary["cases"] for o in r["arms"].values()), 95)

    def test_failure_aware_metric_denominator_and_no_false_candidate(self):
        contract = read(self.bundle / "contract.json")
        refs, public = read(self.bundle / "references_PRIVATE.json"), read(self.bundle / "public_inputs.json")
        rows = [{"case_id": r["case_id"], "arm": a, "status": "missing", "score": None,
                 "contract_sha256": p.digest(contract), "input_sha256": r["input_sha256"],
                 "costs": [], "cost_complete": False, "followup_performed": False} for r in refs for a in p.ARMS]
        result = analyze(contract, refs, rows, public)
        self.assertFalse(result["primary_T_vs_F"]["numerical_candidate_only"])
        for arm in p.ARMS:
            self.assertEqual(result["groups"]["all"][arm]["positive_references"], 6)
            self.assertEqual(result["groups"]["all"][arm]["all_cases"], 24)
            self.assertEqual(result["groups"]["all"][arm]["all_resolved_denominator"]["fpr_bounds_if_unscored_negatives_are_unresolved"], [0, 1])
        rows[0]["score"] = 50
        with self.assertRaises(ValueError):
            analyze(contract, refs, rows, public)

    def test_fresh_scope_budget_hash_and_single_use_required(self):
        with self.assertRaises(ValueError):
            validate_receipts(self.bundle, {}, {"scope": "collection-only"})
        preflight = {"schema_version": "airline-replay-preflight-v1", "bundle_manifest_sha256": sha(self.bundle / "manifest.json"),
                     "completed_at_utc": datetime.now(timezone.utc).isoformat(),
                     **{k: True for k in ("ready_for_live", "runtime_checked", "tokenizer_capacity_checked", "grammar_checked", "asset_hashes_checked")}}
        permit = {"schema_version": "airline-replay-permit-v1", "scope": self.cfg["scope"],
                  "bundle_manifest_sha256": sha(self.bundle / "manifest.json"), "preflight_sha256": p.digest(preflight),
                  "authorized_limits": self.cfg["limits"], "resource_envelope": self.cfg["resource_envelope"],
                  "user_authorization": "unit test only; not a real permit", "new_environment_episodes": 0,
                  "environment_tool_calls": 0, "single_use_claim_path": str(self.root / "claim")}
        validate_receipts(self.bundle, preflight, permit)
        tampered = deepcopy(permit)
        tampered["authorized_limits"]["max_calls"] += 1
        with self.assertRaises(ValueError):
            validate_receipts(self.bundle, preflight, tampered)
        old = deepcopy(preflight)
        old["completed_at_utc"] = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        with self.assertRaises(ValueError):
            validate_receipts(self.bundle, old, {**permit, "preflight_sha256": p.digest(old)})
        Path(permit["single_use_claim_path"]).touch()
        with self.assertRaises(ValueError):
            validate_receipts(self.bundle, preflight, permit)
        with self.assertRaises(PermissionError):
            ProcessStage("monitor", self.cfg, "/unused", permit_live=False, startup_timeout_seconds=1)

    def test_bundle_tamper_detected(self):
        file = self.bundle / "config.json"
        before = file.read_bytes()
        try:
            file.write_bytes(before + b" ")
            with self.assertRaises(ValueError):
                load_bundle(self.bundle)
        finally:
            file.write_bytes(before)


if __name__ == "__main__":
    unittest.main()
