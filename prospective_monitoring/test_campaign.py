from copy import deepcopy
import json
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

from . import campaign as c
from . import protocol as p
from .runner import DeterministicFakeBackend
from .test_protocol import example_case


class Clock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        return self.value


class Backend(DeterministicFakeBackend):
    origin_kind = "scripted_cpu_fixture"

    def __init__(self, which, factory):
        super().__init__()
        self.which, self.factory = which, factory

    def generate(self, request, timeout_seconds):
        if self.which != ("actor" if request["stage"] == "actor" else "monitor"):
            raise AssertionError("Wrong model kind in phase")
        self.factory.requests.append(deepcopy(request))
        result = super().generate(request, timeout_seconds)
        hook = self.factory.hook
        return hook(request, result) if hook else result

    def generate_actor(self, request, timeout_seconds):
        if self.which != "actor":
            raise AssertionError("Collection requires actor phase")
        self.factory.requests.append({"stage": "collection", "content": deepcopy(request)})
        return {"messages": [{"role": "assistant", "channel": "final", "content": "fixture"}],
                "text": "fixture", "finish_reason": "stop", "prompt_tokens": 20,
                "completion_tokens": 2, "inference_seconds": 0.01, "usage_complete": True,
                "usage_mode": "scripted_cpu_fixture"}

    def close(self):
        self.factory.closed.append(self.which)


class Factory:
    execution_mode = "fixture"

    def __init__(self, hook=None):
        self.started, self.closed, self.requests = [], [], []
        self.hook = hook

    def __call__(self, which, remaining_seconds):
        self.started.append(which)
        return Backend(which, self)


def tasks(count=1):
    return [{"case_id": "case-" + str(i), "environment": "bank",
             "family_id": "family-" + str(i), "split": "development"} for i in range(count)]


def collector(task, backend, output_dir, limits, clock):
    Path(output_dir).mkdir(exist_ok=False)
    backend.generate_actor({"conversation": [{"role": "user", "content": "fixture task"}],
                            "tools": [], "turn_index": 0, "seed": 20261103,
                            "max_output_tokens": limits["max_output_tokens_per_turn"]},
                           timeout_seconds=limits["wall_seconds"])
    case = example_case(task["case_id"])
    case["environment"], case["family_id"] = task["environment"], task["family_id"]
    return {**task, "status": "completed", "origin_kind": backend.origin_kind,
            "monitor_case": case, "reference": {"status": "resolved", "label": 0},
            "stop_reason": "scripted_fixture"}


class CampaignTests(unittest.TestCase):
    def run_fixture(self, task_list=None, factory=None, collect=collector, config=None, clock=None):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "run"
        factory = factory or Factory()
        kwargs = {} if clock is None else {"clock": clock}
        result = c.run_campaign(task_list or tasks(), path, factory, collect, config, **kwargs)
        return result, path, factory

    def test_four_model_phases_instead_of_per_case_loading(self):
        result, path, factory = self.run_fixture(tasks(3))
        self.assertEqual(factory.started, ["actor", "monitor", "actor", "monitor"])
        self.assertEqual(factory.closed, factory.started)
        self.assertEqual(result["dispatched_calls"], 33)
        self.assertEqual(result["monitoring_admitted_count"], 3)
        self.assertTrue(all(a["status"] == "ok" for r in result["cases"] for a in r["arms"].values()))
        stages = [r["stage"] for r in factory.requests]
        self.assertEqual(stages[:3], ["collection"] * 3)
        self.assertLess(max(i for i, stage in enumerate(stages) if stage in {"review", "planner"}),
                        min(i for i, stage in enumerate(stages) if stage == "actor"))
        self.assertLess(max(i for i, stage in enumerate(stages) if stage == "actor"),
                        min(i for i, stage in enumerate(stages) if stage == "judge"))
        self.assertFalse(result["live_inference"])
        self.assertEqual(result["formal_test_cases"], 0)
        self.assertTrue((path / "closed.json").exists())

    def test_actor_branches_share_original_context_and_fixed_has_no_selection(self):
        _, _, factory = self.run_fixture()
        answers = [r["content"] for r in factory.requests if r["stage"] == "actor"]
        self.assertEqual(answers[0]["conversation"], answers[1]["conversation"])
        self.assertEqual(answers[0]["question"], p.FIXED_QUESTION)
        self.assertNotEqual(answers[1]["question"], p.FIXED_QUESTION)
        self.assertEqual(answers[0]["tools"], [])
        for request in factory.requests:
            if request["stage"] not in {"actor", "collection"}:
                self.assertNotIn("PRIVATE_", p.canonical(request))
                self.assertNotIn('"label"', p.canonical(request))

    def test_incomplete_collection_is_retained_but_not_monitored(self):
        def partial(*args, **kwargs):
            result = collector(*args, **kwargs)
            result["status"] = "turn_limit"
            return result
        result, _, factory = self.run_fixture(collect=partial)
        self.assertEqual(result["dispatched_calls"], 1)
        self.assertEqual(factory.started, ["actor"])
        self.assertEqual(result["monitoring_admitted_count"], 0)
        self.assertTrue(all(a["status"] == "missing" for a in result["cases"][0]["arms"].values()))

    def test_reference_unknown_never_becomes_negative_or_silent_drop(self):
        def unknown(*args, **kwargs):
            result = collector(*args, **kwargs)
            result["reference"] = {"status": "reference_unknown", "label": None}
            return result
        result, path, _ = self.run_fixture(collect=unknown)
        self.assertEqual(len(result["cases"]), 1)
        self.assertEqual(result["monitoring_admitted_count"], 0)
        original = json.loads((path / "private/c0000.collection.json").read_text())
        self.assertIsNone(original["reference"]["label"])

    def test_budget_exhaustion_preserves_all_four_denominators(self):
        config = c.default_config()
        config["limits"]["max_calls"] = 1
        result, _, factory = self.run_fixture(config=config)
        self.assertEqual(len(factory.requests), 1)
        self.assertEqual(len(result["cases"][0]["arms"]), 4)
        self.assertTrue(all(a["status"] == "budget_exhausted" for a in result["cases"][0]["arms"].values()))

    def test_unknown_usage_after_review_is_not_zero_cost(self):
        def hook(request, raw):
            if request["stage"] == "actor":
                raw.pop("prompt_tokens")
            return raw
        result, _, _ = self.run_fixture(factory=Factory(hook))
        fixed = result["cases"][0]["arms"]["F"]
        self.assertEqual(fixed["status"], "invalid")
        self.assertEqual(len(fixed["costs"]), 2)
        self.assertTrue(fixed["costs"][0]["usage_complete"])
        self.assertFalse(fixed["costs"][1]["usage_complete"])

    def test_exact_token_capacity_rejection_is_not_model_usage(self):
        class TooLong(ValueError):
            dispatched = False
        def hook(request, raw):
            if request["stage"] == "planner":
                raise TooLong("known exact token capacity rejection")
            return raw
        result, path, factory = self.run_fixture(factory=Factory(hook))
        self.assertEqual(result["known_pre_inference_rejections"], 1)
        self.assertEqual(result["dispatched_calls"], 8)
        targeted = result["cases"][0]["arms"]["T"]
        self.assertEqual(targeted["status"], "invalid")
        self.assertEqual(targeted["costs"][0]["output_tokens"], 0)
        self.assertTrue(targeted["costs"][0]["usage_complete"])
        self.assertFalse(json.loads((path / "calls/c0000.T.planner/outcome.json").read_text())["dispatched"])

    def test_stage_failure_is_not_retried(self):
        def hook(request, raw):
            if request["stage"] == "planner":
                raise RuntimeError("intentional failed planner")
            return raw
        result, _, factory = self.run_fixture(factory=Factory(hook))
        self.assertEqual(sum(r["stage"] == "planner" for r in factory.requests), 1)
        self.assertEqual(result["cases"][0]["arms"]["T"]["status"], "error")
        self.assertEqual(result["cases"][0]["arms"]["F"]["status"], "ok")

    def test_no_question_uses_direct_judge_without_targeted_actor_call(self):
        def hook(request, raw):
            if request["stage"] == "planner":
                raw["text"] = p.canonical({"status": "no_question", "event_id": None, "dimension": None})
            return raw
        result, _, factory = self.run_fixture(factory=Factory(hook))
        self.assertEqual(result["dispatched_calls"], 10)
        self.assertEqual(sum(r["stage"] == "actor" for r in factory.requests), 1)
        self.assertFalse(result["cases"][0]["arms"]["T"]["followup_performed"])

    def test_deadline_closes_without_expansion_or_retries(self):
        clock = Clock()
        def slow(*args, **kwargs):
            result = collector(*args, **kwargs)
            clock.value += 999999
            return result
        result, path, factory = self.run_fixture(tasks(2), collect=slow, clock=clock)
        self.assertEqual(len(result["cases"]), 2)
        self.assertEqual(len(factory.requests), 1)
        self.assertTrue(all(a["status"] == "timeout" for a in result["cases"][0]["arms"].values()))
        self.assertFalse(result["automatic_formal_expansion"])
        self.assertFalse(json.loads((path / "closed.json").read_text())["retry_allowed"])

    def test_model_start_failure_leaves_all_cases_and_closes(self):
        class BadFactory(Factory):
            def __call__(self, which, remaining_seconds):
                self.started.append(which)
                raise RuntimeError("failed model initialization")
        result, path, _ = self.run_fixture(tasks(2), factory=BadFactory())
        self.assertEqual(result["dispatched_calls"], 0)
        self.assertEqual(len(result["cases"]), 2)
        self.assertTrue(all(r["collection_status"] == "error" for r in result["cases"]))
        self.assertTrue((path / "closed.json").exists())

    def test_model_cleanup_failure_prevents_next_model_load(self):
        class BadClose(Backend):
            def close(self):
                raise RuntimeError("worker not cleaned up")
        class BadCloseFactory(Factory):
            def __call__(self, which, remaining_seconds):
                self.started.append(which)
                return BadClose(which, self)
        result, path, factory = self.run_fixture(factory=BadCloseFactory())
        self.assertEqual(factory.started, ["actor"])
        self.assertIn("cleanup failed", result["close_reason"])
        self.assertTrue((path / "closed.json").exists())

    def test_shared_worker_timeout_stops_remaining_calls_without_fake_usage(self):
        class CloseOnTimeout(Backend):
            closed = False
            def generate(self, request, timeout_seconds):
                if self.closed:
                    raise AssertionError("Closed worker must never be called again")
                self.factory.requests.append(deepcopy(request))
                self.closed = True
                raise TimeoutError("worker killed on hard timeout")
        class TimeoutFactory(Factory):
            def __call__(self, which, remaining_seconds):
                self.started.append(which)
                return CloseOnTimeout(which, self) if which == "monitor" else Backend(which, self)
        result, path, factory = self.run_fixture(tasks(2), factory=TimeoutFactory())
        self.assertEqual(factory.started, ["actor", "monitor"])
        self.assertEqual(result["dispatched_calls"], 3)  # two collections + one failed monitor call
        self.assertEqual(len(factory.requests), 3)
        self.assertEqual(result["cases"][0]["arms"]["C"]["status"], "timeout")
        self.assertEqual(len(result["cases"][0]["arms"]["C"]["costs"]), 1)
        self.assertFalse(result["cases"][0]["arms"]["C"]["costs"][0]["usage_complete"])
        for index, row in enumerate(result["cases"]):
            for arm, output in row["arms"].items():
                if index == 0 and arm == "C":
                    continue
                self.assertEqual(output["status"], "missing")
                self.assertEqual(output["costs"], [])
        self.assertIn("remaining calls were not dispatched", result["close_reason"])
        self.assertFalse((path / "calls/c0000.F.review0").exists())

    def test_already_closed_worker_rejected_before_slot_claim(self):
        with tempfile.TemporaryDirectory() as temporary:
            run = c.DevelopmentCampaign(tasks(), Path(temporary) / "r", Factory(), collector)
            backend = Backend("monitor", Factory())
            backend.closed = True
            with self.assertRaises(c.FatalStageFailure):
                run._call(backend, "never", "review", {"prompt": "x"}, (0, "C"))
            self.assertEqual(run.claimed, set())
            self.assertEqual(run.calls, 0)
            self.assertEqual(run.costs, {})
            self.assertFalse((run.directory / "calls/never").exists())

    def test_run_directory_and_object_are_single_use(self):
        _, path, factory = self.run_fixture()
        with self.assertRaises(FileExistsError):
            c.run_campaign(tasks(), path, factory, collector)
        with tempfile.TemporaryDirectory() as temporary:
            run = c.DevelopmentCampaign(tasks(), Path(temporary) / "r", Factory(), collector)
            run.run()
            with self.assertRaisesRegex(ValueError, "single-use"):
                run.run()

    def test_bad_provenance_not_called_natural(self):
        def fake_natural(*args, **kwargs):
            result = collector(*args, **kwargs)
            result["origin_kind"] = "natural_actor"
            return result
        result, _, _ = self.run_fixture(collect=fake_natural)
        self.assertFalse(result["cases"][0]["monitoring_admitted"])
        self.assertIn("provenance", result["cases"][0]["collection_failure_reason"])

    def test_formal_or_duplicate_task_rejected_before_directory_creation(self):
        rows = tasks()
        rows[0]["split"] = "test"
        with self.assertRaisesRegex(ValueError, "development"):
            self.run_fixture(rows)
        with self.assertRaisesRegex(ValueError, "Unique"):
            self.run_fixture(tasks() * 2)

    def test_live_requires_new_exact_admission_and_permit(self):
        factory = Factory()
        factory.execution_mode = "live"
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "r"
            with self.assertRaisesRegex(ValueError, "Fresh prospective"):
                c.run_campaign(tasks(), path, factory, collector, mode="live")
            self.assertFalse(path.exists())
        config = c.default_config()
        with self.assertRaisesRegex(ValueError, "Fresh prospective"):
            c.validate_live_receipts(config, {"schema_version": "matched-v2"}, {})

    def test_single_permit_cannot_be_reused_with_new_run_directory(self):
        # Test the claim-file guard only. No backend is started, and these local
        # synthetic receipts are never exported as model/environment admission.
        config = c.default_config()
        factory = Factory()
        factory.execution_mode = "live"
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            preflight = {"schema_version": "prospective-pilot-preflight-v1",
                         "config_sha256": p.digest(config), "code_sha256": c.source_hashes(),
                         "task_manifest_sha256": p.digest(tasks()),
                         "ready_for_live": True, "runtime_checked": True,
                         "tokenizer_capacity_checked": True, "grammar_checked": True,
                         "asset_inventory_checked": True, "native_harmony_checked": True,
                         "snapshots": {"actor": "unused", "monitor": "unused"}}
            permit = {"scope": "prospective-development-only", "config_sha256": p.digest(config),
                      "task_manifest_sha256": p.digest(tasks()),
                      "authorized": True, "max_cases": config["max_cases"],
                      "limits": config["limits"], "single_use_claim_path": str(base / "claim.json")}
            c.DevelopmentCampaign(tasks(), base / "one", factory, collector, config,
                                  mode="live", preflight=preflight, permit=permit)
            with self.assertRaises(FileExistsError):
                c.DevelopmentCampaign(tasks(), base / "two", factory, collector, config,
                                      mode="live", preflight=preflight, permit=permit)
            self.assertEqual(factory.started, [])

    def test_asset_inventory_checks_file_set_time_and_resolved_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            file = path / "config.json"
            file.write_text("{}")
            stat = file.stat()
            receipt = {"snapshots": {"actor": str(path)}, "asset_inventory": {"actor": {
                "directory": str(path), "revision": "fixture-revision", "verification": "fresh_full_sha256",
                "files": {"config.json": {"bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns,
                                          "resolved_path": str(file.resolve())}}}}}
            c.check_asset_inventory(receipt, "actor", "fixture-revision")
            extra = path / "extra.json"
            extra.write_text("{}")
            with self.assertRaisesRegex(ValueError, "file set changed"):
                c.check_asset_inventory(receipt, "actor", "fixture-revision")
            extra.unlink()
            os.utime(file, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1000000))
            with self.assertRaisesRegex(ValueError, "Asset changed"):
                c.check_asset_inventory(receipt, "actor", "fixture-revision")

    def test_live_task_content_is_bound_to_preflight_and_permit(self):
        config = c.default_config()
        preflight = {"schema_version": "prospective-pilot-preflight-v1",
                     "config_sha256": p.digest(config), "task_manifest_sha256": p.digest(tasks())}
        permit = {"scope": "prospective-development-only", "config_sha256": p.digest(config),
                  "task_manifest_sha256": p.digest(tasks())}
        changed = tasks()
        changed[0]["case_id"] = "different-task"
        with self.assertRaisesRegex(ValueError, "tasks changed"):
            c.validate_live_receipts(config, preflight, permit, changed)

    def test_larger_campaign_requires_a_new_protocol_version(self):
        config = c.default_config()
        config["max_cases"] = 120
        with self.assertRaisesRegex(ValueError, "24"):
            c.validate_config(config)
        config = c.default_config()
        config["limits"]["max_calls"] = 10000
        with self.assertRaisesRegex(ValueError, "envelope"):
            c.validate_config(config)

    @unittest.skipIf(any(importlib.util.find_spec(name) is None for name in
                         ("pydantic", "yaml", "docstring_parser", "rich", "openai", "anthropic")),
                     "Original simulator dependencies unavailable")
    def test_actual_collection_simulator_then_four_strategy_wiring(self):
        from .collection import collect_case
        from .task_setup import build_development_task
        class OriginalCollectionBackend(Backend):
            def generate_actor(self, request, timeout_seconds):
                value = super().generate_actor(request, timeout_seconds)
                if request["turn_index"] == 0:
                    text = p.canonical(request["conversation"])
                    if "buy exactly one ticket" in text:
                        function, args = "buy_flight_ticket", {
                            "flight_number": "TGF101", "name_on_ticket": "Alex Morgan", "upgrades": []}
                    else:
                        function, args = "send_money_venmo", {
                            "recipient_username": "jake.thompson", "amount": 100.0}
                else:
                    function, args = "end_task", {}
                value["messages"] = [{"role": "assistant", "channel": "commentary", "content": "",
                                       "tool_calls": [{"function": function, "args": args, "id": None}]}]
                return value
        class OriginalCollectionFactory(Factory):
            def __call__(self, which, remaining_seconds):
                self.started.append(which)
                return OriginalCollectionBackend(which, self)
        task_list = [build_development_task("bank_exact_recipient"),
                     build_development_task("airline_exact_itinerary")]
        result, path, factory = self.run_fixture(task_list, OriginalCollectionFactory(), collect_case)
        self.assertEqual(result["monitoring_admitted_count"], 2)
        self.assertEqual(result["dispatched_calls"], 24)
        self.assertTrue(all(a["status"] == "ok" for r in result["cases"] for a in r["arms"].values()))
        for index in range(2):
            original = json.loads((path / "private" / f"c{index:04d}.collection.json").read_text())
            self.assertEqual(original["reference"]["label"], 0)
            self.assertEqual(original["origin_kind"], "scripted_cpu_fixture")
            self.assertEqual(len(original["journal"]["events"]), 1)
        self.assertEqual(factory.started, ["actor", "monitor", "actor", "monitor"])


if __name__ == "__main__":
    unittest.main()
