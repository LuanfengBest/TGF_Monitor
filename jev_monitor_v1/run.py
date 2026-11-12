"""Bounded single-attempt runner. Imports no label/reference material."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import time

from . import core

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "project/jev_monitor_2x2_2026-11-11"


def read(path):
    return core.strict_json(Path(path).read_text())


def write_once(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as f:
        f.write(core.canonical(data) + "\n")
        f.flush()
        os.fsync(f.fileno())


def filehash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_manifest(bundle):
    manifest = read(bundle / "manifest.json")
    for name, expected in manifest["files"].items():
        if filehash(ROOT / name) != expected:
            raise ValueError("Frozen file changed: " + name)
    return filehash(bundle / "manifest.json")


def planned(bundle):
    rows = [core.strict_json(x) for x in (bundle / "requests.jsonl").read_text().splitlines()]
    if len(rows) != 248 or len({r["request_id"] for r in rows}) != len(rows):
        raise ValueError("Incomplete/duplicate plan")
    for row in rows:
        core.public_record(row["state"]["record"])
        if row["state_sha256"] != core.digest(row["state"]):
            raise ValueError("State changed")
        expected = core.state(row["state"]["record"], row["arm"] in {"B", "D"})
        if expected != row["state"]:
            raise ValueError("Model state differs from public-only transformation")
    return rows


def http_jev(body, key, timeout):
    # requests does not retry by default. Explicit zero retries, no redirects.
    import requests
    def expired(*_):
        raise TimeoutError("Hard per-request wall deadline reached; outcome/usage may be unknown")
    previous = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, timeout)
    try:
        with requests.Session() as session:
            session.mount("https://", requests.adapters.HTTPAdapter(max_retries=0))
            response = session.post("https://api.typesafe.ai/v1/systemone", json=body,
                headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
                timeout=(min(10, timeout), timeout), allow_redirects=False)
            envelope = {"http_status": response.status_code, "text": response.text,
                        "request_id": response.headers.get("x-request-id"),
                        "headers": {k: response.headers.get(k) for k in ("date", "retry-after", "x-request-id")}}
            try:
                envelope["body"] = core.strict_json(response.text)
            except (ValueError, TypeError):
                envelope["body"] = None
            return envelope
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def ensure_smoke(bundle, model, seal):
    receipt = read(bundle / "results" / (model + "_smoke_passed.json"))
    if receipt["manifest_sha256"] != seal or receipt["interface_valid"] != 4:
        raise ValueError("Smoke receipt differs from current freeze")
    for rid, expected in receipt["result_hashes"].items():
        if filehash(bundle / "results" / rid / "result.json") != expected:
            raise ValueError("Smoke result changed")


def run_model(bundle, model, phase, key_file=None):
    bundle = Path(bundle).resolve()
    seal = verify_manifest(bundle)
    cfg, rows = read(bundle / "config.json"), planned(bundle)
    if model == "jev":
        if key_file:
            key_path = Path(key_file).expanduser()
            if key_path.stat().st_mode & 0o077:
                raise ValueError("Key file must be readable by its owner only (chmod 600)")
            key = key_path.read_text().strip()
        else:
            key = os.environ.get(cfg["jev_key_env"])
        if not key:
            raise RuntimeError("Set TYPESAFE_API_KEY or pass --jev-key-file outside the repository; never put the key in chat or this bundle")
    else:
        if not os.environ.get("SLURM_JOB_ID") or os.environ.get("SLURM_JOB_ACCOUNT") != cfg["gpu"]["account"]:
            raise RuntimeError("Qwen requires one checked course GPU allocation")
        ensure_smoke(bundle, "jev", seal)
    if phase == "development":
        ensure_smoke(bundle, "jev", seal)
        ensure_smoke(bundle, "qwen", seal)
    if model == "jev" and phase == "all":
        raise ValueError("Run Jev smoke first, then Qwen all, then Jev development")
    results = bundle / "results"
    results.mkdir(exist_ok=True)
    # Across resumed runs, unreturned dispatches are counted and never repeated.
    attempts = [read(p) for p in results.glob("*/dispatch.json")]
    if any(d["manifest_sha256"] != seal for d in attempts):
        raise ValueError("Different experiment already occupies results directory")
    start = time.monotonic()
    allocation_start = float(os.environ.get("JEV_ALLOCATION_START", time.time()))
    deadline = min(start + cfg["limits"]["wall_seconds"], start + cfg["limits"]["wall_seconds"] - (time.time() - allocation_start))
    backend, ready = None, None
    try:
        if model == "qwen":
            from .qwen_native import start_backend
            write_once(results / "qwen_allocation_claim.json", {"job_id": os.environ["SLURM_JOB_ID"], "manifest_sha256": seal})
            backend, ready = start_backend(bundle, cfg, rows, max(1, deadline - time.monotonic()))
            write_once(results / "qwen_ready.json", ready)
        active = [r for r in rows if r["model"] == model and (phase == "all" or r["phase"] == phase)]
        failures = 0
        for row in active:
            rid = row["request_id"]
            if phase == "all" and row["phase"] == "development":
                seal_smoke(bundle, model, rows, seal)
                ensure_smoke(bundle, "jev", seal)
            slot = results / rid
            if (slot / "dispatch.json").exists():
                old = read(slot / "dispatch.json")
                if old["request_sha256"] != core.digest(row):
                    raise ValueError("Resume request differs")
                continue
            remaining = deadline - time.monotonic()
            if remaining <= 5:
                break
            own_attempts = sum(d["model"] == model for d in attempts)
            if len(attempts) >= cfg["limits"]["total_actual_requests"] or own_attempts >= cfg["limits"][model + "_actual_requests"]:
                raise RuntimeError("Actual attempt cap reached")
            if model == "jev":
                reserved = (own_attempts + 1) * cfg["jev_per_question_context"]
                if reserved > cfg["jev_input_budget_tokens"] or reserved * cfg["jev_price_per_million_input_tokens_usd"] / 1e6 > cfg["api_usd_cap"]:
                    raise RuntimeError("API budget reserve exhausted")
            dispatch = {"request_id": rid, "model": model, "request_sha256": core.digest(row),
                        "manifest_sha256": seal, "started_at_utc": datetime.now(timezone.utc).isoformat(),
                        "job_id": os.environ.get("SLURM_JOB_ID"), "attempt": 1}
            write_once(slot / "dispatch.json", dispatch)
            attempts.append(dispatch)
            sent = time.monotonic()
            result = {"request_id": rid, "model": model, "status": "invalid", "verdict": None,
                      "usage": None, "usage_complete": False}
            fatal = False
            try:
                timeout = min(cfg["limits"]["call_timeout_seconds"], remaining - 3)
                if model == "jev":
                    raw = http_jev(core.jev_body(row["state"]), key, timeout)
                    write_once(slot / "raw.json", raw)
                    result["raw_sha256"] = filehash(slot / "raw.json")
                    payload = raw["body"]
                    if isinstance(payload, dict):
                        result["usage"] = payload.get("usage")
                        result["returned_model"] = payload.get("model")
                        result["usage_complete"] = isinstance((payload.get("usage") or {}).get("input_tokens"), int)
                    if raw["http_status"] != 200:
                        result.update(status="http_failure", http_status=raw["http_status"])
                        fatal = raw["http_status"] in {400, 401, 403, 413, 422}
                    else:
                        result.update(core.parse_response(model, payload))
                    if result["usage_complete"] and payload["usage"]["input_tokens"] > cfg["jev_per_question_context"]:
                        fatal = True
                        result["budget_anomaly"] = "provider usage exceeds reserved per-request context"
                else:
                    request = {"prompt": core.qwen_prompt(row["state"]), "schema": core.schema(),
                               "max_output_tokens": 2048, "seed": row["seed"]}
                    raw = backend.generate(request, timeout)
                    write_once(slot / "raw.json", raw)
                    result["raw_sha256"] = filehash(slot / "raw.json")
                    result.update(usage={"input_tokens": raw["prompt_tokens"], "output_tokens": raw["completion_tokens"]},
                                  usage_complete=True, returned_model=cfg["model_ids"]["qwen"],
                                  native_prompt_sha256=raw["prompt_sha256"])
                    if raw["prompt_sha256"] != ready["capacity"][rid]["prompt_sha256"]:
                        raise ValueError("Native dispatch differs from preflight tokens")
                    result.update(core.parse_response(model, raw))
            except Exception as exc:
                result.update(status="request_or_parse_failure", verdict=None, error=type(exc).__name__ + ": " + str(exc))
                result.pop("probabilities", None)
                # A native timeout kills its one-use worker; do not reload silently.
                if model == "qwen":
                    fatal = True
            result["latency_seconds"] = time.monotonic() - sent
            write_once(slot / "result.json", result)
            print(core.canonical({"request_id": rid, "status": result["status"], "attempted": len(attempts)}), flush=True)
            failures = failures + 1 if result["status"] in {"http_failure", "request_or_parse_failure"} else 0
            if fatal or failures >= 3:
                break
        if phase in {"smoke", "all"}:
            seal_smoke(bundle, model, rows, seal)
    finally:
        if backend is not None:
            backend.close()


def seal_smoke(bundle, model, rows, seal):
    path = bundle / "results" / (model + "_smoke_passed.json")
    if path.exists():
        ensure_smoke(bundle, model, seal)
        return
    hashes = {}
    for row in rows:
        if row["phase"] == "smoke" and row["model"] == model:
            result_path = bundle / "results" / row["request_id"] / "result.json"
            result = read(result_path)
            if result["status"] not in {"valid", "abstention"} or not result["usage_complete"]:
                raise RuntimeError("Interface smoke failed; no development calls permitted")
            hashes[row["request_id"]] = filehash(result_path)
    if len(hashes) != 4:
        raise ValueError("Expected four interface outputs")
    write_once(path, {"model": model, "manifest_sha256": seal, "interface_valid": 4,
                      "result_hashes": hashes, "accuracy_not_a_gate": True})


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", type=Path, default=DEFAULT)
    ap.add_argument("--model", required=True, choices=("jev", "qwen"))
    ap.add_argument("--phase", required=True, choices=("smoke", "development", "all"))
    ap.add_argument("--jev-key-file", type=Path)
    args = ap.parse_args()
    run_model(args.bundle, args.model, args.phase, args.jev_key_file)
