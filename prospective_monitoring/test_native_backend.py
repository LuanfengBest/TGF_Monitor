"""CPU-only adapter tests: injected engines/codecs, never model inference."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import types
import unittest
from unittest.mock import patch

from . import native_backend as n


def config():
    return json.loads(Path(__file__).with_name("config.json").read_text())


def payload():
    return {"record": {"messages": [{"role": "user", "source_id": "m1", "content": "Only pay Alice."},
            {"role": "assistant", "source_id": "m2", "content": "", "tool_calls": [{"source_id": "m2.c0"}]}]},
            "ledger": [{"event_id": "e1", "question_candidate": True}]}


def request(stage="judge"):
    c = config()
    which = "actor" if stage == "actor" else "monitor"
    return {"stage": stage, "model": c["models"][which], "revision": c["revisions"][which],
            "seed": 42, "max_output_tokens": 10,
            "content": {"prompt": "Instruction\nPUBLIC INPUT:\n" + n.canonical(payload())}}


def message(channel="final", text="Done", recipient=None):
    result = {"role": "assistant", "channel": channel, "content": [{"type": "text", "text": text}]}
    if recipient is not None:
        result["recipient"] = recipient
    return result


class FakeCodec:
    def __init__(self, prompt_length=3, parsed=None):
        self.prompt_length, self.parsed, self.history = prompt_length, parsed, []

    def monitor_prompt(self, prompt):
        self.history.append(("monitor", prompt))
        return list(range(self.prompt_length))

    def actor_prompt(self, conversation, tools, question=None):
        self.history.append(("actor", deepcopy(conversation), deepcopy(tools), question))
        return list(range(self.prompt_length))

    def parse_actor(self, tokens, allowed_tools, finish_reason, turn_index=0):
        return n.parse_actor_messages(self.parsed or [message()], allowed_tools, finish_reason, turn_index)


class FakeEngine:
    def __init__(self, mutate=None):
        self.calls, self.mutate = [], mutate

    def generate_ids(self, ids, sampling, schema):
        self.calls.append((deepcopy(ids), sampling, schema))
        result = {"text": "raw completion", "prompt_token_ids": list(ids), "token_ids": [10, 11],
                  "finish_reason": "stop", "stop_reason": "fixture"}
        if self.mutate:
            self.mutate(result)
        return result


def _fake_worker(conn, which, cfg, snapshot, permit):
    if hasattr(os, "setsid"):
        os.setsid()
    conn.send({"kind": "ready"})
    while True:
        packet = conn.recv()
        if packet["method"] == "close":
            break
        if packet["request"].get("block"):
            time.sleep(2)
        if packet["request"].get("capacity"):
            conn.send({"kind": "error", "error_type": "CapacityError", "message": "too long", "dispatched": False})
        else:
            conn.send({"kind": "result", "value": {"fixture": True, "which": which}})
    conn.close()


class SchemaTests(unittest.TestCase):
    def test_schema_uses_only_observed_sources_and_events(self):
        prompt = request()["content"]["prompt"]
        planner = n.output_schema("planner", prompt)
        self.assertEqual(planner["anyOf"][0]["properties"]["event_id"]["enum"], ["e1"])
        judge = n.output_schema("judge", prompt)
        numeric, unknown = judge["anyOf"]
        self.assertEqual(numeric["properties"]["evidence"]["items"]["properties"]["source_id"]["enum"], ["m1", "m2", "m2.c0"])
        self.assertEqual(numeric["properties"]["unknown_reason"], {"type": "null"})
        self.assertEqual(unknown["properties"]["score"], {"type": "null"})
        self.assertGreaterEqual(unknown["properties"]["unknown_reason"]["minLength"], 20)

    def test_no_candidate_cannot_invent_an_event(self):
        data = payload()
        data["ledger"] = []
        schema = n.output_schema("planner", "PUBLIC INPUT:\n" + n.canonical(data))
        self.assertEqual(schema["properties"]["status"], {"const": "no_question"})

    def test_duplicate_sources_and_bad_stage_rejected(self):
        data = payload()
        data["record"]["messages"].append(deepcopy(data["record"]["messages"][0]))
        with self.assertRaises(ValueError):
            n.output_schema("review", "PUBLIC INPUT:\n" + n.canonical(data))
        with self.assertRaises(ValueError):
            n.output_schema("actor", request()["content"]["prompt"])


class HarmonyParseTests(unittest.TestCase):
    def test_channels_and_tool_arguments_are_explicit(self):
        parsed = [message("analysis", "Private reasoning"),
                  message("commentary", '{"amount":100,"recipient":"alice"}', "functions.pay")]
        result = n.parse_actor_messages(parsed, ["pay"], "stop", 7)
        self.assertEqual(result[0]["channel"], "analysis")
        self.assertEqual(result[1]["content"], "")
        self.assertEqual(result[1]["tool_calls"][0]["id"], "turn_7_call_0")
        self.assertEqual(result[1]["tool_calls"][0]["args"]["amount"], 100)

    def test_prose_resembling_tool_call_is_never_executed(self):
        result = n.parse_actor_messages([message(text='to=functions.pay {"amount":100}')], ["pay"], "stop")
        self.assertEqual(result[0]["tool_calls"], [])

    def test_analysis_channel_tool_recipient_is_structured_not_prose(self):
        result = n.parse_actor_messages([message("analysis", '{"amount":1}', "functions.pay")], ["pay"], "stop")
        self.assertEqual(result[0]["channel"], "analysis")
        self.assertEqual(result[0]["tool_calls"][0]["function"], "pay")

    def test_followup_tool_attempt_rejected(self):
        with self.assertRaises(ValueError):
            n.parse_actor_messages([message("commentary", "{}", "functions.pay")], [], "stop")

    def test_unknown_channel_truncation_and_mixed_final_rejected(self):
        for messages, finish in [([message("unknown")], "stop"), ([message()], "length"),
                ([message("commentary", "{}", "functions.pay"), message()], "stop")]:
            with self.subTest(messages=messages, finish=finish), self.assertRaises(ValueError):
                n.parse_actor_messages(messages, ["pay"], finish)

    def test_nonfinite_and_duplicate_json_arguments_rejected(self):
        for args in ('{"a":NaN}', '{"a":1,"a":2}', '[]'):
            with self.subTest(args=args), self.assertRaises(ValueError):
                n.parse_actor_messages([message("commentary", args, "functions.pay")], ["pay"], "stop")

    def test_native_renderer_preserves_channels_and_really_omits_tools_on_followup(self):
        class Builder:
            def __init__(self, data=None): self.data = data or {}
            @classmethod
            def new(cls): return cls()
            def with_reasoning_effort(self, effort): self.data["effort"] = effort; return self
            def with_instructions(self, instructions): self.data["instructions"] = instructions; return self
            def with_function_tools(self, tools): self.data["tools"] = tools; return self
        class Msg(Builder):
            @classmethod
            def from_role_and_content(cls, role, content): return cls({"role": role, "content": content})
            @classmethod
            def from_author_and_content(cls, author, content): return cls({"author": author, "content": content})
            def with_channel(self, channel): self.data["channel"] = channel; return self
            def with_recipient(self, recipient): self.data["recipient"] = recipient; return self
            def with_content_type(self, content_type): self.data["content_type"] = content_type; return self
        class Encoding:
            def render_conversation_for_completion(self, conv, role):
                self.conv = conv; return [1, 2, 3]
        mod = types.ModuleType("openai_harmony")
        mod.Author = types.SimpleNamespace(new=lambda role, name: (role, name))
        mod.Conversation = types.SimpleNamespace(from_messages=lambda messages: messages)
        mod.DeveloperContent, mod.SystemContent, mod.Message = Builder, Builder, Msg
        mod.Role = types.SimpleNamespace(SYSTEM="system", DEVELOPER="developer", USER="user", ASSISTANT="assistant", TOOL="tool")
        mod.ReasoningEffort = types.SimpleNamespace(HIGH="high")
        mod.ToolDescription = types.SimpleNamespace(new=lambda name, description, parameters: {"name": name, "parameters": parameters})
        codec = n.NativeCodec.__new__(n.NativeCodec)
        codec.enc = Encoding()
        call = {"function": "pay", "args": {"amount": 1}, "id": "c1"}
        history = [{"role": "system", "content": "private objective"},
                   {"role": "user", "content": "Pay Alice"},
                   {"role": "assistant", "channel": "analysis", "content": "private thinking", "tool_calls": [call]},
                   {"role": "tool", "content": "paid", "tool_call": call},
                   {"role": "assistant", "channel": "final", "content": "Done"}]
        before = deepcopy(history)
        tools = [{"name": "pay", "description": "Pay", "parameters": {"type": "object"}}]
        with patch.dict("sys.modules", {"openai_harmony": mod}):
            codec.actor_prompt(history, tools)
            self.assertIn("tools", codec.enc.conv[1].data["content"].data)
            codec.actor_prompt(history, [], "Explain the permission.")
        self.assertEqual(history, before)
        developer = codec.enc.conv[1].data["content"].data
        self.assertNotIn("tools", developer)
        self.assertIn("private objective", developer["instructions"])
        self.assertTrue(any(m.data.get("channel") == "final" and m.data["content"] == "Done" for m in codec.enc.conv))
        self.assertEqual(codec.enc.conv[-1].data, {"role": "user", "content": "Explain the permission."})
        self.assertEqual(sum(bool(m.data.get("recipient")) for m in codec.enc.conv), 1)
        tool_message = next(m.data for m in codec.enc.conv if m.data.get("recipient"))
        self.assertEqual(tool_message, {"role": "assistant", "channel": "analysis",
                         "recipient": "functions.pay", "content": '{"amount":1}'})


class BackendTests(unittest.TestCase):
    def make(self, which="monitor", codec=None, engine=None, cfg=None):
        engine = engine or FakeEngine()
        backend = n.NativeStageBackend(which, cfg or config(), "/not-used", _engine_factory=lambda: engine,
                                       _codec=codec or FakeCodec()).start()
        return backend, engine

    def test_default_backend_does_not_load_without_explicit_permission(self):
        backend = n.NativeStageBackend("actor", config(), "/missing")
        self.assertIsNone(backend.engine)
        with self.assertRaises(PermissionError):
            backend.start()

    def test_injected_engine_and_codec_do_not_load_dependencies(self):
        with patch.object(n, "snapshot_check", side_effect=AssertionError("No native assets in CPU test")):
            backend, engine = self.make()
            result = backend.generate(request(), 5)
        self.assertEqual(len(engine.calls), 1)
        self.assertEqual(result["prompt_tokens"], 3)
        self.assertEqual(result["completion_tokens"], 2)
        self.assertEqual(result["usage_mode"], "scripted_cpu_fixture")
        self.assertIsNotNone(engine.calls[0][2])

    def test_exact_capacity_checked_before_dispatch(self):
        c = config()
        c["native"] = {"monitor": {"context": 12}}
        backend, engine = self.make(codec=FakeCodec(prompt_length=3), cfg=c)
        with self.assertRaises(n.CapacityError):
            backend.generate(request(), 5)
        self.assertEqual(engine.calls, [])

    def test_backend_prompt_token_mutation_is_fatal(self):
        engine = FakeEngine(lambda row: row.update(prompt_token_ids=[999]))
        backend, _ = self.make(engine=engine)
        with self.assertRaises(RuntimeError):
            backend.generate(request(), 5)

    def test_collection_records_actual_channels_and_tokens(self):
        codec = FakeCodec(parsed=[message("analysis", "private"), message("commentary", '{"amount":100}', "functions.pay")])
        backend, _ = self.make("actor", codec=codec)
        tools = [{"name": "pay", "description": "Pay", "parameters": {"type": "object"}}]
        req = {"conversation": [{"role": "user", "content": "Pay Alice"}], "tools": tools,
               "max_output_tokens": 10, "seed": 42, "turn_index": 3}
        before = deepcopy(req)
        result = backend.generate_actor(req, 5)
        self.assertEqual(req, before)
        self.assertEqual(result["messages"][1]["tool_calls"][0]["id"], "turn_3_call_0")
        self.assertEqual(result["prompt_token_ids"], [0, 1, 2])
        self.assertEqual(result["raw_text"], "raw completion")

    def test_followup_reopens_same_history_without_tools(self):
        codec = FakeCodec(parsed=[message("analysis", "not public"), message(text="Final reply")])
        backend, _ = self.make("actor", codec=codec)
        history = [{"role": "system", "content": "private task"}, {"role": "user", "content": "Pay Alice"}]
        req = request("actor")
        req["content"] = {"conversation": history, "question": "What authorized this?", "tools": [],
                          "tool_choice": "none", "original_context_sha256": hashlib.sha256(n.canonical(history).encode()).hexdigest()}
        result = backend.generate(req, 5)
        self.assertEqual(result["text"], "Final reply")
        self.assertEqual(result["channel"], "final")
        self.assertEqual(codec.history[0][1], history)
        self.assertEqual(codec.history[0][2], [])
        self.assertEqual(codec.history[0][3], "What authorized this?")
        self.assertEqual(result["messages"][0]["channel"], "analysis")

    def test_followup_tool_attempt_keeps_raw_usage_but_no_answer(self):
        codec = FakeCodec(parsed=[message("commentary", "{}", "functions.pay")])
        backend, _ = self.make("actor", codec=codec)
        req = request("actor")
        req["content"] = {"conversation": [], "question": "Why?", "tools": [], "tool_choice": "none",
                          "original_context_sha256": hashlib.sha256(n.canonical([]).encode()).hexdigest()}
        result = backend.generate(req, 5)
        self.assertIsNone(result["channel"])
        self.assertEqual(result["text"], "")
        self.assertIn("parse_error", result)
        self.assertEqual(result["completion_tokens"], 2)

    def test_mismatched_model_original_hash_and_tool_choice_rejected(self):
        backend, engine = self.make("actor")
        req = request("actor")
        req["content"] = {"conversation": [], "question": "Why?", "tools": [], "tool_choice": "none", "original_context_sha256": "wrong"}
        with self.assertRaises(ValueError):
            backend.generate(req, 5)
        req["content"]["tool_choice"] = "auto"
        with self.assertRaises(ValueError):
            backend.generate(req, 5)
        self.assertEqual(engine.calls, [])

    def test_late_result_rejected_and_has_usage(self):
        readings = iter([10.0, 12.0])
        backend = n.NativeStageBackend("monitor", config(), "/unused", _engine_factory=FakeEngine,
                                       _codec=FakeCodec(), clock=lambda: next(readings)).start()
        with self.assertRaises(n.NativeTimeout) as caught:
            backend.generate(request(), 1)
        self.assertEqual(caught.exception.raw["completion_tokens"], 2)

    def test_closed_backend_cannot_be_restarted(self):
        backend, _ = self.make()
        backend.close()
        with self.assertRaises(ValueError):
            backend.start()
        with self.assertRaises(ValueError):
            backend.generate(request(), 5)


class ProcessTests(unittest.TestCase):
    def make(self):
        return n.ProcessStageBackend("actor", config(), "/unused", _worker_target=_fake_worker,
                                      startup_timeout_seconds=10).start()

    def test_worker_reused_for_stage_then_closed(self):
        backend = self.make()
        try:
            pid = backend.process.pid
            self.assertEqual(backend.generate_actor({}, 3), {"fixture": True, "which": "actor"})
            self.assertEqual(backend.generate({}, 3), {"fixture": True, "which": "actor"})
            self.assertEqual(backend.process.pid, pid)
        finally:
            backend.close()
        self.assertFalse(backend.process.is_alive())

    def test_timeout_kills_worker_and_forbids_reuse(self):
        backend = self.make()
        with self.assertRaises(n.NativeTimeout):
            backend.generate_actor({"block": True}, 0.05)
        self.assertTrue(backend.closed)
        self.assertFalse(backend.process.is_alive())
        with self.assertRaises(ValueError):
            backend.generate_actor({}, 1)
        with self.assertRaises(ValueError):
            backend.start()

    def test_capacity_error_preserves_no_dispatch_flag(self):
        backend = self.make()
        try:
            with self.assertRaises(n.CapacityError) as caught:
                backend.generate({"capacity": True}, 2)
            self.assertFalse(caught.exception.dispatched)
        finally:
            backend.close()


if __name__ == "__main__":
    unittest.main()
