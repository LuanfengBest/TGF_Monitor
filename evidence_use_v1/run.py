"""One-use offline-assets campaign. No simulator, actor followups, or retries."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import time

from prospective_monitoring import native_backend as native
from prospective_monitoring.preflight import verify_asset_inventory
from prospective_monitoring.campaign import check_asset_inventory

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "project/evidence_use_diagnostic_2026-11-07"


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    with Path(path).open("x") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def verify_manifest():
    manifest = read(BUNDLE / "manifest.json")
    for name, digest in manifest["files"].items():
        path = ROOT / name
        if not path.is_file() or sha(path) != digest:
            raise ValueError("Frozen input/code changed: " + name)
    return manifest


def preflight():
    verify_manifest()
    cfg = read(BUNDLE / "config.json")
    requests = read(BUNDLE / "requests.json")
    admission = ROOT / "admission"
    admission.mkdir(exist_ok=False)
    start = time.monotonic()
    deadline = start + 1800
    receipt = {"ready": False, "model_calls": 0, "manifest_sha256": sha(BUNDLE / "manifest.json"),
               "job_id": os.environ.get("SLURM_JOB_ID"), "snapshots": cfg["snapshots"]}
    def expired(*_):
        raise TimeoutError("CPU admission deadline")
    signal.signal(signal.SIGALRM, expired)
    signal.alarm(1800)
    try:
        import jsonschema
        for request in requests:
            jsonschema.Draft202012Validator.check_schema(request["schema"])
        receipt["runtime"] = native.runtime_check(cfg)
        prior = read(ROOT / "airline_dev_v1/prior_assets.json")
        inventory, capacity = {}, []
        for which in ("monitor", "actor"):
            inventory[which] = verify_asset_inventory(cfg["snapshots"][which], which, prior[which], deadline)
            codec = native.NativeCodec(which, cfg["snapshots"][which])
            if which == "monitor":
                import xgrammar
                compiler = xgrammar.GrammarCompiler(xgrammar.TokenizerInfo.from_huggingface(codec.tokenizer))
            for req in requests:
                if req["model_slot"] != which:
                    continue
                if which == "monitor":
                    compiler.compile_json_schema(req["schema"])
                    ids = codec.monitor_prompt(req["prompt"])
                else:
                    ids = codec.actor_prompt([{"role": "user", "content": req["prompt"]}], [])
                if len(ids) + req["max_output_tokens"] > native.PINNED[which]["context"]:
                    raise native.CapacityError(req["request_id"])
                capacity.append({"request_id": req["request_id"], "prompt_tokens": len(ids),
                                 "reserved_output_tokens": req["max_output_tokens"],
                                 "prompt_token_sha256": hashlib.sha256(native.canonical(ids).encode()).hexdigest()})
        receipt.update(ready=True, asset_inventory=inventory, capacity=capacity)
    except Exception as exc:
        receipt["error"] = type(exc).__name__ + ": " + str(exc)
    finally:
        signal.alarm(0)
        receipt["elapsed_seconds"] = time.monotonic() - start
        write(admission / "preflight.json", receipt)
    print(json.dumps({k: receipt.get(k) for k in ("ready", "model_calls", "elapsed_seconds", "error")}), flush=True)
    if not receipt["ready"]:
        raise SystemExit(1)


class JudgeStage(native.NativeStageBackend):
    def generate_actor(self, request, timeout_seconds):
        raise PermissionError("No environment or followup generation in this campaign")

    def generate(self, req, timeout_seconds):
        if req["model_slot"] != self.which:
            raise ValueError("Wrong model loaded")
        cap = req["max_output_tokens"]
        limit = self.config["stage_output_caps"]["judge" if self.which == "monitor" else "secondary_judge"]
        if type(cap) is not int or not 0 < cap <= limit:
            raise ValueError("Output cap mismatch")
        if self.which == "monitor":
            return self._sample(self.codec.monitor_prompt(req["prompt"]), cap, req["seed"], timeout_seconds, req["schema"])
        ids = self.codec.actor_prompt([{"role": "user", "content": req["prompt"]}], [])
        raw = self._sample(ids, cap, req["seed"], timeout_seconds)
        raw["raw_text"] = raw["text"]
        try:
            messages = self.codec.parse_actor(raw["token_ids"], [], raw["finish_reason"])
            finals = [m["content"] for m in messages if m["channel"] == "final"]
            if len(finals) != 1:
                raise ValueError("One final answer required")
            raw.update(text=finals[0], tool_calls=[], channel="final")
        except (ValueError, KeyError, TypeError) as exc:
            raw.update(text="", parse_error=str(exc))
        return raw


def worker(connection, which, config, snapshot, permit_live):
    if hasattr(os, "setsid"):
        os.setsid()
    backend = None
    try:
        if permit_live is not True:
            raise PermissionError("Explicit one-use admission required")
        backend = JudgeStage(which, config, snapshot, permit_live=True).start()
        connection.send({"kind": "ready"})
        while True:
            packet = connection.recv()
            if packet["method"] == "close":
                return
            if packet["method"] != "generate":
                raise PermissionError("Only frozen Judge requests allowed")
            try:
                value = backend.generate(packet["request"], packet["timeout_seconds"])
                connection.send({"kind": "result", "value": value})
            except Exception as exc:
                connection.send({"kind": "error", "error_type": type(exc).__name__, "message": str(exc),
                                 "dispatched": not isinstance(exc, native.CapacityError), "raw": getattr(exc, "raw", None)})
    except (EOFError, BrokenPipeError):
        pass
    except Exception as exc:
        connection.send({"kind": "error", "error_type": type(exc).__name__, "message": str(exc), "dispatched": False})
    finally:
        if backend is not None:
            backend.close()
        connection.close()


def validate_output(raw, request):
    if raw.get("finish_reason") != "stop":
        return "truncated_or_nonstop", None
    if raw.get("parse_error"):
        return "invalid_native_output", None
    try:
        import jsonschema
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("Duplicate JSON key")
                result[key] = value
            return result
        parsed = json.loads(raw["text"], object_pairs_hook=unique)
        jsonschema.validate(parsed, request["schema"])
        return ("unknown" if parsed["score"] is None else "valid"), parsed
    except Exception:
        return "invalid_schema", None


def budget_check(calls, reserved, request, limits, remaining):
    if calls >= limits["max_calls"] or reserved + request["max_output_tokens"] > limits["max_output_tokens"]:
        raise RuntimeError("Dispatch/output reserve exhausted")
    if remaining <= 1:
        raise RuntimeError("Allocation deadline reached")


def campaign():
    verify_manifest()
    cfg = read(BUNDLE / "config.json")
    requests = read(BUNDLE / "requests.json")
    limits = cfg["limits"]
    if not os.environ.get("SLURM_JOB_ID") or os.environ.get("SLURM_JOB_ACCOUNT") != "cpsc4880":
        raise PermissionError("One admitted course allocation required")
    pre = read(ROOT / "admission/preflight.json")
    if not pre["ready"] or pre["job_id"] != os.environ["SLURM_JOB_ID"] or pre["manifest_sha256"] != sha(BUNDLE / "manifest.json"):
        raise ValueError("Fresh same-job preflight required")
    allocation_start = int(os.environ["TGF_ALLOCATION_START"])
    end = allocation_start + limits["wall_seconds"] - 30
    out = ROOT / "results"
    out.mkdir(exist_ok=False)
    write(out / "started.json", {"job_id": os.environ["SLURM_JOB_ID"], "allocation_start": allocation_start,
                                 "manifest_sha256": sha(BUNDLE / "manifest.json"), "planned_calls": len(requests)})
    calls, reserved, completed, tokens = 0, 0, [], 0
    failure = None
    capacity = {r["request_id"]: r for r in pre["capacity"]}
    try:
        for which in ("monitor", "actor"):
            check_asset_inventory(pre, which, cfg["revisions"][which])
            remaining = end - time.time()
            if remaining <= 1:
                raise RuntimeError("No allocation time remains for load")
            backend = native.ProcessStageBackend(which, cfg, cfg["snapshots"][which], permit_live=True,
                startup_timeout_seconds=min(remaining, limits["model_startup_seconds"]), _worker_target=worker)
            try:
                backend.start()
                for req in requests:
                    if req["model_slot"] != which:
                        continue
                    remaining = end - time.time()
                    budget_check(calls, reserved, req, limits, remaining)
                    slot = out / req["request_id"]
                    slot.mkdir(exist_ok=False)
                    write(slot / "dispatch.json", {"request_id": req["request_id"], "request_sha256": hashlib.sha256(native.canonical(req).encode()).hexdigest(),
                                                  "reserved_output_tokens": req["max_output_tokens"], "time_utc": datetime.now(timezone.utc).isoformat()})
                    calls += 1
                    reserved += req["max_output_tokens"]
                    raw = backend.generate(req, min(remaining, limits["call_seconds"]))
                    write(slot / "raw.json", raw)
                    if raw["prompt_sha256"] != capacity[req["request_id"]]["prompt_token_sha256"]:
                        raise ValueError("Native dispatch differs from admitted exact prompt")
                    tokens += raw["completion_tokens"]
                    status, parsed = validate_output(raw, req)
                    item = {"request_id": req["request_id"], "status": status, "output": parsed,
                            "completion_tokens": raw["completion_tokens"], "prompt_tokens": raw["prompt_tokens"],
                            "inference_seconds": raw["inference_seconds"]}
                    write(slot / "parsed.json", item)
                    completed.append(item)
                    print(json.dumps({"completed": len(completed), "planned": len(requests), "request": req["request_id"],
                                      "status": status, "actual_output_tokens": tokens}), flush=True)
            finally:
                backend.close()
    except Exception as exc:
        failure = type(exc).__name__ + ": " + str(exc)
    summary = {"job_id": os.environ["SLURM_JOB_ID"], "status": "completed" if failure is None and len(completed) == len(requests) else "stopped",
               "error": failure, "planned": len(requests), "dispatched": calls, "returned": len(completed),
               "reserved_output_tokens": reserved, "actual_returned_output_tokens": tokens,
               "allocation_elapsed_seconds": time.time() - allocation_start,
               "new_environment_rollouts": 0, "new_actor_followups": 0, "positions": completed,
               "unreturned_or_undispatched": [r["request_id"] for r in requests if r["request_id"] not in {x["request_id"] for x in completed}]}
    write(out / "summary.json", summary)
    write(out / "hashes.json", {str(f.relative_to(ROOT)): sha(f) for f in sorted(out.rglob("*.json"))})
    print(json.dumps({k: v for k, v in summary.items() if k != "positions"}), flush=True)
    if failure:
        raise SystemExit(1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("preflight", "campaign"))
    args = ap.parse_args()
    preflight() if args.mode == "preflight" else campaign()
