from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from . import protocol as p
from .runner import DeterministicFakeBackend, OfflineRun, default_config, run_offline
from .test_protocol import example_case


class FakeClock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        return self.value


class RunnerTests(unittest.TestCase):
    def run_case(self, backend=None, config=None, cases=None, clock=None):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "run"
        kwargs = {} if clock is None else {"clock": clock}
        backend = backend or DeterministicFakeBackend()
        result = run_offline(cases or [example_case()], path, backend, config, **kwargs)
        return result, path, backend

    def test_all_four_strategies_with_simulated_usage(self):
        result, path, backend = self.run_case()
        arms = result["cases"][0]["arms"]
        self.assertEqual(set(arms), set(p.ARMS))
        self.assertTrue(all(arm["status"] == "ok" for arm in arms.values()))
        self.assertEqual(result["dispatched_calls"], 10)
        self.assertEqual([len(arms[arm]["costs"]) for arm in p.ARMS], [1, 3, 3, 3])
        self.assertFalse(result["live_inference"])
        for request in backend.requests:
            if request["stage"] != "actor":
                self.assertNotIn("PRIVATE_", p.canonical(request))
        actor_requests = [r for r in backend.requests if r["stage"] == "actor"]
        self.assertEqual(len(actor_requests), 2)
        self.assertEqual(actor_requests[0]["content"]["conversation"], actor_requests[1]["content"]["conversation"])
        self.assertEqual(actor_requests[0]["content"]["question"], p.FIXED_QUESTION)
        self.assertNotEqual(actor_requests[1]["content"]["question"], p.FIXED_QUESTION)
        archived = json.loads((path / "calls/c0000.F.actor/request.json").read_text())
        self.assertNotIn("conversation", archived["request"]["content"])
        self.assertEqual(len(archived["request_sha256"]), 64)

    def test_run_directory_is_single_use(self):
        _, path, _ = self.run_case()
        with self.assertRaises(FileExistsError):
            run_offline([example_case()], path, DeterministicFakeBackend())

    def test_live_backend_and_live_flag_are_rejected(self):
        backend = DeterministicFakeBackend()
        backend.offline = False
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "offline"):
                run_offline([example_case()], Path(directory) / "x", backend)
            config = default_config()
            config["live_enabled"] = True
            with self.assertRaisesRegex(ValueError, "offline"):
                run_offline([example_case()], Path(directory) / "x", DeterministicFakeBackend(), config)

    def test_backend_failure_is_not_retried_and_other_arms_remain(self):
        class FailureBackend(DeterministicFakeBackend):
            def generate(self, request, timeout_seconds):
                if request["stage"] == "planner":
                    self.requests.append(deepcopy(request))
                    raise RuntimeError("fixture backend failure")
                return super().generate(request, timeout_seconds)
        result, path, backend = self.run_case(FailureBackend())
        arms = result["cases"][0]["arms"]
        self.assertEqual(arms["T"]["status"], "error")
        self.assertEqual(sum(r["stage"] == "planner" for r in backend.requests), 1)
        self.assertEqual(len(arms), 4)
        self.assertFalse(arms["T"]["costs"][0]["usage_complete"])
        self.assertTrue((path / "calls/c0000.T.planner/outcome.json").exists())

    def test_deadline_retains_all_cases_and_blocks_later_calls(self):
        clock = FakeClock()
        class SlowBackend(DeterministicFakeBackend):
            def generate(self, request, timeout_seconds):
                answer = super().generate(request, timeout_seconds)
                clock.value += timeout_seconds + 1
                return answer
        result, _, backend = self.run_case(SlowBackend(), cases=[example_case("one"), example_case("two")], clock=clock)
        self.assertEqual(len(backend.requests), 1)
        self.assertEqual(len(result["cases"]), 2)
        self.assertTrue(all(arm["status"] == "timeout" for row in result["cases"] for arm in row["arms"].values()))

    def test_call_budget_keeps_missing_arms_in_denominator(self):
        config = default_config()
        config["limits"]["max_calls"] = 1
        result, _, backend = self.run_case(config=config)
        self.assertEqual(len(backend.requests), 1)
        self.assertEqual(result["cases"][0]["arms"]["P"]["status"], "ok")
        self.assertTrue(all(result["cases"][0]["arms"][arm]["status"] == "budget_exhausted" for arm in ("C", "F", "T")))

    def test_bad_actor_channel_is_invalid_not_followup_evidence(self):
        class AnalysisBackend(DeterministicFakeBackend):
            def generate(self, request, timeout_seconds):
                value = super().generate(request, timeout_seconds)
                if request["stage"] == "actor":
                    value["channel"] = "analysis"
                return value
        result, _, _ = self.run_case(AnalysisBackend())
        self.assertEqual(result["cases"][0]["arms"]["F"]["status"], "invalid")
        self.assertEqual(result["cases"][0]["arms"]["T"]["status"], "invalid")

    def test_no_question_fallback_is_counted_without_actor(self):
        class NoQuestionBackend(DeterministicFakeBackend):
            def generate(self, request, timeout_seconds):
                value = super().generate(request, timeout_seconds)
                if request["stage"] == "planner":
                    value["text"] = p.canonical({"status": "no_question", "event_id": None, "dimension": None})
                return value
        result, _, backend = self.run_case(NoQuestionBackend())
        targeted = result["cases"][0]["arms"]["T"]
        self.assertEqual(targeted["status"], "ok")
        self.assertFalse(targeted["followup_performed"])
        self.assertEqual(sum(r["stage"] == "actor" for r in backend.requests), 1)

    def test_tampered_input_rejected_before_directory_creation(self):
        case = example_case()
        case["ledger"][0]["arguments"]["amount"] = 999
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "x"
            with self.assertRaises(ValueError):
                run_offline([case], path, DeterministicFakeBackend())
            self.assertFalse(path.exists())

    def test_duplicate_case_id_rejected(self):
        with self.assertRaisesRegex(ValueError, "unique"):
            self.run_case(cases=[example_case(), example_case()])

    def test_unknown_usage_is_reserved_after_malformed_response(self):
        class BadUsageBackend(DeterministicFakeBackend):
            def generate(self, request, timeout_seconds):
                value = super().generate(request, timeout_seconds)
                if request["stage"] == "review":
                    value["completion_tokens"] = -1
                return value
        result, _, _ = self.run_case(BadUsageBackend())
        for arm in ("C", "F"):
            row = result["cases"][0]["arms"][arm]
            self.assertEqual(row["status"], "invalid")
            self.assertFalse(row["costs"][-1]["usage_complete"])

    def test_bad_actor_usage_after_valid_review_is_charged_unknown(self):
        class BadActorUsage(DeterministicFakeBackend):
            def generate(self, request, timeout_seconds):
                value = super().generate(request, timeout_seconds)
                if request["stage"] == "actor":
                    value.pop("prompt_tokens")
                return value
        result, _, _ = self.run_case(BadActorUsage())
        fixed = result["cases"][0]["arms"]["F"]
        self.assertEqual(fixed["status"], "invalid")
        self.assertEqual(len(fixed["costs"]), 2)
        self.assertTrue(fixed["costs"][0]["usage_complete"])
        self.assertFalse(fixed["costs"][1]["usage_complete"])
        self.assertGreaterEqual(result["output_tokens_or_failed_reserve"], 8192)

    def test_actor_cannot_return_tool_calls(self):
        class ToolActor(DeterministicFakeBackend):
            def generate(self, request, timeout_seconds):
                value = super().generate(request, timeout_seconds)
                if request["stage"] == "actor":
                    value["tool_calls"] = [{"function": "send_money_venmo", "args": {}}]
                return value
        result, _, _ = self.run_case(ToolActor())
        self.assertEqual(result["cases"][0]["arms"]["F"]["status"], "invalid")
        self.assertEqual(result["cases"][0]["arms"]["T"]["status"], "invalid")

    def test_reserved_output_budget_prevents_dispatch(self):
        config = default_config()
        config["limits"]["max_output_tokens"] = 100
        result, _, backend = self.run_case(config=config)
        self.assertEqual(len(backend.requests), 0)
        self.assertTrue(all(arm["status"] == "budget_exhausted"
                            for arm in result["cases"][0]["arms"].values()))

    def test_slot_is_single_use_even_on_same_run_object(self):
        with tempfile.TemporaryDirectory() as directory:
            backend = DeterministicFakeBackend()
            case = example_case()
            run = OfflineRun([case], Path(directory) / "run", backend)
            content = {"prompt": p.judge_prompt(case, "P")}
            run._call("one", "judge", content, (0, "P"))
            with self.assertRaisesRegex(Exception, "retry forbidden"):
                run._call("one", "judge", content, (0, "P"))
            self.assertEqual(len(backend.requests), 1)


if __name__ == "__main__":
    unittest.main()
