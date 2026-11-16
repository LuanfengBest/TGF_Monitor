"""Read-only CPU verification of the report's principal result cohorts.

Uses the original scoring/validation functions and compares their complete
outputs with saved reports. Only fresh analysis timestamps are excluded from
two comparisons. Does not regenerate author reviews or run a simulator/model.
"""
from collections import Counter, defaultdict
from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import runpy
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def readonly_guard(event, args):
    if event.startswith("socket.") or event in {
        "subprocess.Popen", "os.system", "os.posix_spawn", "os.fork",
        "os.remove", "os.rename", "os.mkdir", "os.rmdir", "os.truncate",
        "os.link", "os.symlink", "os.chmod", "os.utime",
    }:
        raise RuntimeError("Read-only verification forbids " + event)
    if event == "open":
        mode, flags = args[1], args[2]
        if (isinstance(mode, str) and any(c in mode for c in "wax+")) or (
            isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)
        ):
            raise RuntimeError("Read-only verification forbids file writes")
    if event == "import" and args[0].split(".")[0] in {
        "torch", "transformers", "vllm", "openai_harmony", "xgrammar",
    }:
        raise RuntimeError("Model-runtime imports are not part of offline verification")


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def verify_map(base, hashes):
    base = Path(base).resolve()
    for name, expected in hashes.items():
        relative = Path(name)
        require(not relative.is_absolute() and ".." not in relative.parts, "Unsafe manifest path: " + name)
        path = base / relative
        require(path.resolve().is_relative_to(base), "Escaping manifest path: " + name)
        require(path.is_file() and sha(path) == expected, "Missing or changed file: " + str(path))
    return len(hashes)


def same(actual, expected, label, omit=()):
    actual = {k: v for k, v in actual.items() if k not in omit} if isinstance(actual, dict) else actual
    expected = {k: v for k, v in expected.items() if k not in omit} if isinstance(expected, dict) else expected
    if actual != expected:
        keys = sorted(k for k in set(actual) | set(expected) if actual.get(k) != expected.get(k)) if isinstance(actual, dict) and isinstance(expected, dict) else []
        raise ValueError(label + " differs from saved result; differing top-level fields: " + repr(keys))


def historical_alignment():
    base = ROOT / "project/evaluation_alignment_2026-11-05"
    scoring = module("tgf_saved_alignment", base / "offline_eval.py")
    outcomes = {}
    for name in ("dev64", "natural24"):
        folder = base / "data" / name
        refs = scoring.read_jsonl(folder / "references_PRIVATE.jsonl")
        predictions = scoring.read_jsonl(folder / "predictions_PRIVATE.jsonl")
        result = scoring.score(read(folder / "contract.json"), refs, predictions, scoring.read_jsonl(folder / "public_inputs.jsonl"))
        same(result, read(folder / "report.json"), "Historical alignment " + name)
        outcomes[name] = {"records": len(refs), "prediction_rows": len(predictions), "exact_saved_report_match": True}
    return outcomes


def natural_collection():
    from prospective_data_v2.prepare import validate_manifest
    from prospective_data_v2.specs import digest
    from prospective_monitoring.reference import evaluate_reference
    from prospective_monitoring.simulator import project_state

    base = ROOT / "project/new_data_collection_2026-11-05"
    campaign = base / "cluster_results_32257283/campaign"
    frozen = validate_manifest(read(ROOT / "project/new_data_preparation_2026-11-05/frozen_specifications/manifest_PRIVATE.json"))
    files = verify_map(campaign, read(campaign / "file_hashes.json"))
    verify_map(base, read(base / "REVIEW_ARTIFACT_SHA256.json"))
    reviewed = {r["case_id"]: r for r in read(base / "author_review_2026-11-06/author_review_PRIVATE.json")["cases"]}
    require(len(frozen["tasks"]) == len(reviewed) == 48, "Natural collection denominator changed")
    counts = defaultdict(Counter)
    raw_calls = events = 0
    for task in frozen["tasks"]:
        folder = campaign / "cases" / task["case_id"]
        result, evidence = read(folder / "result_private.json"), read(folder / "execution_evidence_private.json")
        require(read(folder / "task_private.json") == task, "Frozen natural task changed")
        require(result["origin_kind"] == evidence["origin_kind"] == "natural_actor", "Natural provenance changed")
        require(digest(result["conversation"]) == result["conversation_sha256"], "Conversation digest mismatch")
        require(result["journal"] == evidence["journal"], "Execution journal mismatch")
        ref = evaluate_reference(result["contract"], evidence["journal"])
        same(ref, result["reference"], "Natural reference " + task["case_id"])
        review = reviewed[task["case_id"]]
        require(ref["status"] == review["reference_status"] and ref["label"] == review["label"], "Reference/author label disagreement")
        counts[task["environment"]][str(ref["label"])] += 1
        receipts = evidence["raw_tool_receipts"]
        journal_events = result["journal"]["events"]
        require(len(receipts) == len(journal_events), "Tool receipt count mismatch")
        previous = None
        for raw, event in zip(receipts, journal_events):
            for phase in ("before", "after"):
                require(digest(raw[phase + "_raw"]) == raw[phase + "_sha256"], "Raw state digest mismatch")
                require(project_state(raw[phase + "_raw"], task["environment"]) == event[phase], "Recorded state projection mismatch")
            require(previous is None or previous == raw["before_raw"], "Broken state chain")
            previous = raw["after_raw"]
            require(all(raw[k] == event[k] for k in ("event_id", "call_source_id", "result_source_id")), "Source pointer mismatch")
        events += len(journal_events)
        for turn in sorted((folder / "turns").glob("turn_*")):
            request = read(turn / "request.json")
            require(digest(request) == read(turn / "request_hash.json")["sha256"], "Natural request hash mismatch")
            if (turn / "dispatch.json").exists():
                claim = campaign / "calls" / f"{task['case_id']}-{request['turn_index']:02d}.json"
                require(read(claim)["request_sha256"] == digest(request), "Missing or mismatched dispatch claim")
            if (turn / "raw.json").is_file():
                require(read(turn / "raw.json")["usage_mode"] == "native_model_usage", "Non-native call in natural collection")
                raw_calls += 1
    expected = read(base / "author_review_2026-11-06/coverage_screen.json")
    for environment, labels in counts.items():
        same(dict(labels), expected["groups"][environment]["labels"], "Natural coverage " + environment)
    require(raw_calls == 155, "Natural actor call count changed")
    return {"job_id": "32257283", "records": 48, "actor_calls": raw_calls, "recorded_tool_events": events,
            "verified_campaign_files": files, "labels": {k: dict(v) for k, v in counts.items()},
            "saved_reference_and_coverage_match": True, "review_is_not_human_gold": True}


def four_strategy():
    from airline_dev_v1.report import predictions, analyze
    base = ROOT / "project/airline_monitor_comparison_2026-11-06"
    contract, refs, rows, public, summary = predictions(base / "bundle", base / "cluster_results_32354336/comparison")
    result = analyze(contract, refs, rows, public)
    result["run_usage"] = {k: summary[k] for k in ("dispatched_calls", "elapsed_seconds", "output_tokens_or_failed_reserve", "close_reason")}
    same(rows, read(base / "report_32354336/predictions_PRIVATE.json"), "Four-strategy predictions")
    same(result, read(base / "report_32354336/report_PRIVATE.json"), "Four-strategy report")
    return {"job_id": "32354336", "records": 24, "judgments": len(rows), "model_calls": summary["dispatched_calls"], "exact_saved_report_match": True}


def fixed_operation():
    from anchored_question_v1.report import report
    base = ROOT / "project/anchored_question_diagnostic_2026-11-06"
    rows, result = report(base / "bundle", base / "cluster_results_32374475/comparison")
    same(rows, read(base / "report_32374475/predictions_PRIVATE.json"), "Fixed-operation predictions")
    same(result, read(base / "report_32374475/report_PRIVATE.json"), "Fixed-operation report")
    return {"job_id": "32374475", "records": 24, "judgments": len(rows), "model_calls": result["run_usage"]["dispatched_calls"], "exact_saved_report_match": True}


def evidence_probe(name, job):
    base = ROOT / "project" / name
    analyzer = module("tgf_saved_probe_" + job, base / "analyze_results.py")
    result = analyzer.analyze(base / ("cluster_results_" + job))
    same(result, read(base / ("analysis_" + job + ".json")), "Evidence probe " + job, omit=("created_at_utc",))
    return {"job_id": job, "planned": result["planned"], "returned": result["returned"],
            "statuses": dict(Counter(r["status"] for r in result["rows"])),
            "saved_analysis_match_except_creation_timestamp": True}


def main():
    require(not sys.flags.optimize, "Do not use python -O; original validators rely on assertions")
    sys.addaudithook(readonly_guard)
    output = {"read_only": True, "new_model_calls": 0, "new_simulator_episodes": 0,
              "network_and_child_processes_forbidden": True}
    for name, callback in (
        ("historical_alignment", historical_alignment),
        ("natural_collection", natural_collection),
        ("four_strategy", four_strategy),
        ("fixed_operation", fixed_operation),
        ("evidence_use", lambda: evidence_probe("evidence_use_diagnostic_2026-11-07", "32425664")),
        ("evidence_claim", lambda: evidence_probe("evidence_claim_probe_2026-11-07", "32446760")),
    ):
        output[name] = callback()
        print(name + ": verified", file=sys.stderr, flush=True)
    captured = io.StringIO()
    with redirect_stdout(captured):
        runpy.run_path(str(HERE / "offline_verify.py"), run_name="__main__")
    output["final_validation"] = json.loads(captured.getvalue())
    print("final_validation: verified", file=sys.stderr, flush=True)
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
