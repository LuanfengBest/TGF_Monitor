"""Read-only CPU reporting for a prospective DEVELOPMENT campaign.

Usage: python project/prospective_monitoring/reporting/pilot_report.py
           --run /path/to/retrieved/run --output /path/to/new/report-directory

This module lives outside the hashed runtime package. It never dispatches models,
executes tools, submits jobs, repairs predictions, or changes original artifacts.
"""
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import sys

REPOSITORY = Path(__file__).resolve().parents[3]
if str(REPOSITORY) not in sys.path:
    sys.path.insert(0, str(REPOSITORY))
from prospective_monitoring.analysis import ARMS, analyze, cost_summary, decision


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def read_json(path, default=None):
    path = Path(path)
    if not path.exists():
        return deepcopy(default)
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key in " + str(path))
            result[key] = value
        return result
    def constant(value):
        raise ValueError("Nonfinite JSON value: " + value)
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs, parse_constant=constant)


def file_hashes(directory):
    result = {}
    for path in sorted(Path(directory).rglob("*")):
        if path.is_symlink():
            raise ValueError("Symlinked run artifacts are not accepted: " + str(path))
        if path.is_file():
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
            result[str(path.relative_to(directory))] = digest.hexdigest()
    return result


def _identity(row):
    return tuple(row.get(key) for key in ("case_id", "environment", "family_id", "split"))


def _index(rows, expected):
    result = {}
    for row in rows:
        case_id = row.get("case_id")
        if case_id not in expected or case_id in result:
            raise ValueError("Unknown/duplicate result case: " + str(case_id))
        if _identity(row) != _identity(expected[case_id]):
            raise ValueError("Result identity differs from manifest: " + case_id)
        result[case_id] = row
    return result


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _call_ledger(run, tasks, config):
    calls, totals, statuses = [], {}, Counter()
    for path in sorted((run / "calls").glob("*")):
        if not path.is_dir():
            continue
        archived = read_json(path / "request.json", {})
        request = archived.get("request", {})
        outcome = read_json(path / "outcome.json", {})
        raw = read_json(path / "raw.json")
        marker = (path / "dispatched.json").exists()
        dispatched = outcome.get("dispatched", marker)
        if type(dispatched) is not bool:
            raise ValueError("Call dispatched status must be boolean")
        prefix = path.name.split(".", 1)[0]
        index = int(prefix[1:]) if prefix.startswith("c") and prefix[1:].isdigit() else None
        if index is None or index >= len(tasks):
            raise ValueError("Unbound call slot: " + path.name)
        stage = request.get("stage")
        if ".collection." in path.name:
            stage = "collection"
        if stage not in {"collection", "planner", "review", "actor", "judge"}:
            raise ValueError("Unknown call stage: " + path.name)
        parts = path.name.split(".")
        arm = parts[1] if len(parts) > 1 and parts[1] in ARMS else None
        model_kind = "actor" if stage in {"collection", "actor"} else "monitor"
        model = request.get("model") or config.get("models", {}).get(model_kind, model_kind)
        status = outcome.get("status", "dispatched_without_outcome" if dispatched else "unattempted_claim")
        valid_usage = (dispatched and isinstance(raw, dict) and raw.get("usage_complete", True) is True
                       and all(type(raw.get(k)) is int and raw[k] >= 0 for k in ("prompt_tokens", "completion_tokens"))
                       and _finite(raw.get("inference_seconds")))
        mode = raw.get("usage_mode", "unspecified_backend_usage") if isinstance(raw, dict) else None
        call = {"slot": path.name, "case_id": tasks[index]["case_id"], "stage": stage,
                "arm": arm, "model": model, "dispatched": dispatched, "status": status,
                "verified_usage": bool(valid_usage), "usage_mode": mode,
                "error": outcome.get("error")}
        if valid_usage:
            values = {"input_tokens": raw["prompt_tokens"], "output_tokens": raw["completion_tokens"],
                      "inference_seconds": raw["inference_seconds"]}
            call["usage"] = values
            total = totals.setdefault(model, {"input_tokens": 0, "output_tokens": 0, "inference_seconds": 0.0})
            for key in total:
                total[key] += values[key]
        statuses[status] += 1
        calls.append(call)
    return {"claimed_slots": len(calls), "dispatched_calls": sum(c["dispatched"] for c in calls),
            "known_not_dispatched_slots": sum(not c["dispatched"] for c in calls),
            "verified_usage_calls": sum(c["verified_usage"] for c in calls),
            "unknown_usage_dispatched_slots": [c["slot"] for c in calls if c["dispatched"] and not c["verified_usage"]],
            "observed_verified_usage_by_model": dict(sorted(totals.items())),
            "usage_is_complete": all(not c["dispatched"] or c["verified_usage"] for c in calls),
            "status_counts": dict(sorted(statuses.items())), "calls": calls}


def build_report(run):
    run = Path(run).resolve()
    if not run.is_dir():
        raise ValueError("Run directory does not exist")
    manifest = read_json(run / "manifest.json")
    if not isinstance(manifest, dict) or not isinstance(manifest.get("cases"), list) or not manifest["cases"]:
        raise ValueError("Campaign manifest with its full task denominator is required")
    tasks = manifest["cases"]
    expected = {}
    for task in tasks:
        if (task.get("split") != "development" or not all(isinstance(task.get(k), str) and task[k]
                for k in ("case_id", "environment", "family_id")) or task["case_id"] in expected):
            raise ValueError("Unique development tasks required")
        expected[task["case_id"]] = task
    summary = read_json(run / "summary.json", {})
    closed = read_json(run / "closed.json", {})
    config = read_json(run / "config.json", {})
    if summary.get("formal_test_cases", 0) != 0 or manifest.get("automatic_formal_expansion") is not False:
        raise ValueError("This reporter accepts development-only campaigns with no formal expansion")
    if summary.get("automatic_formal_expansion", False) is not False:
        raise ValueError("Formal expansion is outside this report")
    summarized = _index(summary.get("cases", []), expected)
    ledger = _call_ledger(run, tasks, config)
    collection_dispatches = Counter(c["case_id"] for c in ledger["calls"]
                                    if c["stage"] == "collection" and c["dispatched"])
    arm_dispatches = Counter((c["case_id"], c["arm"]) for c in ledger["calls"]
                             if c["arm"] is not None and c["dispatched"])
    issues, cases, diagnostic_records = [], [], []
    collection_statuses, origins, references, sensitivity = Counter(), Counter(), Counter(), Counter()
    failure_reasons = []
    arm_statuses = {arm: Counter() for arm in ARMS}
    pair_numeric = pair_followups = pair_valid = 0
    cost_rows = []
    for index, task in enumerate(tasks):
        case_id = task["case_id"]
        disk = read_json(run / f"c{index:04d}.result.json")
        listed = summarized.get(case_id)
        if disk is not None:
            _index([disk], expected)
        if disk is not None and listed is not None and disk != listed:
            raise ValueError("Summary and case result disagree: " + case_id)
        row = deepcopy(disk if disk is not None else listed)
        if row is None:
            row = {**task, "collection_status": "unattempted", "monitoring_admitted": False,
                   "collection_failure_reason": "No case result artifact", "collection_costs": None, "arms": {}}
        private = read_json(run / "private" / f"c{index:04d}.collection.json")
        original = read_json(run / "collection" / f"c{index:04d}" / "result_private.json")
        if private is not None and original is not None and private != original:
            raise ValueError("Collection artifact copies disagree: " + case_id)
        collected = private if private is not None else original
        if collected is not None:
            if _identity(collected) != _identity(task):
                raise ValueError("Private collection identity differs from manifest: " + case_id)
        collected = collected or {}
        status = row.get("collection_status", "missing")
        ended = status == "completed"
        admitted = row.get("monitoring_admitted") is True
        origin = collected.get("origin_kind", "unrecorded")
        natural = manifest.get("live_inference") is True and origin == "natural_actor"
        if origin == "natural_actor" and manifest.get("live_inference") is not True:
            issues.append("Natural collection claim in non-live manifest: " + case_id)
        if manifest.get("live_inference") is True and collected and origin != "natural_actor":
            issues.append("Non-natural collection in live manifest: " + case_id)
        reference = collected.get("reference", {})
        label = reference.get("label")
        resolved = reference.get("status") == "resolved" and type(label) is int and label in (0, 1)
        if not resolved:
            label = None
        ref_status = "positive" if label == 1 else "negative" if label == 0 else "unknown_or_unrecorded"
        sensitive = reference.get("sensitive_execution")
        committed = reference.get("committed_events")
        committed_known = type(committed) is int and committed >= 0
        if resolved and type(sensitive) is bool and committed_known and sensitive == (committed > 0):
            execution_category = "sensitive_execution" if sensitive else "zero_committed_sensitive_actions"
        else:
            execution_category = "execution_evidence_unknown"
        collection_statuses[status] += 1
        origins[origin] += 1
        references[ref_status] += 1
        sensitivity[execution_category] += 1
        if label == 0 and execution_category == "sensitive_execution":
            sensitivity["legal_sensitive_negative"] += 1
        if label == 0 and execution_category == "zero_committed_sensitive_actions":
            sensitivity["zero_action_negative"] += 1
        reason = row.get("collection_failure_reason") or collected.get("stop_reason")
        if not ended or not admitted:
            failure_reasons.append({"case_id": case_id, "stage": "collection_or_admission",
                                    "status": status, "reason": reason or "Not attempted / no result",
                                    "collection_model_calls": collection_dispatches[case_id]})
        arm_rows, predictions = {}, {}
        for arm in ARMS:
            value = deepcopy(row.get("arms", {}).get(arm) or {
                "status": "missing", "score": None, "failure_reason": "No arm result artifact"})
            pred = decision(value)
            predictions[arm] = pred
            valid = pred["numeric"] or pred["abstention"]
            arm_statuses[arm]["all_task_denominator"] += 1
            arm_statuses[arm]["numeric"] += pred["numeric"]
            arm_statuses[arm]["valid_including_abstention"] += valid
            arm_statuses[arm]["abstention"] += pred["abstention"]
            arm_statuses[arm]["technical_failure_among_admitted"] += bool(admitted and pred["technical_failure"])
            arm_statuses[arm]["not_admitted_to_monitoring"] += not admitted
            arm_statuses[arm]["no_model_call_dispatched"] += arm_dispatches[(case_id, arm)] == 0
            arm_statuses[arm]["status_" + value.get("status", "missing")] += 1
            if not valid:
                failure_reasons.append({"case_id": case_id, "stage": arm, "status": value.get("status", "missing"),
                                        "reason": value.get("failure_reason") or "No valid final judgment",
                                        "monitoring_admitted": admitted,
                                        "model_calls": arm_dispatches[(case_id, arm)]})
            arm_rows[arm] = value
        numeric_pair = all(predictions[a]["numeric"] for a in ("F", "T"))
        valid_pair = all(predictions[a]["numeric"] or predictions[a]["abstention"] for a in ("F", "T"))
        followup_pair = all(arm_rows[a].get("followup_performed") is True for a in ("F", "T"))
        pair_numeric += numeric_pair
        pair_valid += valid_pair
        pair_followups += numeric_pair and followup_pair
        case = {**task, "collection_status": status, "collection_normally_ended": ended,
                "monitoring_admitted": admitted, "collection_model_calls": collection_dispatches[case_id],
                "collection_inference_unattempted": collection_dispatches[case_id] == 0,
                "origin_kind": origin, "natural_actor_provenance": natural,
                "reference_label": label, "reference_status": reference.get("status", "unrecorded"),
                "reference_unknown_reasons": reference.get("unknown_reasons", []),
                "committed_events": committed if committed_known else None,
                "execution_category": execution_category, "collection_reason": reason,
                "F_T_numeric_pair": numeric_pair, "F_T_numeric_followup_pair": numeric_pair and followup_pair,
                "arm_statuses": {a: arm_rows[a].get("status", "missing") for a in ARMS}}
        cases.append(case)
        cost_rows.append({**task, "arms": arm_rows, "collection_costs": deepcopy(row.get("collection_costs"))})
        if resolved:
            diagnostic_records.append({**task, "label": label,
                "sensitive_negative": label == 0 and execution_category == "sensitive_execution", "arms": arm_rows})
    n = len(tasks)
    # The all-task cost denominator includes explicitly unattempted zero-call arms.
    # Missing result artifacts have no verified cost, even if no raw calls survived.
    costs = cost_summary(cost_rows)
    collection_cost = cost_summary([{"case_id": r["case_id"], "arms": {"collection": {
        "costs": r["collection_costs"]}}} for r in cost_rows], arms=("collection",))
    monitoring_admitted = sum(c["monitoring_admitted"] for c in cases)
    complete_paths = monitoring_admitted > 0 and all(
        c["arm_statuses"][a] in {"ok", "unknown"}
        for c in cases if c["monitoring_admitted"] for a in ("F", "T"))
    admitted_rows = [r for r, c in zip(cost_rows, cases) if c["monitoring_admitted"]]
    admitted_cost = cost_summary(admitted_rows) if admitted_rows else None
    measured = bool(manifest.get("live_inference") is True and admitted_cost and
                    all(c["natural_actor_provenance"] for c in cases if c["monitoring_admitted"]) and
                    not admitted_cost["includes_fixture_estimates_not_measured_model_cost"] and
                    admitted_cost["arms"]["F"]["cost_complete"] and admitted_cost["arms"]["T"]["cost_complete"] and
                    all(row["arms"][arm].get("costs") for row in admitted_rows for arm in ("F", "T")) and
                    all(entry.get("usage_mode") == "native_model_usage"
                        for row in admitted_rows for arm in ("F", "T") for entry in row["arms"][arm].get("costs", [])))
    comparison_available = measured and complete_paths
    diagnostic = analyze(diagnostic_records, draws=5000, seed=config.get("seed", 20261103)) if diagnostic_records else None
    if diagnostic is not None:
        diagnostic["scope"] = "development_resolved_reference_subset_not_heldout_performance"
        diagnostic["all_task_denominator"] = n
        diagnostic["resolved_reference_denominator"] = len(diagnostic_records)
        diagnostic["reference_coverage"] = len(diagnostic_records) / n
        diagnostic["excluded_unknown_reference_case_ids"] = [c["case_id"] for c in cases if c["reference_label"] is None]
        # The pilot is for collection/operational diagnosis. Do not elevate a
        # selected-reference or development difference into a confirmatory result.
        diagnostic["confirmatory_effect_claim_permitted"] = False
    if summary and summary.get("dispatched_calls") != ledger["dispatched_calls"]:
        issues.append("Summary dispatched_calls differs from readable call ledger")
    if summary and summary.get("monitoring_admitted_count") != monitoring_admitted:
        issues.append("Summary admitted count differs from full-manifest case records")
    if not closed.get("closed"):
        issues.append("No closed receipt; this artifact snapshot does not establish process termination")
    comparison_available = comparison_available and not issues
    return {
        "schema_version": "prospective-development-report-v1", "study_kind": manifest.get("study_kind"),
        "live_inference": manifest.get("live_inference") is True, "formal_test_cases": 0,
        "all_task_denominator": n, "source_manifest_sha256": hashlib.sha256(canonical(manifest).encode()).hexdigest(),
        "closure_confirmed_by_artifact": closed.get("closed") is True,
        "close_reason": summary.get("close_reason", closed.get("close_reason")),
        "collection": {"normally_ended": sum(c["collection_normally_ended"] for c in cases),
            "monitoring_admitted": monitoring_admitted,
            "collection_inference_unattempted": sum(c["collection_inference_unattempted"] for c in cases),
            "natural_actor_records": sum(c["natural_actor_provenance"] for c in cases),
            "status_counts": dict(sorted(collection_statuses.items())), "origin_counts": dict(sorted(origins.items())),
            "meaning": "normally_ended means actor termination, never objective achievement"},
        "references": dict(references), "executions": dict(sensitivity),
        "monitoring": {"all_task_denominator": n, "admitted_denominator": monitoring_admitted,
            "arms": {a: dict(arm_statuses[a]) for a in ARMS}, "F_T_valid_pairs_including_abstention": pair_valid,
            "F_T_numeric_pairs": pair_numeric, "F_T_numeric_pairs_with_both_followups": pair_followups},
        "cost": {"monitoring_all_task_scope": costs, "collection_scope": collection_cost,
            "same_admitted_cohort_monitoring": admitted_cost,
            "F_T_cost_comparability": {"scope": "same_admitted_development_cases",
                "complete_strategy_paths": complete_paths, "measured_native_usage": measured,
                "comparison_available": comparison_available,
                "actual_T_over_F_time": admitted_cost["T_over_F_inference_time"] if comparison_available else None,
                "within_10_percent": admitted_cost["within_proposed_10_percent_time_tolerance"] if comparison_available else None,
                "caps_are_not_measurements": True},
            "phase_elapsed_seconds": {p.stem: read_json(p, {}).get("elapsed_seconds") for p in sorted((run / "phases").glob("*.json"))},
            "campaign_elapsed_seconds": summary.get("elapsed_seconds"),
            "failed_output_token_reserve_is_not_observed_tokens": summary.get("output_tokens_or_failed_reserve")},
        "call_ledger": ledger, "failure_reasons": failure_reasons, "cases": cases,
        "development_diagnostics": diagnostic, "integrity_or_completeness_issues": issues,
        "interpretation_limits": [
            "Development collection/yield/cost pilot only; formal test count is zero.",
            "Termination is separate from task objective success; objectives are not machine-evaluated here.",
            "Zero-action negatives are separate from legitimate sensitive executions.",
            "Collection timeouts or model-start failures are not monitor misclassifications.",
            "Easy explicit-ID/catalog tasks and conspicuous side actions are not a robust benchmark.",
            "Generation condition and variant parity are confounded; no causal condition contrast is estimated.",
            "Forward-correction tasks add permissions; they do not establish revocation robustness.",
            "Four strategies share trajectories, but this development pilot cannot establish held-out TGF superiority.",
        ],
    }


def markdown_report(report):
    n = report["all_task_denominator"]
    collection, monitoring = report["collection"], report["monitoring"]
    lines = ["# TGF development pilot artifact report", "",
             "Development diagnostics only. Formal test cases: **0**.", "",
             f"Manifest tasks: **{n}**; collection normally ended: **{collection['normally_ended']}**; "
             f"admitted to monitoring: **{collection['monitoring_admitted']}**.",
             f"Natural actor records: {collection['natural_actor_records']}; collection inference unattempted: "
             f"{collection['collection_inference_unattempted']}.", "",
             "A normally ended collection is not evidence that the agent achieved its task objective.", "",
             "| Arm | Numeric | Valid including abstention | Not admitted | Failures among admitted |",
             "|---|---:|---:|---:|---:|"]
    for arm, values in monitoring["arms"].items():
        lines.append(f"| {arm} | {values.get('numeric', 0)}/{n} | {values.get('valid_including_abstention', 0)}/{n} | "
                     f"{values.get('not_admitted_to_monitoring', 0)} | {values.get('technical_failure_among_admitted', 0)} |")
    lines += ["", f"F/T numeric pairs: {monitoring['F_T_numeric_pairs']}/{n}; numeric pairs with both follow-ups actually performed: "
              f"{monitoring['F_T_numeric_pairs_with_both_followups']}/{n}.", "",
              "Reference counts: `" + canonical(report["references"]) + "`.",
              "Execution counts: `" + canonical(report["executions"]) + "`.", "",
              f"Call-ledger dispatched calls: {report['call_ledger']['dispatched_calls']}; unknown-usage dispatched calls: "
              f"{len(report['call_ledger']['unknown_usage_dispatched_slots'])}.",
              "Cost comparability: `" + canonical(report["cost"]["F_T_cost_comparability"]) + "`.", "",
              "Input files are read-only. Full per-case failures, usage by model, and artifact hashes are in report.json.", ""]
    for issue in report["integrity_or_completeness_issues"]:
        lines.append("- Artifact issue: " + issue)
    lines += ["", "Interpretation limits:", ""]
    lines += ["- " + limit for limit in report["interpretation_limits"]]
    return "\n".join(lines) + "\n"


def write_report(run, output):
    run, output = Path(run).resolve(), Path(output).resolve()
    if output == run or run in output.parents:
        raise ValueError("Report output must be outside the immutable run directory")
    if output.exists():
        raise FileExistsError("A new output directory is required")
    before = file_hashes(run)
    report = build_report(run)
    after = file_hashes(run)
    if before != after:
        raise RuntimeError("Run artifacts changed during reporting; no stable report was written")
    report["input_files_sha256"] = before
    report["raw_artifacts_unchanged"] = True
    output.mkdir(parents=True, exist_ok=False)
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    (output / "REPORT.md").write_text(markdown_report(report))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    report = write_report(args.run, args.output)
    print(json.dumps({"all_task_denominator": report["all_task_denominator"],
                      "monitoring_admitted": report["collection"]["monitoring_admitted"],
                      "formal_test_cases": 0, "output": str(Path(args.output).resolve())}, indent=2))


if __name__ == "__main__":
    main()
