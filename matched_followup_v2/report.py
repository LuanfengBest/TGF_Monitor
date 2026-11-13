"""Paired evidence table; all 8 cases retained, unknowns never filled with 50."""
import argparse
import csv
from pathlib import Path
from .common import CONFIG, canonical, load, save


def report(directory):
    directory = Path(directory)
    config = load(directory / "frozen_config.json") if (directory / "frozen_config.json").exists() else load(CONFIG)
    manifest = load(directory / "call_manifest.json")
    rows, evidence = [], []
    for i, cid in enumerate(config["cases"]):
        row = {"case_id": cid}
        for arm in ("P", "L", "F", "T", "L43", "L44"):
            slot = f"c{i:02d}.{arm}"
            path = directory / "judgments" / (slot + ".json")
            result = load(path) if path.exists() else {"status": "missing", "judgment": None}
            row[arm + "_status"] = result["status"]
            obj = result["judgment"]
            for endpoint in ("authorization_violation", "task_constraint_error"):
                row[arm + "_" + endpoint] = obj[endpoint]["score"] if obj else None
            if obj:
                evidence.append({"case_id": cid, "arm": arm, **obj,
                                 "citation_semantics_independently_reviewed": False})
        for comparison, left, right in (("T_minus_F", "T", "F"), ("T_minus_L", "T", "L")):
            a, b = row[left + "_authorization_violation"], row[right + "_authorization_violation"]
            row[comparison] = a - b if a is not None and b is not None else None
        rows.append(row)
    with (directory / "paired_evidence_table.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    save(directory / "judgment_evidence.json", evidence)
    stats = {"fixed_case_denominator": len(rows), "inference_claim": "development mechanism diagnostic only",
             "reference_mode": config.get("reference_mode", "independent_human"),
             "human_review_complete": manifest.get("preflight", {}).get("human_review_complete", False),
             "valid_by_arm": {arm: sum(r[arm + "_status"] == "valid" for r in rows) for arm in ("P", "L", "F", "T", "L43", "L44")},
             "resolved_by_arm_and_endpoint": {arm: {
                 endpoint: sum(r[arm + "_" + endpoint] is not None for r in rows)
                 for endpoint in ("authorization_violation", "task_constraint_error")}
                 for arm in ("P", "L", "F", "T", "L43", "L44")},
             "dispatched_calls": sum(s["status"] in {"dispatched", "completed"} for s in manifest["slots"].values()),
             "recorded_completion_tokens": sum(s.get("completion_tokens", 0) for s in manifest["slots"].values()),
             "unobserved_completion_calls": sum(s["status"] == "dispatched" for s in manifest["slots"].values()),
             "reserved_output_tokens": sum(s.get("output_token_reservation", 0) for s in manifest["slots"].values()),
             "actor_answer_failures": sum(s.get("reason") == "invalid_actor_answer" for s in manifest["slots"].values()),
             "human_evidence_support_review_pending": True, "null_scores_imputed": False,
             "close_reason": manifest.get("close_reason")}
    stats["recorded_cost_by_call_kind"] = {kind: {
        "prompt_tokens": sum(s.get("prompt_tokens", 0) for s in manifest["slots"].values() if s["kind"] == kind),
        "completion_tokens": sum(s.get("completion_tokens", 0) for s in manifest["slots"].values() if s["kind"] == kind)}
        for kind in ("planner", "actor", "judge")}
    stats["resolved_FT_pairs"] = sum(r["T_minus_F"] is not None for r in rows)
    stats["pilot_cases"] = config.get("pilot_cases", [])
    stats["accuracy_not_computed"] = True
    gate = directory / "pilot_gate.json"
    stats["pilot_gate"] = load(gate) if gate.exists() else None
    save(directory / "summary.json", stats)
    return stats


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", type=Path, required=True)
    print(canonical(report(p.parse_args().run)))
