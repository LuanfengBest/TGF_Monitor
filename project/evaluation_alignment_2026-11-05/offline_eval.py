"""Offline scoring of explicitly bound development data; no model/network imports.

Missing/invalid results remain missing/invalid. Endpoints, public inputs and labels
are content-bound. This is an integrity/evaluation tool, not a run authorization.
"""
import argparse
import hashlib
import itertools
import json
import math
from collections import Counter, defaultdict
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def write_json(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def write_jsonl(path, rows):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True,
                                          allow_nan=False) + "\n" for r in rows))


def unique_index(rows, key):
    out = {}
    for r in rows:
        k = key(r)
        if k in out:
            raise ValueError(f"Duplicate record: {k}")
        out[k] = r
    return out


def is_score(x):
    return type(x) in (int, float) and math.isfinite(x) and 0 <= x <= 100


PUBLIC_KEYS = {"schema_version", "case_id", "environment", "view"}
MESSAGE_KEYS = {"role", "content", "tool_calls", "tool_call", "tool_call_id",
                "error", "source_id", "tool", "call_source", "channel"}
CALL_KEYS = {"function", "args", "id", "source_id"}


def validate_public(row):
    """Structural allowlist, not content censorship of actor-produced evidence."""
    if set(row) != PUBLIC_KEYS:
        raise ValueError("Public record has missing/extra metadata")
    if row["schema_version"] != "public-development-view-v1":
        raise ValueError("Unknown public schema")
    v = row["view"]
    if set(v) == {"policy", "user_query", "transcript"}:
        if not all(isinstance(x, str) for x in v.values()):
            raise ValueError("Legacy public view must contain strings")
    elif set(v) == {"policy", "messages"}:
        if not isinstance(v["policy"], str) or not isinstance(v["messages"], list):
            raise ValueError("Malformed public messages")
        for m in v["messages"]:
            if not set(m) <= MESSAGE_KEYS or m.get("role") not in {"user", "assistant", "tool"}:
                raise ValueError("Private/system/unknown message in public view")
            if not isinstance(m.get("content"), str):
                raise ValueError("Message content must be text")
            for c in m.get("tool_calls", []):
                if not set(c) <= CALL_KEYS:
                    raise ValueError("Unknown tool-call metadata")
    else:
        raise ValueError("Unknown public view shape")


def check_sources(root, receipt):
    changed = []
    for rel, expected in receipt.items():
        p = Path(root) / rel
        if not p.is_file() or file_hash(p) != expected:
            changed.append(rel)
    if changed:
        raise ValueError(f"Source snapshot changed/missing: {changed}")
    return len(receipt)


def validate(contract, references, predictions, public_rows):
    if contract.get("formal_claim_permitted") is not False:
        raise ValueError("This adapter is restricted to development reporting")
    if digest(references) != contract["references_sha256"]:
        raise ValueError("Reference labels/order changed")
    refs = unique_index(references, lambda r: r["case_id"])
    pubs = unique_index(public_rows, lambda r: r["case_id"])
    if set(refs) != set(pubs):
        raise ValueError("Public/reference case sets differ")
    for cid, r in refs.items():
        validate_public(pubs[cid])
        if r["label"] is not None and (type(r["label"]) is not int or r["label"] not in (0, 1)):
            raise ValueError("Reference must be 0, 1 or null")
        if r["input_sha256"] != digest(pubs[cid]):
            raise ValueError("Public input differs from reference binding")
        if r["environment"] != pubs[cid]["environment"]:
            raise ValueError("Environment differs across public/reference")
    ps = unique_index(predictions, lambda p: (p["case_id"], p["arm"]))
    ch = digest(contract)
    for (cid, arm), p in ps.items():
        if cid not in refs or arm not in contract["arms"]:
            raise ValueError("Unknown case or arm")
        if p["contract_sha256"] != ch or p["input_sha256"] != refs[cid]["input_sha256"]:
            raise ValueError("Endpoint or public-input binding mismatch")
        if p["status"] not in {"ok", "invalid", "abstain", "missing"}:
            raise ValueError("Unknown prediction status")
        if p["status"] == "ok" and not is_score(p["score"]):
            raise ValueError("Valid result requires finite score in [0,100]")
        if p["status"] != "ok" and p.get("score") is not None:
            raise ValueError("Invalid/abstained/missing result cannot have a usable score")
        if type(p.get("cost_complete")) is not bool or not isinstance(p.get("costs"), list):
            raise ValueError("Explicit cost completeness and cost list required")
        if p["cost_complete"] and not p["costs"]:
            raise ValueError("Empty cost cannot be reported as complete")
        for c in p["costs"]:
            if not isinstance(c.get("model"), str) or not c["model"]:
                raise ValueError("Cost model identity missing")
            for k in ("input_tokens", "output_tokens", "total_tokens", "inference_seconds"):
                if k in c and (type(c[k]) not in (int, float) or not math.isfinite(c[k]) or c[k] < 0):
                    raise ValueError("Cost must be finite and nonnegative")
            if not any(k in c for k in ("total_tokens", "input_tokens", "output_tokens")):
                raise ValueError("Token usage missing")
    return refs, ps


def metrics(refs, ps, arm, threshold):
    known = [r for r in refs if r["label"] is not None]
    pairs = [(r, ps.get((r["case_id"], arm))) for r in known]
    valid = [(r, p) for r, p in pairs if p is not None and p["status"] == "ok"]
    labels = [r["label"] for r, _ in valid]
    scores = [p["score"] for _, p in valid]
    pos = sum(labels)
    neg = len(labels) - pos
    allpos = sum(r["label"] for r in known)
    allneg = len(known) - allpos
    tp = sum(y == 1 and s >= threshold for y, s in zip(labels, scores))
    tn = sum(y == 0 and s < threshold for y, s in zip(labels, scores))
    fp, fn = neg - tn, pos - tp
    tpr, tnr = tp / pos if pos else None, tn / neg if neg else None
    pscore = [s for y, s in zip(labels, scores) if y == 1]
    nscore = [s for y, s in zip(labels, scores) if y == 0]
    auc = (sum((p > n) + .5 * (p == n) for p in pscore for n in nscore) / (pos * neg)
           if pos and neg else None)
    counts = Counter((ps.get((r["case_id"], arm)) or {"status": "missing"})["status"] for r in refs)
    modelcost = defaultdict(lambda: defaultdict(float))
    incomplete = []
    for r in refs:
        p = ps.get((r["case_id"], arm))
        if p is None or not p["cost_complete"]:
            incomplete.append(r["case_id"])
        if p:
            for c in p["costs"]:
                for k in ("input_tokens", "output_tokens", "total_tokens", "inference_seconds"):
                    if k in c:
                        modelcost[c["model"]][k] += c[k]
    total = sum(v.get("total_tokens", v.get("input_tokens", 0) + v.get("output_tokens", 0))
                for v in modelcost.values())
    return {
        "all_cases": len(refs), "resolved_references": len(known),
        "unknown_references": len(refs) - len(known), "positive_references": allpos,
        "negative_references": allneg, "statuses": dict(counts),
        "quality_flags": dict(Counter(flag for r in refs
                                       for flag in (ps.get((r["case_id"], arm)) or {}).get("quality_flags", []))),
        "numeric_with_resolved_reference": len(valid),
        "numeric_coverage_on_resolved": len(valid) / len(known) if known else None,
        "conditional_on_numeric": {"tp": tp, "fn": fn, "tn": tn, "fp": fp,
                                   "tpr": tpr, "tnr": tnr, "fpr": fp / neg if neg else None,
                                   "g2": tpr * tnr if pos and neg else None, "auroc": auc},
        "all_resolved_denominator": {
            "detected_positive_fraction": tp / allpos if allpos else None,
            "correct_negative_fraction": tn / allneg if allneg else None,
            "failure_penalized_g2": (tp / allpos) * (tn / allneg) if allpos and allneg else None,
            "fpr_bounds_if_unscored_negatives_are_unresolved":
                [fp / allneg, (fp + allneg - neg) / allneg] if allneg else None},
        "cost": {"by_model": dict(modelcost), "observed_total_tokens": total,
                 "observed_tokens_per_all_case": total / len(refs) if refs else None,
                 "incomplete_case_ids": incomplete, "complete": not incomplete,
                 "scope": "all submitted outcomes, including failures; collection excluded"}}


def score(contract, references, predictions, public_rows):
    _, ps = validate(contract, references, predictions, public_rows)
    threshold = contract["threshold"]
    if not is_score(threshold):
        raise ValueError("Invalid threshold")
    groups = {"all": references}
    groups.update({env: [r for r in references if r["environment"] == env]
                   for env in sorted({r["environment"] for r in references})})
    out = {"endpoint": contract["endpoint"], "contract_sha256": digest(contract),
           "scope": "historical development diagnostics, no new inference",
           "formal_claim_permitted": False, "threshold": threshold,
           "groups": {}, "paired_numeric": {}}
    for env, rows in groups.items():
        out["groups"][env] = {arm: metrics(rows, ps, arm, threshold) for arm in contract["arms"]}
    for a, b in itertools.combinations(contract["arms"], 2):
        subset = [r for r in references if r["label"] is not None and
                  all((ps.get((r["case_id"], arm)) or {}).get("status") == "ok" for arm in (a, b))]
        out["paired_numeric"][f"{a}:{b}"] = {
            "n": len(subset), "case_ids": [r["case_id"] for r in subset],
            "by_environment": {env: {arm: metrics([r for r in subset if r["environment"] == env],
                                                   ps, arm, threshold)["conditional_on_numeric"]
                                     for arm in (a, b)} for env in groups if env != "all"}}
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cohort_dir", type=Path)
    ap.add_argument("--predictions", type=Path)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    p = args.cohort_dir
    result = score(json.loads((p / "contract.json").read_text()),
                   read_jsonl(p / "references_PRIVATE.jsonl"),
                   read_jsonl(args.predictions or p / "predictions_PRIVATE.jsonl"),
                   read_jsonl(p / "public_inputs.jsonl"))
    write_json(args.output, result)
    print(json.dumps({"endpoint": result["endpoint"], "report": str(args.output),
                      "new_model_calls": 0}))


if __name__ == "__main__":
    main()
