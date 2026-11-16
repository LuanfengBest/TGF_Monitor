"""Use the existing pinned Qwen/vLLM backend, with the NEW output contract."""
import hashlib
import json
import os
import time

from prospective_monitoring import native_backend as native
from . import core


class QwenStage(native.NativeStageBackend):
    def generate(self, request, timeout_seconds):
        return self._sample(self.codec.monitor_prompt(request["prompt"]), request["max_output_tokens"],
                            request["seed"], timeout_seconds, request["schema"])

    def generate_actor(self, *args, **kwargs):
        raise PermissionError("No Actor calls in this experiment")


def worker(connection, which, config, snapshot, permit_live):
    if hasattr(os, "setsid"):
        os.setsid()
    backend = None
    try:
        backend = QwenStage(which, config, snapshot, permit_live=permit_live).start()
        connection.send({"kind": "ready"})
        while True:
            packet = connection.recv()
            if packet["method"] == "close":
                return
            if packet["method"] != "generate":
                raise PermissionError("Only frozen classification calls")
            try:
                value = backend.generate(packet["request"], packet["timeout_seconds"])
                connection.send({"kind": "result", "value": value})
            except Exception as exc:
                connection.send({"kind": "error", "error_type": type(exc).__name__, "message": str(exc),
                                 "dispatched": True, "raw": getattr(exc, "raw", None)})
    except (EOFError, BrokenPipeError):
        pass
    except Exception as exc:
        connection.send({"kind": "error", "error_type": type(exc).__name__, "message": str(exc), "dispatched": False})
    finally:
        if backend:
            backend.close()
        connection.close()


def start_backend(bundle, config, rows, timeout):
    cfg = config["qwen"]
    begin = time.monotonic()
    runtime = native.runtime_check(cfg)
    path = native.snapshot_check(cfg["snapshot"], "monitor")
    inventory = json.loads((bundle / "qwen_assets.json").read_text())
    if inventory["revision"] != cfg["revisions"]["monitor"]:
        raise ValueError("Weight inventory revision mismatch")
    for name, expected in inventory["files"].items():
        if "/" in name or ".." in name:
            raise ValueError("Unsafe asset name")
        asset = path / name
        if asset.stat().st_size != expected["bytes"]:
            raise ValueError("Pinned model asset size differs: " + name)
        h = hashlib.sha256()
        with asset.open("rb") as stream:
            while chunk := stream.read(4 * 1024 * 1024):
                h.update(chunk)
                if time.monotonic() - begin > min(timeout - 30, config["limits"]["model_startup_seconds"]):
                    raise TimeoutError("Pinned asset hash check deadline")
        if h.hexdigest() != expected["sha256"]:
            raise ValueError("Pinned model asset hash differs: " + name)
    codec = native.NativeCodec("monitor", path)
    import xgrammar
    compiler = xgrammar.GrammarCompiler(xgrammar.TokenizerInfo.from_huggingface(codec.tokenizer))
    compiler.compile_json_schema(core.schema())
    capacity = {}
    for row in rows:
        if row["model"] == "qwen":
            ids = codec.monitor_prompt(core.qwen_prompt(row["state"]))
            if len(ids) + 2048 > cfg["native"]["monitor"]["context"]:
                raise ValueError("Full original record plus ledger exceeds context: " + row["request_id"])
            capacity[row["request_id"]] = {"prompt_tokens": len(ids), "reserved_output_tokens": 2048,
                "prompt_sha256": hashlib.sha256(native.canonical(ids).encode()).hexdigest()}
    ready = {"runtime": runtime, "model": cfg["models"]["monitor"], "revision": cfg["revisions"]["monitor"],
             "snapshot": str(path), "capacity": capacity, "temperature": 0, "enable_thinking": False,
             "job_id": os.environ.get("SLURM_JOB_ID"), "seed": 17, "max_num_seqs": 1}
    local_capacity = json.loads((bundle / "capacity_LOCAL.json").read_text())
    local_hashes = {r["request_id"]:r["prompt_sha256"] for r in local_capacity["requests"]}
    if any(local_hashes.get(rid) != value["prompt_sha256"] for rid,value in capacity.items()):
        raise ValueError("Cluster tokenizer differs from frozen local exact token sequence")
    remaining = min(timeout, config["limits"]["model_startup_seconds"]) - (time.monotonic() - begin)
    if remaining <= 0:
        raise TimeoutError("Model startup budget exhausted")
    backend = native.ProcessStageBackend("monitor", cfg, str(path), permit_live=True,
        startup_timeout_seconds=remaining,
        _worker_target=worker)
    backend.start()
    ready["startup_preflight_seconds"] = time.monotonic() - begin
    return backend, ready
