"""Offline reproduction of the saved timing run; never submit or infer.

Original preparation artifacts retain their creation-time no-launch state.
run_01/config.json records the subsequent user authorization for this run.
"""
import ast
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = Path(__file__).resolve().parent / "run_01"
sys.path.insert(0, str(ROOT))


def guard(event, args):
    if event in {"socket.connect", "socket.connect_ex", "socket.getaddrinfo", "subprocess.Popen", "os.system", "os.posix_spawn"}:
        raise RuntimeError("Offline verifier blocks network/subprocess: " + event)


def same(a, b):
    if isinstance(a, dict):
        assert isinstance(b, dict) and set(a) == set(b)
        for k in a:
            same(a[k], b[k])
    elif isinstance(a, list):
        assert isinstance(b, list) and len(a) == len(b)
        for x, y in zip(a, b):
            same(x, y)
    elif isinstance(a, float):
        assert math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-8), (a, b)
    else:
        assert a == b, (a, b)


def main():
    sys.addaudithook(guard)
    from jev_monitor_v1.core import digest, parse_response
    from jev_monitor_v1.run import read, filehash
    from authorization_timing_jev_v2.run import planned
    from authorization_timing_jev_v2.score import score
    seal = filehash(BUNDLE / "manifest.json")
    omitted = []
    local_receipt = "project/authorization_timing_jev_2026-11-12/run_01/LOCAL_READINESS.json"
    for name, expected in read(BUNDLE / "manifest.json")["files"].items():
        if name == local_receipt and not (ROOT / name).exists():
            omitted.append({"path": name, "sha256": expected, "reason": "local account/balance preflight receipt; no analysis inputs"})
            continue
        assert filehash(ROOT / name) == expected, name
    cfg, rows = read(BUNDLE / "config.json"), planned(BUNDLE)
    assert cfg["execution_authorized"] is True
    assert digest(cfg["budget"]) == "78f7365228d26a6e3f9ee657c65fd8a90cc60f6f9ac6d0a3e2ba5dc9a6474f00"
    results_manifest = read(BUNDLE / "RESULT_HASHES.json")
    for name, expected in results_manifest.items():
        assert filehash(BUNDLE / name) == expected, name
    attempts = []
    formal_dispatched = formal_returned = 0
    for row in rows:
        slot = BUNDLE / "results" / row["request_id"]
        if not (slot / "dispatch.json").exists():
            assert not (slot / "result.json").exists()
            continue
        dispatch = read(slot / "dispatch.json")
        assert dispatch["manifest_sha256"] == seal and dispatch["request_sha256"] == digest(row) and dispatch["attempt"] == 1
        attempts.append(dispatch)
        formal_dispatched += row["phase"] == "formal"
        if (slot / "result.json").exists():
            formal_returned += row["phase"] == "formal"
            result = read(slot / "result.json")
            if result.get("raw_sha256"):
                assert filehash(slot / "raw.json") == result["raw_sha256"]
            if result["status"] in {"valid", "abstention"}:
                raw = read(slot / "raw.json")
                parsed = parse_response(row["model"], raw["body"] if row["model"] == "jev" else raw)
                assert all(result[k] == v for k,v in parsed.items())
    assert len(attempts) <= 72
    assert all(sum(d["model"] == m for d in attempts) <= 36 for m in ("jev", "qwen"))
    analysis = score(BUNDLE)
    same(analysis, read(BUNDLE / "analysis.json"))
    assert analysis["usage"]["jev"]["reserved_api_usd_all_attempts"] <= .10
    assert analysis["usage"]["qwen"]["output_tokens_known"] <= 18432
    accounting = read(BUNDLE / "cluster/accounting_final.json")
    assert not accounting["queue"]["stdout"].strip()
    submission = read(BUNDLE / "cluster/submission_receipt.json")
    assert submission["wall_limit_minutes"] == 30 and submission["gpu_count"] == 1
    jobrow = next(line for line in accounting["accounting"]["stdout"].splitlines() if line.startswith(submission["job_id"]+"|"))
    elapsed = jobrow.split("|")[3]
    h, m, s = map(int, elapsed.split(":"))
    assert h*3600+m*60+s <= 1800
    # Archive integrity is not experiment success. The frozen scorer's zeros
    # on entirely missing groups are not measured accuracy or a null effect.
    outcome = read(BUNDLE / "RUN_OUTCOME.json")
    assert jobrow.split("|")[1:3] == ["FAILED", "1:0"]
    assert read(BUNDLE / "results/STOP.json") == accounting["stop"]
    assert accounting["stop"]["error_type"] == "NativeTimeout"
    assert accounting["stop"]["completed_slots"] == 0
    assert accounting["qwen_ready"] is False and accounting["qwen_finished"] is False
    assert len(attempts) == 4 and all(d["model"] == "jev" for d in attempts)
    assert formal_dispatched == formal_returned == 0
    assert outcome["status"] == "stopped_qwen_startup_timeout"
    assert outcome["scientific_conclusion_available"] is False
    assert outcome["primary_effect"] is None
    assert outcome["formal_dispatched"] == formal_dispatched
    assert outcome["formal_returned"] == formal_returned
    assert outcome["formal_planned"] == 64
    assert outcome["h200_seconds"] == h*3600+m*60+s
    assert outcome["jev_estimated_api_usd"] == analysis["usage"]["jev"]["estimated_api_usd_known"]
    assert all(g["status_counts"] == {"missing": 16} for g in analysis["groups"].values())
    assert len(list((BUNDLE / "booking_attempts").glob("*.json"))) == 16
    old = {}
    for name in ("jev_monitor_2x2_2026-11-11", "jev_tgf_mainline_2026-11-12"):
        directory = ROOT / "project" / name
        # These campaigns use different manifest filenames/shape; use only known
        # frozen file maps and never their run entrypoints.
        candidates = [directory / "manifest.json", directory / "freeze.json"]
        found = next((p for p in candidates if p.exists()), None)
        if found is not None and "files" in read(found):
            for path, expected in read(found)["files"].items():
                assert filehash(ROOT / path) == expected
            old[name] = {"manifest_sha256": filehash(found), "files": len(read(found)["files"])}
    for source in (ROOT / "authorization_timing_jev_v2").glob("*.py"):
        ast.parse(source.read_text())
    receipt = {"passed": True, "pass_meaning": "archive_integrity_only_not_experiment_success",
               "scope": "saved_results_only_no_network_no_subprocess_no_models",
               "manifest_sha256": seal, "frozen_files_verified": len(read(BUNDLE / "manifest.json")["files"])-len(omitted),
               "local_only_receipts": omitted,
               "result_files_verified": len(results_manifest), "attempts": len(attempts),
               "experiment_status": outcome["status"], "formal_returned": formal_returned,
               "formal_planned": 64, "primary_effect": None,
               "job_id": submission["job_id"], "elapsed_gpu_seconds": h*3600+m*60+s,
               "old_manifests": old, "human_reviews": 0, "analysis_reproduced": True}
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
