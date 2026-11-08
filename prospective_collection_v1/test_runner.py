import json
from pathlib import Path
import tempfile
import unittest

from prospective_data_v2.specs import build_manifest
from prospective_collection_v1.runner import Guard


class CountingBackend:
    origin_kind = "natural_actor"
    def __init__(self):
        self.calls = 0
        self.fail = False
    def generate_actor(self, request, timeout_seconds):
        self.calls += 1
        if self.fail:
            raise TimeoutError("simulated failed dispatch")
        return {"timeout_received":timeout_seconds}


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.tasks = build_manifest()["tasks"]
        self.backend = CountingBackend()
        self.now = 0.0
        self.guard = Guard(self.backend, self.tasks, self.tmp.name, 0, lambda:self.now)
        self.req = {"turn_index":0, "max_output_tokens":4096}

    def test_claim_is_durable_before_dispatch(self):
        self.guard.claim_case(self.tasks[0])
        case = self.tasks[0]["case_id"]
        def call(request, timeout_seconds):
            self.assertTrue((Path(self.tmp.name)/"claims"/(case+".json")).is_file())
            self.assertTrue((Path(self.tmp.name)/"calls"/(case+"-00.json")).is_file())
            return {}
        self.backend.generate_actor = call
        self.guard.generate_actor(self.req, 120)

    def test_failed_call_still_consumes_slot(self):
        self.guard.claim_case(self.tasks[0])
        self.backend.fail = True
        with self.assertRaises(TimeoutError):
            self.guard.generate_actor(self.req, 120)
        with self.assertRaises(ValueError):
            self.guard.generate_actor(self.req, 120)
        self.assertEqual(self.backend.calls, 1)
        self.assertEqual(self.guard.budget.reserved_output_tokens,4096)

    def test_restarted_guard_cannot_repeat_case(self):
        self.guard.claim_case(self.tasks[0])
        replacement = Guard(self.backend,self.tasks,self.tmp.name,0,lambda:0)
        with self.assertRaises(FileExistsError):
            replacement.claim_case(self.tasks[0])

    def test_global_deadline_clips_per_case_timeout(self):
        self.guard.claim_case(self.tasks[0])
        self.now = 7190
        self.assertEqual(self.guard.generate_actor(self.req,120)["timeout_received"],10)
        self.now = 7200
        with self.assertRaises(TimeoutError):
            self.guard.generate_actor({**self.req,"turn_index":1},120)
        self.assertEqual(self.backend.calls,1)

    def test_no_scripted_provenance_relabel(self):
        self.backend.origin_kind = "scripted_cpu_fixture"
        with self.assertRaises(ValueError):
            Guard(self.backend,self.tasks,self.tmp.name,0)

    def test_limit_and_unknown_case_rejected_before_backend(self):
        with self.assertRaises(ValueError):
            self.guard.claim_case({"case_id":"unknown"})
        self.guard.claim_case(self.tasks[0])
        for invalid in ({"turn_index":10,"max_output_tokens":4096},
                        {"turn_index":0,"max_output_tokens":4097}):
            with self.assertRaises(ValueError):
                self.guard.generate_actor(invalid,120)
        self.assertEqual(self.backend.calls,0)


if __name__ == "__main__":
    unittest.main()
