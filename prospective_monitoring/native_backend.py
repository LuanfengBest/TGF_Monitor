"""Pinned local Harmony/Qwen adapter, with a killable single-model stage worker.

Importing this module imports no model libraries and loads no weights. Live use
requires explicit start(), permit_live=True, and existing pinned local snapshots.
This is an adapter, not a job-submission or experiment-authorization entrypoint.
"""
from copy import deepcopy
import hashlib
import json
import math
import multiprocessing
import os
from pathlib import Path
import signal
import time


PINNED = {
    "actor": {"model": "openai/gpt-oss-120b", "revision": "b5c939de8f754692c1647ca79fbf85e8c1e70f8a",
              "context": 131072, "top_p": 0.9, "quantization": "mxfp4"},
    "monitor": {"model": "Qwen/Qwen3-32B", "revision": "9216db5781bf21249d130ec9da846c4624c16137",
                "context": 131072, "top_p": 0.95, "rope_factor": 4.0, "original_context": 32768},
}
TOKENIZER_HASHES = {
    "tokenizer.json": "aeb13307a71acd8fe81861d94ad54ab689df773318809eed3cbe794b4492dae4",
    "tokenizer_config.json": "d5d09f07b48c3086c508b30d1c9114bd1189145b74e982a265350c923acd8101",
}
PINNED_RUNTIME = {"python": "3.12.12", "vllm": "0.13.0", "torch": "2.9.0+cu129",
                  "transformers": "4.57.3", "openai-harmony": "0.0.8"}
DIMENSIONS = ("recipient_or_item", "amount_or_parameters", "timing_or_correction", "authority_scope")


class CapacityError(ValueError):
    """Actual prompt plus output reserve does not fit; no inference dispatched."""
    dispatched = False


class NativeTimeout(TimeoutError):
    """Stage worker was killed. In-flight usage is unknown; retry is forbidden."""
    usage_complete = False


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def dependency_files():
    return [Path(__file__).resolve().parents[1] / "matched_followup_v2/native.py"]


def _positive_int(value, name):
    if type(value) is not int or value <= 0:
        raise ValueError(name + " must be a positive integer")
    return value


def _seconds(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise ValueError("timeout_seconds must be finite and positive")
    return float(value)


def snapshot_check(snapshot, which):
    """Cheap local admission; weight-content hashing remains campaign preflight's job."""
    spec = PINNED[which]
    path = Path(snapshot).absolute()
    if path.name != spec["revision"] or path.parent.name != "snapshots":
        raise ValueError("An exact pinned local HF snapshot is required")
    for name in ("config.json", "model.safetensors.index.json"):
        if not (path / name).is_file():
            raise ValueError("Missing local model asset: " + name)
    index = json.loads((path / "model.safetensors.index.json").read_text())
    for name in set(index["weight_map"].values()):
        if Path(name).name != name or not (path / name).is_file() or (path / name).stat().st_size <= 0:
            raise ValueError("Missing or unsafe local model shard")
    if which == "monitor":
        for name, expected in TOKENIZER_HASHES.items():
            if hashlib.sha256((path / name).read_bytes()).hexdigest() != expected:
                raise ValueError("Pinned Qwen tokenizer/template mismatch")
    else:
        cfg = json.loads((path / "config.json").read_text())
        if cfg.get("quantization_config", {}).get("quant_method") != "mxfp4":
            raise ValueError("Actor quantization mismatch")
    return path


def runtime_check(config):
    from importlib.metadata import version
    import platform
    expected = config.get("runtime", PINNED_RUNTIME)
    if expected != PINNED_RUNTIME:
        raise ValueError("Runtime changes need a new explicit protocol/preflight")
    found = {"python": platform.python_version()}
    found.update({key: version(key) for key in expected if key != "python"})
    if found != expected:
        raise ValueError("Pinned native runtime mismatch: " + canonical(found))
    return found


def _obj(properties):
    return {"type": "object", "properties": properties, "required": list(properties),
            "additionalProperties": False}


def output_schema(stage, prompt):
    """Constrain output shape and public IDs, not factual correctness."""
    if stage not in {"planner", "review", "judge"}:
        raise ValueError("No structured monitor schema for this stage")
    payload = json.loads(prompt.split("PUBLIC INPUT:\n", 1)[1])
    messages = payload["record"]["messages"]
    sources = []
    for message in messages:
        sources.append(message["source_id"])
        sources.extend(call["source_id"] for call in message.get("tool_calls", []))
    if len(sources) != len(set(sources)) or not sources:
        raise ValueError("Monitor schema needs unique original source IDs")
    if stage == "planner":
        no_question = _obj({"status": {"const": "no_question"}, "event_id": {"type": "null"},
                            "dimension": {"type": "null"}})
        candidates = [e["event_id"] for e in payload["ledger"] if e["question_candidate"]]
        if not candidates:
            return no_question
        return {"anyOf": [_obj({"status": {"const": "selected"}, "event_id": {"enum": candidates},
                                 "dimension": {"enum": list(DIMENSIONS)}}), no_question]}
    evidence = _obj({"claim": {"type": "string", "minLength": 1, "maxLength": 500},
                     "source_id": {"enum": sources},
                     "quote": {"type": "string", "minLength": 1, "maxLength": 400}})
    if stage == "review":
        return _obj({"notes": {"type": "array", "maxItems": 6, "items": evidence}})
    common = {"evidence": {"type": "array", "maxItems": 4, "items": evidence},
              "rationale": {"type": "string", "minLength": 1, "maxLength": 800}}
    numeric = deepcopy(common)
    numeric["evidence"]["minItems"] = 1
    numeric.update(score={"type": "integer", "minimum": 0, "maximum": 100}, unknown_reason={"type": "null"})
    unknown = deepcopy(common)
    unknown.update(score={"type": "null"}, unknown_reason={"type": "string", "minLength": 20, "maxLength": 500})
    return {"anyOf": [_obj(numeric), _obj(unknown)]}


def normalize_tools(tools):
    if not isinstance(tools, list):
        raise ValueError("tools must be a list")
    result, seen = [], set()
    for tool in tools:
        if not isinstance(tool, dict) or set(tool) != {"name", "description", "parameters"}:
            raise ValueError("Tools require name/description/parameters")
        name = tool["name"]
        if not isinstance(name, str) or not name or name in seen or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_" for c in name):
            raise ValueError("Invalid or duplicate tool name")
        if not isinstance(tool["description"], str) or not isinstance(tool["parameters"], dict):
            raise ValueError("Malformed tool definition")
        seen.add(name)
        result.append(deepcopy(tool))
    canonical(result)
    return result


def parse_actor_messages(parsed, allowed_tools, finish_reason, turn_index=0):
    """Parse Harmony message dictionaries without interpreting prose as calls."""
    if finish_reason != "stop":
        raise ValueError("Truncated or unsuccessful actor completion")
    allowed = set(allowed_tools)
    result, calls = [], 0
    for data in parsed:
        role = data.get("role", "assistant")
        if role != "assistant":
            raise ValueError("Non-assistant message in actor completion")
        channel = data.get("channel")
        if channel not in {"analysis", "commentary", "final"}:
            raise ValueError("Actor completion lacks an explicit supported channel")
        content = data.get("content")
        if not isinstance(content, list) or any(not isinstance(p, dict) or not isinstance(p.get("text"), str) for p in content):
            raise ValueError("Only plain-text Harmony message content is supported")
        text = "".join(p["text"] for p in content)
        recipient = data.get("recipient")
        message = {"role": "assistant", "channel": channel, "content": text, "tool_calls": []}
        if recipient is not None:
            if channel not in {"analysis", "commentary"} or not isinstance(recipient, str) or not recipient.startswith("functions."):
                raise ValueError("Unexpected tool-call channel or recipient")
            name = recipient[len("functions."):]
            if name not in allowed:
                raise ValueError("Actor attempted an unavailable tool: " + name)
            def pairs(items):
                obj = {}
                for k, v in items:
                    if k in obj:
                        raise ValueError("Duplicate tool argument key")
                    obj[k] = v
                return obj
            args = json.loads(text, object_pairs_hook=pairs,
                              parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite tool argument")))
            if not isinstance(args, dict):
                raise ValueError("Tool arguments must be an object")
            message["content"] = ""
            message["tool_calls"] = [{"function": name, "args": args, "id": f"turn_{turn_index}_call_{calls}"}]
            calls += 1
        result.append(message)
    if not result:
        raise ValueError("Empty actor completion")
    if calls and any(m["channel"] == "final" for m in result):
        raise ValueError("Completion mixes tool dispatch with a final response")
    if not calls and len([m for m in result if m["channel"] == "final" and m["content"].strip()]) != 1:
        raise ValueError("A non-tool completion needs exactly one nonempty final answer")
    return result


class NativeCodec:
    """Pinned native serialization; instantiated only on explicit start/admission."""
    def __init__(self, which, snapshot):
        self.which = which
        if which == "actor":
            from openai_harmony import HarmonyEncodingName, load_harmony_encoding
            self.enc = load_harmony_encoding(HarmonyEncodingName.HARMONY_GPT_OSS)
        else:
            from transformers import AutoTokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(str(snapshot), local_files_only=True, trust_remote_code=False)

    def monitor_prompt(self, prompt):
        rendered = self.tokenizer.apply_chat_template([{"role": "user", "content": prompt}],
            tokenize=False, add_generation_prompt=True, enable_thinking=False)
        expected = "<|im_start|>user\n" + prompt + "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
        if rendered != expected:
            raise ValueError("Unexpected pinned Qwen template branch")
        return self.tokenizer.encode(rendered, add_special_tokens=False)

    def actor_prompt(self, conversation, tools, question=None):
        from openai_harmony import Author, Conversation, DeveloperContent, Message, ReasoningEffort, Role, SystemContent, ToolDescription
        # Legacy unchannelled histories retain the established deterministic parser.
        from matched_followup_v2.native import assistant_segments
        tools = normalize_tools(tools)
        instructions = [m["content"] for m in conversation if m["role"] in {"system", "developer", "monitor"}]
        if tools:
            instructions.append("Call at most one tool per assistant turn. Wait for its result before selecting another tool.")
        developer = DeveloperContent.new()
        if instructions:
            developer = developer.with_instructions("\n\n".join(instructions))
        if tools:
            developer = developer.with_function_tools([ToolDescription.new(t["name"], t["description"], t["parameters"]) for t in tools])
        messages = [Message.from_role_and_content(Role.SYSTEM, SystemContent.new().with_reasoning_effort(ReasoningEffort.HIGH)),
                    Message.from_role_and_content(Role.DEVELOPER, developer)]
        for m in conversation:
            role = m["role"]
            if role in {"system", "developer", "monitor"}:
                continue
            if role == "user":
                messages.append(Message.from_role_and_content(Role.USER, m["content"]))
            elif role == "assistant":
                segments = ([(m["channel"], m["content"])] if "channel" in m else assistant_segments(m["content"]))
                for channel, text in segments:
                    if channel not in {"analysis", "commentary", "final"}:
                        raise ValueError("Unknown historical assistant channel")
                    if text and not ("channel" not in m and channel == "commentary"
                                     and text.startswith("to=functions.") and m.get("tool_calls")):
                        # Structured calls are emitted separately, never discovered in text.
                        messages.append(Message.from_role_and_content(Role.ASSISTANT, text).with_channel(channel))
                for call in m.get("tool_calls") or []:
                    # Tool arguments already carry canonical JSON. An added
                    # '<|constrain|> json' header is not a valid round trip in
                    # the pinned Harmony 0.0.8 completion parser.
                    messages.append(Message.from_role_and_content(Role.ASSISTANT, canonical(call["args"]))
                                    .with_channel(m.get("channel", "commentary")).with_recipient("functions." + call["function"]))
            elif role == "tool":
                call = m.get("tool_call")
                if not isinstance(call, dict) or not isinstance(call.get("function"), str):
                    raise ValueError("Tool result lacks bound historical function")
                messages.append(Message.from_author_and_content(Author.new(Role.TOOL, "functions." + call["function"]),
                                m.get("error") or m["content"]).with_channel("commentary"))
            else:
                raise ValueError("Unsupported native history role")
        if question is not None:
            messages.append(Message.from_role_and_content(Role.USER, question))
        return self.enc.render_conversation_for_completion(Conversation.from_messages(messages), Role.ASSISTANT)

    def parse_actor(self, tokens, allowed_tools, finish_reason, turn_index=0):
        from openai_harmony import Role
        parsed = [m.to_dict() for m in self.enc.parse_messages_from_completion_tokens(tokens, Role.ASSISTANT)]
        return parse_actor_messages(parsed, allowed_tools, finish_reason, turn_index)


def compile_monitor_schemas(snapshot, examples):
    """CPU-only tokenizer/grammar admission for supplied (stage, prompt, cap) examples.

    It covers only these inputs, not unknown future generated trajectories. Actual
    native dispatch always recounts its own exact prompt and output reserve.
    """
    path = snapshot_check(snapshot, "monitor")
    codec = NativeCodec("monitor", path)
    import xgrammar
    compiler = xgrammar.GrammarCompiler(xgrammar.TokenizerInfo.from_huggingface(codec.tokenizer))
    rows = []
    for example in examples:
        stage, prompt, cap = example["stage"], example["prompt"], example["max_output_tokens"]
        _positive_int(cap, "max_output_tokens")
        schema = output_schema(stage, prompt)
        compiler.compile_json_schema(schema)
        ids = codec.monitor_prompt(prompt)
        if len(ids) + cap > PINNED["monitor"]["context"]:
            raise CapacityError("Monitor grammar example exceeds context")
        rows.append({"stage": stage, "prompt_tokens": len(ids), "reserved_output_tokens": cap,
                     "schema_sha256": hashlib.sha256(canonical(schema).encode()).hexdigest(),
                     "prompt_sha256": hashlib.sha256(canonical(ids).encode()).hexdigest()})
    return {"scope": "supplied_examples_only", "grammar_examples_compiled": len(rows), "examples": rows,
            "model_inference_performed": False, "future_dynamic_prompt_admission": "required_per_dispatch"}


class NativeStageBackend:
    """One loaded model per process; caller groups collection/review/answer/judge stages."""
    def __init__(self, which, config, snapshot, permit_live=False, *, _engine_factory=None, _codec=None, clock=time.monotonic):
        if which not in PINNED:
            raise ValueError("Unknown native model kind")
        self.which, self.config, self.snapshot = which, deepcopy(config), snapshot
        self.permit_live, self._engine_factory, self.codec = permit_live, _engine_factory, _codec
        self.clock, self.engine, self.started, self.closed = clock, None, False, False
        self.offline = _engine_factory is not None
        self.origin_kind = "scripted_cpu_fixture" if self.offline else "natural_actor"
        for field, key in (("models", "model"), ("revisions", "revision")):
            if self.config[field][which] != PINNED[which][key]:
                raise ValueError("Pinned model identity changed")
        self.context = self.config.get("native", {}).get(which, {}).get("context", PINNED[which]["context"])
        _positive_int(self.context, "context")
        if self.context > PINNED[which]["context"]:
            raise ValueError("Context exceeds validated model limit")

    def start(self):
        if self.started or self.closed:
            raise ValueError("Backend is single-start and cannot be reused after close")
        if self.offline:
            if self.codec is None:
                raise ValueError("CPU injection requires a fake codec; no implicit tokenizer load")
            self.engine = self._engine_factory()
        else:
            if self.permit_live is not True:
                raise PermissionError("Explicit live start permission is required")
            path = snapshot_check(self.snapshot, self.which)
            runtime_check(self.config)
            import torch
            from vllm import LLM
            if torch.cuda.device_count() != 1 or "H200" not in torch.cuda.get_device_name(0):
                raise ValueError("Native stage requires exactly one H200")
            spec = PINNED[self.which]
            self.codec = NativeCodec(self.which, path)
            kwargs = {"model": str(path), "tokenizer": str(path), "revision": spec["revision"],
                      "tokenizer_revision": spec["revision"], "tensor_parallel_size": 1,
                      "gpu_memory_utilization": 0.90, "max_model_len": self.context,
                      "seed": self.config["seed"], "max_num_seqs": 1, "trust_remote_code": False}
            if self.which == "actor":
                kwargs["quantization"] = "mxfp4"
            else:
                kwargs["hf_overrides"] = {"rope_parameters": {"rope_type": "yarn", "factor": 4.0,
                                                             "original_max_position_embeddings": 32768}}
            self.engine = LLM(**kwargs)
        self.started = True
        return self

    def close(self):
        self.closed = True
        self.engine = None

    def _sample(self, ids, cap, seed, timeout_seconds, schema=None):
        if not self.started or self.closed:
            raise ValueError("Explicitly start a fresh backend first")
        _seconds(timeout_seconds)
        _positive_int(cap, "max_output_tokens")
        if type(seed) is not int:
            raise ValueError("Seed must be an integer")
        ids = list(ids)
        if any(type(t) is not int or t < 0 for t in ids):
            raise ValueError("Tokenizer returned invalid token IDs")
        if len(ids) + cap > self.context:
            raise CapacityError(f"{len(ids)} prompt + {cap} output > {self.context} context")
        kwargs = {"max_tokens": cap, "temperature": self.config.get("temperature", 0.6),
                  "top_p": PINNED[self.which]["top_p"], "seed": seed}
        if self.which == "actor":
            kwargs["stop_token_ids"] = list(self.codec.enc.stop_tokens_for_assistant_actions()) if hasattr(self.codec, "enc") else []
        start = self.clock()
        if self.offline:
            raw = self.engine.generate_ids(ids, deepcopy(kwargs), deepcopy(schema))
        else:
            from vllm import SamplingParams
            if schema is not None:
                from vllm.sampling_params import StructuredOutputsParams
                kwargs["structured_outputs"] = StructuredOutputsParams(json=schema, disable_fallback=True)
            outputs = self.engine.generate([{"prompt_token_ids": ids}], SamplingParams(**kwargs), use_tqdm=False)
            if len(outputs) != 1 or len(outputs[0].outputs) != 1:
                raise RuntimeError("Unexpected native response count")
            result, output = outputs[0], outputs[0].outputs[0]
            raw = {"text": output.text, "token_ids": list(output.token_ids),
                   "prompt_token_ids": list(result.prompt_token_ids), "finish_reason": output.finish_reason,
                   "stop_reason": output.stop_reason}
        elapsed = max(0.0, self.clock() - start)
        if raw.get("prompt_token_ids") != ids:
            raise RuntimeError("Native engine changed prompt token IDs")
        tokens = raw.get("token_ids")
        if not isinstance(tokens, list) or any(type(t) is not int or t < 0 for t in tokens):
            raise ValueError("Invalid completion token IDs")
        if len(tokens) > cap:
            raise ValueError("Native engine exceeded output reserve")
        result = deepcopy(raw)
        result.update(prompt_tokens=len(ids), completion_tokens=len(tokens), inference_seconds=elapsed,
                      prompt_sha256=hashlib.sha256(canonical(ids).encode()).hexdigest(),
                      usage_complete=True, usage_mode="scripted_cpu_fixture" if self.offline else "native_model_usage")
        if elapsed >= timeout_seconds:
            # The process wrapper is the hard deadline. Direct use also rejects late results.
            error = NativeTimeout("Native result returned after the allowed duration")
            error.raw = result
            raise error
        return result

    def generate_actor(self, request, timeout_seconds):
        if not self.started or self.closed:
            raise ValueError("Explicitly start a fresh backend first")
        if self.which != "actor":
            raise ValueError("Actor collection requires the actor stage")
        tools = normalize_tools(request["tools"])
        ids = self.codec.actor_prompt(request["conversation"], tools)
        raw = self._sample(ids, request["max_output_tokens"], request["seed"], timeout_seconds)
        raw["raw_text"] = raw["text"]
        try:
            raw["messages"] = self.codec.parse_actor(raw["token_ids"], [t["name"] for t in tools],
                                                      raw["finish_reason"], request.get("turn_index", 0))
        except (ValueError, KeyError, TypeError) as exc:
            raw.update(messages=[], parse_error=type(exc).__name__ + ": " + str(exc))
        return raw

    def generate(self, request, timeout_seconds):
        if not self.started or self.closed:
            raise ValueError("Explicitly start a fresh backend first")
        stage = request["stage"]
        wanted = "actor" if stage == "actor" else "monitor"
        if self.which != wanted or request["model"] != PINNED[wanted]["model"] or request["revision"] != PINNED[wanted]["revision"]:
            raise ValueError("Request/model stage mismatch")
        if stage not in {"actor", "planner", "review", "judge"}:
            raise ValueError("Unknown inference stage")
        cap = _positive_int(request["max_output_tokens"], "max_output_tokens")
        if cap > self.config["stage_output_caps"][stage]:
            raise ValueError("Request exceeds frozen stage output cap")
        if wanted == "monitor":
            prompt = request["content"]["prompt"]
            schema = output_schema(stage, prompt)
            return self._sample(self.codec.monitor_prompt(prompt), cap, request["seed"], timeout_seconds, schema)
        content = request["content"]
        if content.get("tools") != [] or content.get("tool_choice") != "none":
            raise ValueError("Follow-up tools must be disabled")
        original = content["conversation"]
        if content.get("original_context_sha256") != hashlib.sha256(canonical(original).encode()).hexdigest():
            raise ValueError("Actor original context hash mismatch")
        ids = self.codec.actor_prompt(original, [], content["question"])
        raw = self._sample(ids, cap, request["seed"], timeout_seconds)
        raw["raw_text"] = raw["text"]
        try:
            messages = self.codec.parse_actor(raw["token_ids"], [], raw["finish_reason"])
            finals = [m["content"] for m in messages if m["channel"] == "final"]
            if len(finals) != 1:
                raise ValueError("One final answer required")
            raw.update(messages=messages, text=finals[0], channel="final", tool_calls=[])
        except (ValueError, KeyError, TypeError) as exc:
            raw.update(text="", channel=None, tool_calls=[], parse_error=type(exc).__name__ + ": " + str(exc))
        return raw


def _stage_worker(connection, which, config, snapshot, permit_live):
    # A dedicated session makes timeout termination include vLLM worker children.
    if hasattr(os, "setsid"):
        os.setsid()
    backend = None
    try:
        backend = NativeStageBackend(which, config, snapshot, permit_live=permit_live).start()
        connection.send({"kind": "ready"})
        while True:
            packet = connection.recv()
            if packet["method"] == "close":
                return
            try:
                method = getattr(backend, packet["method"])
                result = method(packet["request"], packet["timeout_seconds"])
                connection.send({"kind": "result", "value": result})
            except Exception as exc:
                connection.send({"kind": "error", "error_type": type(exc).__name__, "message": str(exc),
                                 "dispatched": not isinstance(exc, CapacityError), "raw": getattr(exc, "raw", None)})
    except (EOFError, BrokenPipeError):
        pass
    except Exception as exc:
        connection.send({"kind": "error", "error_type": type(exc).__name__, "message": str(exc), "dispatched": False})
    finally:
        if backend is not None:
            backend.close()
        connection.close()


class ProcessStageBackend:
    """Persistent one-model subprocess with a hard per-call wall deadline.

    A timeout closes the whole stage and kills its process group; it cannot be
    restarted. The campaign owns dispatch receipts and never retries a slot.
    """
    offline = False
    origin_kind = "natural_actor"

    def __init__(self, which, config, snapshot, permit_live=False, startup_timeout_seconds=900,
                 *, _worker_target=None):
        if which not in PINNED:
            raise ValueError("Unknown model stage")
        self.which, self.config, self.snapshot = which, deepcopy(config), str(snapshot)
        self.permit_live = permit_live
        self.startup_timeout = _seconds(startup_timeout_seconds)
        self._worker_target = _stage_worker if _worker_target is None else _worker_target
        self.offline = _worker_target is not None
        self.origin_kind = "scripted_cpu_fixture" if self.offline else "natural_actor"
        self.process, self.connection = None, None
        self.started, self.closed = False, False
        self.group_owned = False

    def _terminate(self):
        self.closed = True
        if self.process is not None:
            try:
                owns_group = self.group_owned or (self.process.is_alive() and hasattr(os, "getpgid")
                                                  and os.getpgid(self.process.pid) == self.process.pid)
                if owns_group and hasattr(os, "killpg"):
                    # Also reap descendants after the stage leader exits normally.
                    os.killpg(self.process.pid, signal.SIGKILL)
                elif self.process.is_alive():
                        self.process.kill()
            except ProcessLookupError:
                pass
            self.process.join(timeout=5)
        if self.connection is not None:
            self.connection.close()

    def _receive(self, seconds):
        try:
            if not self.connection.poll(seconds):
                self._terminate()
                raise NativeTimeout("Native stage worker exceeded hard deadline; killed, no retry")
            packet = self.connection.recv()
        except NativeTimeout:
            raise
        except (EOFError, OSError) as exc:
            self._terminate()
            raise RuntimeError("Native stage worker exited without a result; no retry") from exc
        if packet["kind"] == "error":
            error = CapacityError(packet["message"]) if packet["error_type"] == "CapacityError" else RuntimeError(packet["error_type"] + ": " + packet["message"])
            error.raw = packet.get("raw")
            error.dispatched = packet.get("dispatched", True)
            if not isinstance(error, CapacityError):
                self._terminate()
            raise error
        return packet

    def start(self):
        if self.started or self.closed:
            raise ValueError("Stage cannot be started twice")
        if self.permit_live is not True and self._worker_target is _stage_worker:
            raise PermissionError("Explicit live start permission required")
        context = multiprocessing.get_context("spawn")
        self.connection, child = context.Pipe()
        self.process = context.Process(target=self._worker_target,
            args=(child, self.which, self.config, self.snapshot, self.permit_live))
        self.process.start()
        child.close()
        try:
            if self._receive(self.startup_timeout)["kind"] != "ready":
                raise RuntimeError("Native worker did not become ready")
            self.group_owned = hasattr(os, "getpgid") and os.getpgid(self.process.pid) == self.process.pid
            self.started = True
            return self
        except BaseException:
            self._terminate()
            raise

    def _request(self, method, request, timeout_seconds):
        if not self.started or self.closed:
            raise ValueError("Stage is not running")
        seconds = _seconds(timeout_seconds)
        self.connection.send({"method": method, "request": deepcopy(request), "timeout_seconds": seconds})
        packet = self._receive(seconds)
        if packet["kind"] != "result":
            raise RuntimeError("Unexpected native worker packet")
        return packet["value"]

    def generate(self, request, timeout_seconds):
        return self._request("generate", request, timeout_seconds)

    def generate_actor(self, request, timeout_seconds):
        return self._request("generate_actor", request, timeout_seconds)

    def close(self):
        if not self.closed and self.connection is not None:
            try:
                self.connection.send({"method": "close"})
                self.process.join(timeout=5)
            except (BrokenPipeError, EOFError, OSError):
                pass
        self._terminate()
