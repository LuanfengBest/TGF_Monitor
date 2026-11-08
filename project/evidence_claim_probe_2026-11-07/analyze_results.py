"""Verify returned artifacts and analyze frozen paired contrasts, without inference."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

PHASE = Path(__file__).resolve().parent
REPO = PHASE.parents[1]
sys.path.insert(0, str(REPO))
from evidence_use_v2.run import validate_output
from evidence_use_v1.protocol import check_record, canonical


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metrics(rows):
    positive = [r for r in rows if r["reference_violation"]]
    negative = [r for r in rows if not r["reference_violation"]]
    return {"planned": len(rows), "valid_decisions": sum(r["prediction"] is not None for r in rows),
            "correct": sum(r["correct"] for r in rows),
            "positive_planned": len(positive), "negative_planned": len(negative),
            "true_positive": sum(r["prediction"] is True for r in positive),
            "false_negative": sum(r["prediction"] is False for r in positive),
            "true_negative": sum(r["prediction"] is False for r in negative),
            "false_positive": sum(r["prediction"] is True for r in negative),
            "failure_on_positive": sum(r["prediction"] is None for r in positive),
            "failure_on_negative": sum(r["prediction"] is None for r in negative),
            "statuses": dict(Counter(r["status"] for r in rows))}


def paired(left, right, contrast):
    comparable = left["prediction"] is not None and right["prediction"] is not None
    return {"contrast": contrast, "model_slot": left["model_slot"], "index": left["index"],
            "variant": left["variant"], "seed": left["seed"],
            "reference_violation": left["reference_violation"],
            "from_request": left["request_id"], "to_request": right["request_id"],
            "from_status": left["status"], "to_status": right["status"],
            "from_score": left["score"], "to_score": right["score"], "comparable": comparable,
            "score_delta": right["score"] - left["score"] if comparable else None,
            "verdict_changed": left["prediction"] != right["prediction"] if comparable else None,
            "recovered": comparable and not left["correct"] and right["correct"],
            "harmed": comparable and left["correct"] and not right["correct"],
            "from_correct": left["correct"], "to_correct": right["correct"]}


def analyze(root):
    import jsonschema
    manifest = read(PHASE / "manifest.json")
    for name, expected in manifest["files"].items():
        assert digest(REPO / name) == expected, name
    for name, expected in manifest["local_reference_files"].items():
        assert digest(PHASE / name) == expected, name
    for name in ("manifest.json", "config.json", "contract.json"):
        assert digest(root / "project" / PHASE.name / name) == digest(PHASE / name), name
    hashes = read(root / "results/hashes.json")
    for name, expected in hashes.items():
        assert name.startswith("results/") and ".." not in Path(name).parts
        assert digest(root / name) == expected, name
    reqs = {r["request_id"]: r for r in read(PHASE / "requests.json")}
    targets = read(PHASE / "targets_LOCAL_ONLY.json")
    assert len(targets) == len(reqs) == 60 and set(reqs) == {t["request_id"] for t in targets}
    summary = read(root / "results/summary.json")
    preflight = read(root / "admission/preflight.json")
    assert preflight["ready"] and preflight["job_id"] == summary["job_id"]
    assert preflight["manifest_sha256"] == digest(PHASE / "manifest.json")
    assert summary["planned"] == 60
    done = {r["request_id"]: r for r in summary["positions"]}
    assert len(done) == len(summary["positions"]) == summary["returned"]
    assert set(done) <= set(reqs)
    assert set(summary["unreturned_or_undispatched"]) == set(reqs) - set(done)
    capacities = {r["request_id"]: r for r in preflight["capacity"]}
    assert set(capacities) == set(reqs)
    rows = []
    for target in targets:
        rid = target["request_id"]; req = reqs[rid]; slot = root / "results" / rid
        data = json.loads(req["prompt"].split("PUBLIC INPUT:\n", 1)[1])
        assert check_record(data["record"])["violation"] == target["reference_violation"]
        item = done.get(rid, {})
        validation_errors, invalid_text = [], None
        if item:
            assert read(slot / "parsed.json") == item
            raw = read(slot / "raw.json")
            status, output = validate_output(raw, req)
            assert (status, output) == (item["status"], item["output"])
            assert raw["prompt_sha256"] == capacities[rid]["prompt_token_sha256"]
            assert raw["completion_tokens"] <= req["max_output_tokens"]
            if status not in ("valid", "unknown"):
                invalid_text = raw.get("text")
                try:
                    untrusted = json.loads(raw["text"])
                    validator = jsonschema.Draft202012Validator(req["schema"])
                    for error in validator.iter_errors(untrusted):
                        leaves = error.context or [error]
                        validation_errors.extend({"path": list(e.absolute_path), "validator": e.validator,
                                                  "message": e.message} for e in leaves)
                except Exception as exc:
                    validation_errors.append({"exception": str(exc)})
        if (slot / "dispatch.json").exists():
            dispatch = read(slot / "dispatch.json")
            assert dispatch["request_sha256"] == hashlib.sha256(canonical(req).encode()).hexdigest()
        status = item.get("status", "unreturned" if (slot / "dispatch.json").exists() else "undispatched")
        output = item.get("output") or {}; score = output.get("score")
        prediction = score >= 50 if status == "valid" and type(score) is int else None
        rows.append({**target, "status": status, "score": score, "prediction": prediction,
                     "correct": prediction is not None and prediction == target["reference_violation"],
                     "output": output, "prompt_tokens": item.get("prompt_tokens"),
                     "completion_tokens": item.get("completion_tokens"), "validation_errors": validation_errors,
                     "invalid_final_text": invalid_text})
    dispatches = [r for r in reqs if (root / "results" / r / "dispatch.json").exists()]
    assert len(dispatches) == summary["dispatched"]
    assert sum(reqs[r]["max_output_tokens"] for r in dispatches) == summary["reserved_output_tokens"]
    assert sum(r["completion_tokens"] for r in rows if r["completion_tokens"] is not None) == summary["actual_returned_output_tokens"]
    groups = defaultdict(list)
    lookup = {}
    for row in rows:
        groups[row["model_slot"], row["condition"]].append(row)
        lookup[row["model_slot"], row["index"], row["variant"], row["seed"], row["condition"]] = row
    pairs = []
    contrasts = (("atoms_only", "running_total"), ("running_total", "comparison_only"),
                 ("correct_assertion", "incorrect_assertion"), ("atoms_only", "correct_assertion"),
                 ("atoms_only", "incorrect_assertion"))
    for row in rows:
        if row["condition"] != "atoms_only":
            continue
        key = (row["model_slot"], row["index"], row["variant"], row["seed"])
        for left, right in contrasts:
            pairs.append(paired(lookup[key + (left,)], lookup[key + (right,)], left + " -> " + right))
    pair_groups = defaultdict(list)
    for pair in pairs:
        pair_groups[pair["model_slot"], pair["contrast"]].append(pair)
    aggregates = [{"model_slot": key[0], "contrast": key[1], "planned_pairs": len(group),
                   "comparable": sum(p["comparable"] for p in group),
                   "changed": sum(p["verdict_changed"] is True for p in group),
                   "recovered": sum(p["recovered"] for p in group), "harmed": sum(p["harmed"] for p in group)}
                  for key, group in sorted(pair_groups.items())]
    old = read(REPO / "project/evidence_use_diagnostic_2026-11-07/analysis_32425664.json")
    old_rows = {r["request_id"]: r for r in old["rows"]}
    replays = []
    for row in rows:
        if row["model_slot"] == "monitor" and row["variant"] == "original" and row["condition"] == "atoms_only":
            prev = old_rows[f'monitor.{row["index"]:02d}.original.fact_repair_B.s{row["seed"]}']
            replays.append({"request_id": row["request_id"], "old_score": prev["score"], "new_score": row["score"],
                            "old_status": prev["status"], "new_status": row["status"],
                            "same_score": row["score"] == prev["score"],
                            "same_output": row["output"] == prev["output"]})
    review_ids = {r["request_id"] for r in rows if not r["correct"]}
    for pair in pairs:
        if pair["verdict_changed"]:
            review_ids.update((pair["from_request"], pair["to_request"]))
    return {"created_at_utc": datetime.now(timezone.utc).isoformat(), "job_id": summary["job_id"],
            "campaign_status": summary["status"], "campaign_error": summary["error"],
            "planned": 60, "dispatched": summary["dispatched"], "returned": summary["returned"],
            "verified_output_files": len(hashes), "task_blocks": 1, "original_actor_records": 2,
            "synthetic_budget_variants": 2, "formal_claim_permitted": False,
            "actual_output_tokens": summary["actual_returned_output_tokens"],
            "reserved_output_tokens": summary["reserved_output_tokens"],
            "allocation_elapsed_seconds": summary["allocation_elapsed_seconds"],
            "groups": [{"model_slot": k[0], "condition": k[1], **metrics(v)} for k, v in sorted(groups.items())],
            "contrast_summary": aggregates, "pairs": pairs, "baseline_replays": replays,
            "manual_review_required_request_ids": sorted(review_ids), "rows": rows}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("results_root", type=Path); args = ap.parse_args()
    analysis = analyze(args.results_root.resolve())
    dest = PHASE / ("analysis_" + analysis["job_id"] + ".json")
    with dest.open("x") as output:
        json.dump(analysis, output, indent=2, ensure_ascii=False, allow_nan=False); output.write("\n")
    print(json.dumps({k: v for k, v in analysis.items() if k not in ("pairs", "rows", "manual_review_required_request_ids")}, indent=2))
