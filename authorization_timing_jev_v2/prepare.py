"""One-use materialization and separate immutable input freeze. No model inference."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random
import resource
import signal
import time
from jev_monitor_v1.core import canonical, digest
from jev_monitor_v1.run import write_once, filehash, read
from . import protocol

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "project/authorization_timing_jev_2026-11-12"
BUNDLE = PLAN / "run_01"


def materialize():
    begin = time.monotonic()
    if BUNDLE.exists():
        # Explicit recovery from an OS resource-limit setup error BEFORE imports,
        # configuration, requests or simulator attempts; never regenerate records.
        if not {p.name for p in BUNDLE.iterdir()} <= {"generation_claim.json", "preparation_recovery.json"}:
            raise FileExistsError("Existing preparation must not be regenerated")
        if not (BUNDLE / "preparation_recovery.json").exists():
            write_once(BUNDLE / "preparation_recovery.json", {"reason": "macOS rejected RSS rlimit before execution",
                "prior_simulator_attempts": 0, "prior_model_calls": 0})
    else:
        BUNDLE.mkdir()
        write_once(BUNDLE / "generation_claim.json", {"started_at_utc": datetime.now(timezone.utc).isoformat(),
            "user_authorization": "那就开始推进吧", "formal_booking_attempt_cap": 16})
    def expired(*_):
        raise TimeoutError("CPU preparation exceeded 15 minutes")
    signal.signal(signal.SIGALRM, expired)
    signal.alarm(900)
    resource.setrlimit(resource.RLIMIT_CPU, (3600, 3600))
    # Native libraries are kept single-threaded by the documented invocation.
    # macOS rejects an RSS rlimit here. The parent CPU supervisor enforces the
    # resident-memory cap and wall deadline using ps; retain measured peak below.
    from .dataset import build, smoke_fixtures
    cfg = read(PLAN / "config.json")
    assert digest(cfg["budget"]) == cfg["unchanged_budget_canonical_sha256_from_v01"]
    cfg.update(execution_authorized=True, status="authorized_frozen_run", run_id="authorization_timing_jev_v02_run01",
               authorization_basis="User: 那就开始推进吧; supersedes preparation-only restriction, all v0.2 resource caps retained.",
               run_order="jev smoke(4), qwen all(4+32) in one allocation, jev formal(32)",
               jev_wall_accounting="Total active Jev client time across smoke/formal <=20min; excludes intervening GPU queue/run time.")
    cfg["qwen"] = read(ROOT / "project/jev_monitor_2x2_2026-11-11/config.json")["qwen"]
    cfg["limits"] = {"model_startup_seconds": 1200, "qwen_call_timeout_seconds": 240}
    save = lambda name, value: write_once(BUNDLE / name, value)
    save("config.json", cfg)
    save("PAIR_SPEC.json", read(PLAN / "PAIR_SPEC.json"))
    records, references = build(cfg_spec := read(PLAN / "PAIR_SPEC.json")["pairs"], save)
    fixtures = smoke_fixtures()
    assert not {r["case_id"] for r in fixtures} & {r["case_id"] for r in records}
    save("records.json", records)
    save("references_PRIVATE.json", references)
    save("smoke_records.json", fixtures)
    save("smoke_provenance.json", {"kind": "hand_authored_synthetic_interface_only", "actual_simulator_calls": 0,
        "accuracy_evidence": False, "note": "Fixture receipt strings are synthetic; all 16 formal bookings have genuine simulator journals."})
    formal = [(r, arm) for r in sorted(records, key=lambda x: x["case_id"]) for arm in cfg["arms"]]
    random.Random(cfg["dispatch_seed"]).shuffle(formal)
    smoke = [(r, arm) for r in fixtures for arm in cfg["arms"]]
    requests = []
    for model in ("jev", "qwen"):
        for phase, slots in (("smoke", smoke), ("formal", formal)):
            for record, arm in slots:
                value = protocol.state(record, arm)
                requests.append({"request_id": f"{model}.{record['case_id']}.{arm}", "model": model,
                    "phase": phase, "case_id": record["case_id"], "arm": arm, "state": value,
                    "state_sha256": digest(value), "seed": 17,
                    "wire_sha256": digest(protocol.jev_body(value)) if model == "jev" else digest(protocol.qwen_prompt(value))})
    save("requests.json", requests)
    assets = read(ROOT / "project/jev_monitor_2x2_2026-11-11/qwen_assets.json")
    save("qwen_assets.json", assets)
    from tokenizers import Tokenizer
    from prospective_monitoring.native_backend import TOKENIZER_HASHES
    token_dir = ROOT / "project/jev_monitor_2x2_2026-11-11/tokenizer"
    for name, expected in TOKENIZER_HASHES.items():
        assert filehash(token_dir / name) == expected
    tokenizer = Tokenizer.from_file(str(token_dir / "tokenizer.json"))
    capacities = []
    for row in requests:
        if row["model"] != "qwen":
            continue
        prompt = protocol.qwen_prompt(row["state"])
        rendered = "<|im_start|>user\n" + prompt + "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
        ids = tokenizer.encode(rendered, add_special_tokens=False).ids
        assert len(ids) <= 30000 and len(ids)+512 <= 32768
        capacities.append({"request_id": row["request_id"], "prompt_tokens": len(ids),
                           "reserved_output_tokens": 512, "prompt_sha256": digest(ids)})
    save("capacity_LOCAL.json", {"requests": capacities, "tokenizer_hashes": TOKENIZER_HASHES,
        "max_prompt_tokens": max(r["prompt_tokens"] for r in capacities),
        "max_jev_request_utf8_bytes": max(len(canonical(protocol.jev_body(r["state"])).encode()) for r in requests if r["model"] == "jev"),
        "byte_count_is_not_a_jev_tokenizer": True})
    save("generation_receipt.json", {"formal_records": len(records), "pairs": 8, "reference_positive": 8,
        "reference_negative": 8, "actual_simulator_booking_attempts": 16, "model_calls": 0,
        "human_reviews": 0, "elapsed_seconds": time.monotonic()-begin,
        "max_rss_bytes_macos": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "all_references_resolved": True, "only_amendment_position_changes_within_pair": True})
    signal.alarm(0)
    print(canonical(read(BUNDLE / "generation_receipt.json")))


def freeze():
    assert read(BUNDLE / "AI_SOURCE_REVIEW.json")["passed"] is True
    assert read(BUNDLE / "OFFLINE_CHECKS.json")["passed"] is True
    assert not (BUNDLE / "results").exists()
    files = [p for p in BUNDLE.rglob("*") if p.is_file()]
    files += list((ROOT / "authorization_timing_jev_v2").glob("*.py"))
    files += list((ROOT / "authorization_timing_jev_v2").glob("*.sh"))
    files += list((ROOT / "authorization_timing_jev_v2").glob("*.sbatch"))
    for directory in ("prospective_monitoring", "prospective_data_v2", "datasets/dual_objective/agent"):
        files += [p for p in (ROOT / directory).rglob("*.py") if "__pycache__" not in p.parts]
    files += [ROOT / p for p in ("jev_monitor_v1/core.py", "jev_monitor_v1/run.py", "jev_monitor_v1/qwen_native.py", "jev_monitor_v1/__init__.py", "matched_followup_v2/native.py")]
    files += [PLAN / name for name in ("PROTOCOL.md", "METRICS.md", "BUDGET.md", "config.json", "PAIR_SPEC.json")]
    write_once(BUNDLE / "manifest.json", {"files": {str(p.relative_to(ROOT)): filehash(p) for p in sorted(set(files))},
        "created_at_utc": datetime.now(timezone.utc).isoformat(), "model_calls_at_freeze": 0,
        "authorization": read(BUNDLE / "config.json")["authorization_basis"]})
    print(canonical({"manifest_sha256": filehash(BUNDLE / "manifest.json"), "files": len(set(files))}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("materialize", "freeze"))
    action = parser.parse_args().action
    materialize() if action == "materialize" else freeze()
