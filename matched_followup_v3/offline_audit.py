"""Read-only replay of archived v2 evidence; never relabel or call a model.

These diagnostics are not v3 protocol validation and do not establish entailment.
The report writer refuses to put new files inside the archived run.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

ENDPOINTS = ("authorization_violation", "task_constraint_error")
ARMS = ("P", "L", "F", "T", "L43", "L44")
SENTINELS = {"", "none", "null", "n/a", "na", "unknown", "not applicable"}


def load(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def token_digest(ids):
    text = json.dumps(ids, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(text.encode()).hexdigest()


def inventory(root):
    return {str(p.relative_to(root)): sha(p) for p in sorted(Path(root).rglob("*")) if p.is_file()}


def audit_run(run):
    run = Path(run).resolve()
    before = inventory(run)
    config = load(run / "frozen_config.json")
    manifest = load(run / "call_manifest.json")
    slots = manifest["slots"]
    completed = {k: v for k, v in slots.items() if v["status"] == "completed"}
    rows, defects, bound_inputs, raw_matches = [], [], [], []
    # Only public monitor inputs are examined. Never inspect actor_private or gold.
    for key, slot in completed.items():
        if slot["kind"] == "actor":
            continue
        inp = load(run / "monitor_inputs" / (key + ".json"))
        if token_digest(inp["prompt_token_ids"]) != slot["prompt_sha256"]:
            raise ValueError("Archived prompt-token hash mismatch: " + key)
        bound_inputs.append(key)
    for cid in config["pilot_cases"]:
        prefix = f"c{config['cases'].index(cid):02d}"
        by_arm = {}
        for arm in ARMS:
            key = prefix + "." + arm
            result = load(run / "judgments" / (key + ".json"))
            raw = load(run / "raw_outputs" / (key + ".json"))
            j = result["judgment"]
            # v2's nonthinking grammar emitted plain JSON for this run.
            if json.loads(raw["text"]) != j:
                raise ValueError("Raw and parsed judgment mismatch: " + key)
            raw_matches.append(key)
            nulls = [e for e in ENDPOINTS if j[e]["score"] is None]
            reason = j.get("unknown_reason")
            bad_reason = bool(nulls) and (reason is None or str(reason).strip().casefold() in SENTINELS)
            if bad_reason:
                defects.append({"slot": key, "case_id": cid, "null_endpoints": nulls,
                                "original_unknown_reason": reason})
            by_arm[arm] = {"original_status": result["status"],
                           "scores": {e: j[e]["score"] for e in ENDPOINTS},
                           "missing_specific_null_reason": bad_reason}
        paired = all(by_arm[a]["original_status"] == "valid" and
                     by_arm[a]["scores"]["authorization_violation"] is not None for a in ("F", "T"))
        rows.append({"case_id": cid, "prefix": prefix, "original_resolved_FT_pair": paired, "arms": by_arm})
    after = inventory(run)
    if before != after:
        raise ValueError("Archive changed during read-only audit")
    return {
        "mode": "post_hoc_v2_diagnostic_not_v3_revalidation", "human_gold": False,
        "inference_calls": 0, "archive_unchanged": True, "original_run_sha256": before,
        "slot_counts": dict(Counter(s["status"] for s in slots.values())),
        "completed_by_kind": dict(Counter(s["kind"] for s in completed.values())),
        "finish_reasons": dict(Counter(s["finish_reason"] for s in completed.values())),
        "prompt_tokens": sum(s["prompt_tokens"] for s in completed.values()),
        "completion_tokens": sum(s["completion_tokens"] for s in completed.values()),
        "public_input_hashes_verified": len(bound_inputs), "raw_judgments_match": len(raw_matches),
        "original_valid_main_judgments": sum(r["arms"][a]["original_status"] == "valid" for r in rows for a in ARMS[:4]),
        "original_resolved_FT_pairs": sum(r["original_resolved_FT_pair"] for r in rows),
        "null_reason_defects": defects, "null_reason_defect_count": len(defects),
        "cases": rows,
        "limitations": ["No replacement scores or validity labels", "Source-ID existence does not prove entailment",
                        "Numeric pair coverage is not accuracy", "No remote runtime or GPU readiness claim"],
    }


def write_report(run, output):
    run, output = Path(run).resolve(), Path(output).resolve()
    # Protect the run and its containing retrieval directory, not just one file.
    archive_root = run.parent.parent
    if output == archive_root or archive_root in output.parents:
        raise ValueError("Audit output must be outside the archived retrieval directory")
    result = audit_run(run)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    r = write_report(args.run, args.out)
    print(json.dumps({k: r[k] for k in ("archive_unchanged", "original_valid_main_judgments",
                                      "original_resolved_FT_pairs", "null_reason_defect_count",
                                      "public_input_hashes_verified", "raw_judgments_match")}))
