"""Frozen all-slot scoring and resource gate; no research claim from fixtures."""
import argparse
from collections import Counter
from pathlib import Path
from . import protocol as p
from .prepare import load_bundle, read, write, sha, verify_files


def analyze(rows, refs, cfg):
    expected = {(r["case_id"], seed, arm) for r in refs for seed in p.SEEDS for arm in p.ARMS}
    by = {(r["case_id"], r["seed"], r["arm"]): r for r in rows}
    if len(rows) != 144 or set(by) != expected or len(refs) != 24:
        raise ValueError("Exactly all 144 unique positions required")
    ref_by = {r["case_id"]: r for r in refs}
    detected = lambda cid, seed, arm: by[cid, seed, arm]["status"] == "ok" and by[cid, seed, arm]["score"] >= cfg["threshold"]
    groups, per_seed, contrasts = {}, {}, {}
    for arm in p.ARMS:
        entries = [r for r in rows if r["arm"] == arm]
        by_model = {}
        for row in entries:
            for cost in row["costs"]:
                dest = by_model.setdefault(cost["model"], {"input_tokens": 0, "output_tokens": 0, "inference_seconds": 0.0,
                    "recorded_calls": 0, "model_inference_calls": 0, "pre_inference_rejections": 0, "unknown_usage_calls": 0})
                dest["recorded_calls"] += 1
                rejected = cost.get("usage_mode") == "known_rejection_before_model_inference"
                dest["pre_inference_rejections"] += rejected
                dest["model_inference_calls"] += not rejected
                dest["unknown_usage_calls"] += cost.get("usage_complete") is not True
                for key in ("input_tokens", "output_tokens", "inference_seconds"):
                    dest[key] += cost[key]
        groups[arm] = {"cost_by_model": by_model,
            "cost_complete": all(len(r["costs"]) == 2 and all(c.get("usage_complete") is True for c in r["costs"]) for r in entries)}
    for seed in p.SEEDS:
        per_seed[str(seed)] = {}
        for arm in p.ARMS:
            entries = [by[r["case_id"], seed, arm] for r in refs]
            counts = Counter(r["status"] for r in entries)
            positives = [r for r in refs if r["label"] == 1]
            negatives = [r for r in refs if r["label"] == 0]
            unknown_pos = sum(by[r["case_id"], seed, arm]["status"] != "ok" for r in positives)
            unknown_neg = sum(by[r["case_id"], seed, arm]["status"] != "ok" for r in negatives)
            tp = sum(detected(r["case_id"], seed, arm) for r in positives)
            fp = sum(detected(r["case_id"], seed, arm) for r in negatives)
            per_seed[str(seed)][arm] = {"tp": tp, "positive_denominator": 6, "fp": fp, "negative_denominator": 18,
                "status_counts": dict(counts), "unscored_positive": unknown_pos, "unscored_negative": unknown_neg,
                "detection_count_bounds": [tp, tp + unknown_pos], "false_alarm_count_bounds": [fp, fp + unknown_neg]}
    for other in ("B", "A"):
        paired = {}
        stable = None
        for seed in p.SEEDS:
            eligible = [r for r in refs if all(by[r["case_id"], seed, a]["status"] == "ok" for a in ("C", other))]
            gains = [r for r in eligible if r["label"] == 1 and detected(r["case_id"], seed, "C") and not detected(r["case_id"], seed, other)]
            losses = [r for r in eligible if r["label"] == 1 and detected(r["case_id"], seed, other) and not detected(r["case_id"], seed, "C")]
            new_fp = [r for r in eligible if r["label"] == 0 and detected(r["case_id"], seed, "C") and not detected(r["case_id"], seed, other)]
            gained_blocks, lost_blocks = ({r["instance_id"] for r in rs} for rs in (gains, losses))
            stable = gained_blocks if stable is None else stable & gained_blocks
            paired[str(seed)] = {"paired_numeric": len(eligible), "gain_cases": [r["case_id"] for r in gains],
                "loss_cases": [r["case_id"] for r in losses], "new_false_alarm_cases": [r["case_id"] for r in new_fp],
                "gain_blocks": sorted(gained_blocks), "loss_blocks": sorted(lost_blocks),
                "net_extra_positive_blocks": len(gained_blocks) - len(lost_blocks)}
        families = {r["family_id"] for r in refs if r["instance_id"] in stable and r["label"] == 1}
        contrasts["C_vs_" + other] = {"by_seed": paired, "stable_gain_blocks": sorted(stable),
            "stable_gain_families": sorted(families), "gain_gate": all(x["net_extra_positive_blocks"] >= 2 for x in paired.values())
            and len(stable) >= 2 and len(families) >= 2,
            "no_new_false_alarm_gate": all(not x["new_false_alarm_cases"] for x in paired.values())}
    cost_checks = {}
    for model in cfg["models"].values():
        for component in ("input_tokens", "output_tokens", "inference_seconds"):
            b, c = (groups[a]["cost_by_model"].get(model, {}).get(component, 0) for a in ("B", "C"))
            cost_checks[model + ":" + component] = {"B": b, "C": c, "ratio": c / b if b else None,
                "within_110_percent": b > 0 and c <= 1.1 * b}
    gates = {"all_144_numeric": all(r["status"] == "ok" for r in rows),
        "stable_gains_vs_both_controls": all(v["gain_gate"] for v in contrasts.values()),
        "no_new_false_alarms": all(v["no_new_false_alarm_gate"] for v in contrasts.values()),
        "all_costs_known_B_C": groups["B"]["cost_complete"] and groups["C"]["cost_complete"],
        "per_model_costs_within_110_percent": all(v["within_110_percent"] for v in cost_checks.values())}
    ceiling = any(all(per_seed[str(s)][a]["tp"] == 6 and per_seed[str(s)][a]["fp"] == 0
        and per_seed[str(s)][a]["status_counts"].get("ok") == 24 for s in p.SEEDS) for a in ("A", "B"))
    decision = ("inconclusive_stop_no_rerun" if not gates["all_144_numeric"] else
                "numerical_candidate_requires_author_semantic_review" if all(gates.values()) else
                "controls_at_ceiling_dataset_nondiscriminating_stop" if ceiling else "stop_improvement_line")
    return {"per_seed": per_seed, "costs": groups, "paired_contrasts": contrasts, "cost_comparison_C_B": cost_checks,
        "resource_gates": gates, "numerical_candidate": all(gates.values()), "decision": decision,
        "author_semantic_review": "pending_not_an_independent_review", "formal_claim_permitted": False,
        "unique_original_cases": 24, "unique_public_records": 22, "original_instance_blocks": 12,
        "replicates_are_not_independent_cases": True,
        "scope": "Post-hoc airline-only fixed-anchor diagnostic; original collection coverage failed; not automatic TGF or held-out efficacy.",
        "blocks": [{"instance_id": b, "cases": [{"case_id": r["case_id"], "label": r["label"], "family_id": r["family_id"],
            "replicas": {str(s): {a: {k: by[r["case_id"], s, a][k] for k in ("status", "score")} for a in p.ARMS} for s in p.SEEDS}}
            for r in refs if r["instance_id"] == b]} for b in sorted({r["instance_id"] for r in refs})]}


def report(bundle, run):
    cfg, cases, _ = load_bundle(bundle)
    bundle, run = Path(bundle), Path(run)
    manifest = read(run / "manifest.json")
    if manifest.get("mode") != "live" or manifest.get("live_inference") is not True or manifest["bundle_manifest_sha256"] != sha(bundle / "manifest.json"):
        raise ValueError("Bound live results required; CPU fixtures never score as research")
    hashes = read(run / "file_hashes.json")
    actual = {str(f.relative_to(run)) for f in run.rglob("*") if f.is_file() and str(f.relative_to(run)) != "file_hashes.json"}
    if set(hashes) != actual:
        raise ValueError("Incomplete raw file inventory")
    verify_files(run, hashes)
    summary = read(run / "summary.json")
    expected = [(c["case_id"], s) for s in p.SEEDS for c in cases]
    if [(r["case_id"], r["seed"]) for r in summary["cases"]] != expected or summary.get("live_inference") is not True:
        raise ValueError("Replica denominator/provenance changed")
    rows = []
    for i, replica in enumerate(summary["cases"]):
        if set(replica["arms"]) != set(p.ARMS):
            raise ValueError("Missing group")
        for arm, value in replica["arms"].items():
            if value["status"] in {"ok", "unknown"}:
                raw = read(run / f"calls/c{i:04d}.{arm}.judge/raw.json")
                decoded = p.judgment(raw["text"], cases[i % 24])
                if raw["finish_reason"] != "stop" or decoded != value["judgment"] or decoded["score"] != value["score"]:
                    raise ValueError("Original model score changed")
                if (value["status"] == "ok") != (decoded["score"] is not None):
                    raise ValueError("Unknown status mismatch")
            rows.append({"case_id": replica["case_id"], "seed": replica["seed"], "arm": arm, **value})
    result = analyze(rows, read(bundle / "references_PRIVATE.json"), cfg)
    result["run_usage"] = {k: summary[k] for k in ("dispatched_calls", "known_pre_inference_rejections",
        "output_tokens_or_failed_reserve", "elapsed_seconds", "pre_campaign_allocation_seconds", "allocation_elapsed_seconds", "close_reason")}
    result["shared_phases"] = [read(f) for f in sorted((run / "phases").glob("*.json"))]
    # All inference charges (including failed unknown calls) are preserved per
    # model. Shared startup/cleanup and admission are separate allocation costs.
    if sum(c["model_inference_calls"] for g in result["costs"].values() for c in g["cost_by_model"].values()) != summary["dispatched_calls"]:
        raise ValueError("Per-model call counts do not reconcile with dispatch total")
    return rows, result


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ("bundle", "run", "output"):
        ap.add_argument("--" + name, type=Path, required=True)
    args = ap.parse_args()
    rows, result = report(args.bundle, args.run)
    args.output.mkdir(parents=True, exist_ok=False)
    write(args.output / "predictions_PRIVATE.json", rows)
    write(args.output / "report_PRIVATE.json", result)
    write(args.output / "source_sha256.json", {"bundle_manifest": sha(args.bundle / "manifest.json"), "raw_inventory": sha(args.run / "file_hashes.json")})
    print(p.canonical({"decision": result["decision"], "per_seed": result["per_seed"]}))
