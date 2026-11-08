"""Deterministic wiring check only. Never a model prediction or research result."""
from copy import deepcopy
import json

from . import protocol as p


class Backend:
    origin_kind, offline = "scripted_cpu_fixture", True

    def __init__(self, factory, which):
        self.factory, self.which, self.closed = factory, which, False

    def generate_actor(self, *args, **kwargs):
        raise AssertionError("An existing-history comparison attempted collection")

    def generate(self, request, timeout_seconds):
        if self.which != ("actor" if request["stage"] == "actor" else "monitor"):
            raise AssertionError("Wrong model phase")
        self.factory.requests.append(deepcopy(request))
        stage = request["stage"]
        if stage == "actor":
            content = request["content"]
            assert content["tools"] == [] and content["tool_choice"] == "none"
            assert content["original_context_sha256"] == p.digest(content["conversation"])
            text = "CPU fixture response, not a model answer."
        else:
            payload = json.loads(request["content"]["prompt"].split("PUBLIC INPUT:\n", 1)[1])
            if stage == "planner":
                candidates = [e for e in payload["ledger"] if e["question_candidate"]]
                value = ({"status": "selected", "event_id": candidates[0]["event_id"], "dimension": "authority_scope"}
                         if candidates else {"status": "no_question", "event_id": None, "dimension": None})
            else:
                citation = {"claim": "CPU source binding check; not an assessment.", "evidence_id": payload["evidence_units"][0]["evidence_id"]}
                value = {"notes": [citation]} if stage == "review" else {
                    "score": 0, "evidence": [citation], "rationale": "CPU fixture only; do not interpret as accuracy.", "unknown_reason": None}
            text = p.canonical(value)
        raw = {"text": text, "channel": "final", "tool_calls": [], "finish_reason": "stop",
               "prompt_tokens": 10, "completion_tokens": 10, "inference_seconds": .001,
               "usage_complete": True, "usage_mode": "scripted_cpu_fixture"}
        return self.factory.hook(self, request, raw) if self.factory.hook else raw

    def close(self):
        self.closed = True
        self.factory.closed.append(self.which)


class Factory:
    execution_mode = "fixture"

    def __init__(self, hook=None):
        self.hook = hook
        self.started, self.closed, self.requests = [], [], []

    def __call__(self, which, remaining_seconds):
        self.started.append(which)
        return Backend(self, which)
