"""CPU tests for the experiment's file boundary and runner."""

import json
from pathlib import Path
import tempfile
import unittest

from .__main__ import prepare, read_json, run_judge, score


class StubJudge:
    def __init__(self, fail=False):
        self.fail = fail
        self.requests = []
        self.closed = False

    def start(self):
        return self

    def generate(self, request, timeout_seconds):
        self.requests.append(request)
        if self.fail:
            raise TimeoutError("fixture failure")
        return {"text": json.dumps({"score": 0, "evidence": [], "rationale": "CPU fixture"}),
                "finish_reason": "stop", "prompt_tokens": 12, "completion_tokens": 3}

    def close(self):
        self.closed = True


class ExperimentFilesTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.bundle = self.root / "bundle"
        self.run = self.root / "run"
        prepare(self.bundle)

    def test_public_only_runner_and_cpu_score(self):
        public = self.bundle / "public"
        # The machine making the model calls has no reference files.
        judge_input = self.root / "judge-input"
        public.rename(judge_input)
        backend = StubJudge()
        run_judge(judge_input, self.run, backend)
        self.assertTrue(backend.closed)
        self.assertEqual(len(backend.requests), 32)
        self.assertEqual({request["max_output_tokens"] for request in backend.requests}, {2048})
        self.assertEqual(read_json(self.run / "summary.json")["state"], "completed")
        judge_input.rename(public)
        report = self.root / "report.json"
        score(self.bundle, self.run, report)
        for arm in read_json(report)["metrics"]["arms"].values():
            self.assertEqual((arm["valid"], arm["tn"], arm["fn"], arm["pairs_correct"]), (16, 8, 8, 0))

    def test_failed_call_is_saved_and_remaining_calls_are_not_dispatched(self):
        backend = StubJudge(fail=True)
        with self.assertRaisesRegex(RuntimeError, "fixture failure"):
            run_judge(self.bundle / "public", self.run, backend)
        self.assertTrue(backend.closed)
        self.assertEqual(len(backend.requests), 1)
        self.assertEqual(read_json(self.run / "summary.json")["state"], "interrupted")
        rows = (self.run / "results.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(rows), 1)
        self.assertIn("fixture failure", json.loads(rows[0])["error"])
        score(self.bundle, self.run, self.root / "partial-report.json")

    def test_changed_public_prompt_is_rejected_before_running(self):
        requests = self.bundle / "public/requests.json"
        requests.write_text(requests.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        backend = StubJudge()
        with self.assertRaisesRegex(ValueError, "changed after preparation"):
            run_judge(self.bundle / "public", self.run, backend)
        self.assertFalse(self.run.exists())
        self.assertEqual(backend.requests, [])
