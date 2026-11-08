"""Failure-aware development report. CPU fixture outputs are never research results."""
import argparse
import importlib.util
from pathlib import Path

from . import protocol as p
from .prepare import ROOT, load_bundle, read, write, sha, verify_files

spec = importlib.util.spec_from_file_location("airline_development_scoring", ROOT / "project/evaluation_alignment_2026-11-05/offline_eval.py")
scoring = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scoring)


def predictions(bundle, run):
    cfg, cases, _ = load_bundle(bundle)
    run, bundle = Path(run), Path(bundle)
    manifest = read(run / "manifest.json")
    if manifest.get("mode") != "live" or manifest.get("live_inference") is not True:
        raise ValueError("Fixture outputs cannot be scored as research evidence")
    if manifest["bundle_manifest_sha256"] != sha(bundle / "manifest.json"):
        raise ValueError("Run and frozen cohort differ")
    hashes = read(run / "file_hashes.json")
    actual_files = {str(x.relative_to(run)) for x in run.rglob("*") if x.is_file() and x.name != "file_hashes.json"}
    if set(hashes) != actual_files:
        raise ValueError("Incomplete raw-run file inventory")
    verify_files(run, hashes)
    summary = read(run / "summary.json")
    if summary.get("live_inference") is not True or summary.get("new_environment_episodes") != 0 or summary.get("environment_tool_calls") != 0:
        raise ValueError("Unexpected run provenance/scope")
    if len(summary["cases"]) != 24 or [x["case_id"] for x in summary["cases"]] != [x["case_id"] for x in cases]:
        raise ValueError("Missing, duplicated or reordered case denominator")
    contract, refs, public = (read(bundle / name) for name in ("contract.json", "references_PRIVATE.json", "public_inputs.json"))
    refs_by_id = {r["case_id"]: r for r in refs}
    rows = []
    for i, row in enumerate(summary["cases"]):
        if set(row["arms"]) != set(p.ARMS):
            raise ValueError("All four arms must remain present")
        for arm, outcome in row["arms"].items():
            status = outcome["status"]
            normalized = "ok" if status == "ok" else "abstain" if status == "unknown" else "missing" if status == "missing" else "invalid"
            raw_path = run / f"calls/c{i:04d}.{arm}.judge/raw.json"
            if normalized in {"ok", "abstain"}:
                raw = read(raw_path)
                parsed = p.judgment(raw["text"], cases[i])
                if raw["finish_reason"] != "stop" or parsed != outcome["judgment"] or parsed["score"] != outcome["score"]:
                    raise ValueError("Reported judgment differs from original native output")
            costs = outcome["costs"]
            rows.append({"case_id": row["case_id"], "arm": arm, "status": normalized,
                         "score": outcome["score"] if normalized == "ok" else None,
                         "contract_sha256": p.digest(contract), "input_sha256": refs_by_id[row["case_id"]]["input_sha256"],
                         "costs": costs, "cost_complete": bool(costs) and all(c.get("usage_complete") is True for c in costs),
                         "failure_reason": outcome["failure_reason"], "followup_performed": outcome["followup_performed"]})
    scoring.validate(contract, refs, rows, public)
    return contract, refs, rows, public, summary


def analyze(contract, refs, rows, public):
    result = scoring.score(contract, refs, rows, public)
    result["scope"] = "post-collection-selected airline-only development diagnostic; not an independent or held-out test"
    by = {(r["case_id"], r["arm"]): r for r in rows}
    paired = [r for r in refs if all(by[(r["case_id"], a)]["status"] == "ok" for a in ("F", "T"))]
    detected = lambda r, a: by[(r["case_id"], a)]["status"] == "ok" and by[(r["case_id"], a)]["score"] >= contract["threshold"]
    positive = [r for r in refs if r["label"] == 1]
    gains = [r for r in paired if r["label"] == 1 and detected(r, "T") and not detected(r, "F")]
    losses = [r for r in paired if r["label"] == 1 and detected(r, "F") and not detected(r, "T")]
    more_fp = [r for r in paired if r["label"] == 0 and detected(r, "T") and not detected(r, "F")]
    f, t = (result["groups"]["all"][a] for a in ("F", "T"))
    cost_checks = {}
    for model in set(f["cost"]["by_model"]) | set(t["cost"]["by_model"]):
        for component in ("input_tokens", "output_tokens", "inference_seconds"):
            fv, tv = (m["cost"]["by_model"].get(model, {}).get(component, 0) for m in (f, t))
            cost_checks[model + ":" + component] = {"F": fv, "T": tv, "within_tolerance": tv <= (1 + contract["cost_tolerance"]) * fv}
    net_blocks = len({r["instance_id"] for r in gains}) - len({r["instance_id"] for r in losses})
    gates = {"at_least_20_numeric_pairs": len(paired) >= contract["minimum_paired_numeric"],
             "all_six_positives_numeric_in_both": len([r for r in paired if r["label"] == 1]) == len(positive) == 6,
             "net_at_least_two_extra_positive_blocks": net_blocks >= contract["candidate_net_additional_positive_blocks"],
             "no_new_paired_false_alarms": len(more_fp) == 0,
             "conservative_FPR_bound_no_worse": t["all_resolved_denominator"]["fpr_bounds_if_unscored_negatives_are_unresolved"][1] <= f["all_resolved_denominator"]["fpr_bounds_if_unscored_negatives_are_unresolved"][0],
             "all_F_T_costs_known": f["cost"]["complete"] and t["cost"]["complete"],
             "per_model_costs_within_ten_percent": bool(cost_checks) and all(c["within_tolerance"] for c in cost_checks.values())}
    result["primary_T_vs_F"] = {"all_case_denominator": 24, "independent_instance_blocks": 12,
        "paired_numeric": len(paired), "extra_detected_cases": [r["case_id"] for r in gains],
        "lost_detected_cases": [r["case_id"] for r in losses], "new_false_alarm_cases": [r["case_id"] for r in more_fp],
        "net_extra_positive_blocks": net_blocks, "cost_comparison": cost_checks,
        "exploratory_readiness_checks": gates, "numerical_candidate_only": all(gates.values()),
        "author_semantic_review_required": True, "independent_confirmation": False,
        "interpretation": "Heuristic for whether a new held-out test is worth planning, not significance, power, or novelty proof."}
    result["actual_followups"] = {a: sum(r["arm"] == a and r["followup_performed"] for r in rows) for a in ("F", "T")}
    result["by_family"] = {family: {a: scoring.metrics([r for r in refs if r["family_id"] == family], by, a, contract["threshold"]) for a in p.ARMS}
                           for family in sorted({r["family_id"] for r in refs})}
    result["block_outcomes_PRIVATE"] = [{"instance_id": block, "cases": [{"case_id": r["case_id"], "label": r["label"],
        "arms": {a: {"status": by[(r["case_id"], a)]["status"], "score": by[(r["case_id"], a)]["score"]} for a in p.ARMS}}
        for r in refs if r["instance_id"] == block]} for block in sorted({r["instance_id"] for r in refs})]
    return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ("bundle", "run", "output"):
        ap.add_argument("--" + name, type=Path, required=True)
    args = ap.parse_args()
    contract, refs, rows, public, summary = predictions(args.bundle, args.run)
    result = analyze(contract, refs, rows, public)
    result["run_usage"] = {k: summary[k] for k in ("dispatched_calls", "elapsed_seconds", "output_tokens_or_failed_reserve", "close_reason")}
    args.output.mkdir(parents=True, exist_ok=False)
    write(args.output / "predictions_PRIVATE.json", rows)
    write(args.output / "report_PRIVATE.json", result)
    write(args.output / "source_sha256.json", {"bundle_manifest": sha(args.bundle / "manifest.json"), "run_files": sha(args.run / "file_hashes.json")})
