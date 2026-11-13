"""Fail-closed, single-attempt runner; never imports private labels or simulator."""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import time
from jev_monitor_v1.core import digest, parse_response, schema
from jev_monitor_v1.run import read, write_once, filehash, verify_manifest, http_jev
from . import protocol

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "project/authorization_timing_jev_2026-11-12/run_01"


def planned(bundle):
    rows = read(bundle / "requests.json")
    if len(rows) != 72 or len({r["request_id"] for r in rows}) != 72:
        raise ValueError("Plan must contain exactly 72 unique slots")
    records = {r["case_id"]: r for r in read(bundle / "records.json")+read(bundle / "smoke_records.json")}
    for row in rows:
        if row["state"] != protocol.state(records[row["case_id"]], row["arm"]) or digest(row["state"]) != row["state_sha256"]:
            raise ValueError("Public transformation changed")
        wire = protocol.jev_body(row["state"]) if row["model"] == "jev" else protocol.qwen_prompt(row["state"])
        if digest(wire) != row["wire_sha256"]:
            raise ValueError("Wire prompt changed")
    return rows


def admission(cfg, attempts, model):
    own = sum(d["model"] == model for d in attempts)
    if len(attempts) >= 72 or own >= 36:
        raise RuntimeError("Attempt cap reached")
    if model == "jev" and (own+1)*cfg["budget"]["jev_reserved_usd_per_attempt"] > cfg["budget"]["jev_client_budget_usd"]:
        raise RuntimeError("API reserve cap reached")


def ensure_smoke(bundle, model, seal):
    receipt = read(bundle / "results" / (model + "_smoke_passed.json"))
    if receipt["manifest_sha256"] != seal or len(receipt["result_hashes"]) != 4:
        raise ValueError("Smoke not passed for this frozen run")
    for rid, expected in receipt["result_hashes"].items():
        if filehash(bundle / "results" / rid / "result.json") != expected:
            raise ValueError("Smoke result changed")


def seal_smoke(bundle, model, rows, seal):
    target = bundle / "results" / (model + "_smoke_passed.json")
    if target.exists():
        ensure_smoke(bundle, model, seal)
        return
    hashes = {}
    for row in rows:
        if row["model"] == model and row["phase"] == "smoke":
            path = bundle / "results" / row["request_id"] / "result.json"
            result = read(path)
            if result["status"] not in {"valid", "abstention"} or not result["usage_complete"]:
                raise ValueError("Interface smoke failed")
            hashes[row["request_id"]] = filehash(path)
    if len(hashes) != 4:
        raise ValueError("Incomplete smoke")
    write_once(target, {"manifest_sha256": seal, "result_hashes": hashes,
                       "accuracy_not_a_gate": True, "interface_valid": 4})


def run(bundle, model, phase, key_file):
    bundle = bundle.resolve()
    seal = verify_manifest(bundle)
    cfg, rows = read(bundle / "config.json"), planned(bundle)
    if not cfg["execution_authorized"] or digest(cfg["budget"]) != cfg["unchanged_budget_canonical_sha256_from_v01"]:
        raise PermissionError("Missing authorization or changed budget")
    if (model, phase) not in {("jev", "smoke"), ("qwen", "all"), ("jev", "formal")}:
        raise ValueError("Fixed phase ordering only")
    results = bundle / "results"
    results.mkdir(exist_ok=True)
    if (results / "STOP.json").exists():
        raise RuntimeError("Campaign stopped; no automatic continuation/retry")
    if model == "qwen" or phase == "formal":
        ensure_smoke(bundle, "jev", seal)
    if phase == "formal":
        ensure_smoke(bundle, "qwen", seal)
        if read(results / "qwen_all_finished.json")["completed_slots"] != 36:
            raise ValueError("Qwen did not finish its bounded allocation")
    attempts = [read(p) for p in results.glob("*/dispatch.json")]
    if any(d["manifest_sha256"] != seal for d in attempts):
        raise ValueError("Foreign attempt ledger")
    active = [r for r in rows if r["model"] == model and (phase == "all" or r["phase"] == phase)]
    if any((results / r["request_id"] / "dispatch.json").exists() for r in active):
        raise RuntimeError("One or more slots already dispatched; no repeat")
    key = None
    if model == "jev":
        key_path = Path(key_file).expanduser()
        if key_path.stat().st_mode & 0o077 or key_path.stat().st_uid != os.getuid():
            raise ValueError("API key must be owned by current user and owner-only")
        key = key_path.read_text().strip()
        if not key:
            raise ValueError("Empty API key")
    else:
        if not os.environ.get("SLURM_JOB_ID") or os.environ.get("SLURM_JOB_ACCOUNT") != "cpsc4880":
            raise PermissionError("Expected course allocation")
    start = time.monotonic()
    previous_jev = sum(read(p)["elapsed_seconds"] for p in results.glob("jev_*_finished.json"))
    wall = 1200-previous_jev if model == "jev" else 1800-max(0, time.time()-float(os.environ["TIMING_ALLOCATION_START"]))
    deadline = start+wall
    claim = {"manifest_sha256": seal, "started_at_utc": datetime.now(timezone.utc).isoformat(),
             "job_id": os.environ.get("SLURM_JOB_ID"), "wall_remaining_seconds": wall}
    write_once(results / f"{model}_{phase}_claim.json", claim)
    backend, completed = None, 0
    try:
        if model == "qwen":
            from .qwen_native import start_backend
            backend, ready = start_backend(bundle, cfg, rows, max(1, deadline-time.monotonic()-10))
            write_once(results / "qwen_ready.json", ready)
        for row in active:
            if row["phase"] == "formal":
                seal_smoke(bundle, model, rows, seal)
            remaining = deadline-time.monotonic()
            if remaining <= 5:
                raise TimeoutError("Campaign wall limit reached")
            admission(cfg, attempts, model)
            rid = row["request_id"]
            slot = results / rid
            dispatch = {"request_id": rid, "model": model, "phase": row["phase"],
                        "manifest_sha256": seal, "request_sha256": digest(row), "attempt": 1,
                        "started_at_utc": datetime.now(timezone.utc).isoformat(), "job_id": os.environ.get("SLURM_JOB_ID")}
            write_once(slot / "dispatch.json", dispatch)  # Count unknown/lost responses as attempts.
            attempts.append(dispatch)
            sent = time.monotonic()
            result = {"request_id": rid, "model": model, "status": "invalid", "verdict": None,
                      "usage": None, "usage_complete": False}
            try:
                if model == "jev":
                    raw = http_jev(protocol.jev_body(row["state"]), key, min(30, remaining-3))
                    write_once(slot / "raw.json", raw)
                    if raw["http_status"] != 200:
                        result.update(status="http_failure", http_status=raw["http_status"])
                        raise RuntimeError("HTTP failure; no retry")
                    payload = raw["body"]
                    result.update(parse_response(model, payload), usage=payload.get("usage"), returned_model=payload.get("model"))
                    used = (result["usage"] or {}).get("input_tokens")
                    if type(used) is not int or used < 0 or used > 32768:
                        raise ValueError("Missing/invalid/out-of-reserve usage")
                    result["usage_complete"] = True
                else:
                    raw = backend.generate({"prompt": protocol.qwen_prompt(row["state"]), "schema": schema(),
                        "max_output_tokens": 512, "seed": 17}, min(240, remaining-3))
                    write_once(slot / "raw.json", raw)
                    ready_row = ready["capacity"][rid]
                    if raw["prompt_sha256"] != ready_row["prompt_sha256"] or raw["prompt_tokens"] != ready_row["prompt_tokens"]:
                        raise ValueError("Native token sequence changed")
                    result.update(parse_response(model, raw), usage={"input_tokens": raw["prompt_tokens"], "output_tokens": raw["completion_tokens"]},
                                  returned_model="Qwen/Qwen3-32B", usage_complete=True)
                    if raw["completion_tokens"] > 512:
                        raise ValueError("Output budget exceeded")
                if result["status"] not in {"valid", "abstention"}:
                    raise ValueError("Interface unavailable; campaign stops")
            except Exception as exc:
                if result["status"] in {"valid", "abstention"}:
                    result.update(status="invalid", verdict=None)
                result["error_type"] = type(exc).__name__  # No secret-bearing exception strings.
                raise
            finally:
                result["latency_seconds"] = time.monotonic()-sent
                if (slot / "raw.json").exists():
                    result["raw_sha256"] = filehash(slot / "raw.json")
                write_once(slot / "result.json", result)
            completed += 1
            print(f"{model} {phase}: {completed}/{len(active)} interface-valid", flush=True)
        if phase in {"smoke", "all"}:
            seal_smoke(bundle, model, rows, seal)
        write_once(results / f"{model}_{phase}_finished.json", {"completed_slots": completed,
            "elapsed_seconds": time.monotonic()-start, "manifest_sha256": seal, "job_id": os.environ.get("SLURM_JOB_ID")})
    except Exception as exc:
        write_once(results / "STOP.json", {"model": model, "phase": phase, "error_type": type(exc).__name__,
            "completed_slots": completed, "elapsed_seconds": time.monotonic()-start, "no_retry": True})
        print(f"STOP: {model}/{phase}: {type(exc).__name__}; no retry", flush=True)
        raise SystemExit(1)
    finally:
        if backend:
            backend.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", type=Path, default=DEFAULT)
    ap.add_argument("--model", choices=("jev", "qwen"), required=True)
    ap.add_argument("--phase", choices=("smoke", "formal", "all"), required=True)
    ap.add_argument("--key-file", default="/Users/a1234/.config/typesafe/api_key")
    args = ap.parse_args()
    run(args.bundle, args.model, args.phase, args.key_file)
