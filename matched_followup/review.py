"""Keep human gold and explicitly provisional AI development references distinct."""
import json
from .common import digest, load
from .public import POLICY, source_map


def validate_reference(paths, config, cases):
    mode = config.get("reference_mode", "independent_human")
    if mode == "independent_human":
        return dict(validate_reviews(paths, config, cases), reference_mode=mode)
    if mode != "development_ai" or config.get("study_kind") != "development_diagnostic" or len(paths) != 1:
        raise ValueError("AI reference is only admissible for the explicit development diagnostic")
    review = load(paths[0])
    if (review.get("reviewer_type") != "ai" or review.get("human_gold") is not False
            or review.get("independent_review") is not False or not review.get("reviewer")
            or not review.get("authorized_scope") or review.get("endpoint_contract_sha256") != digest(POLICY)):
        raise ValueError("AI reference provenance is missing or misrepresented")
    if review.get("source_sha256") != config["source_sha256"]:
        raise ValueError("AI review uses another frozen source")
    items = review.get("cases", [])
    table = {r["id"]: r for r in items}
    if len(table) != len(items) or set(table) != set(config["cases"]):
        raise ValueError("AI reference must cover exactly the frozen 8 cases")
    for cid, case in cases.items():
        r = table[cid]
        if r.get("public_sha256") != case["public_sha256"] or not r.get("reviewed_at") or not r.get("rationale"):
            raise ValueError("Unbound/incomplete AI reference: " + cid)
        if r.get("reviewed_event_ids") != [e["event_id"] for e in case["ledger"]]:
            raise ValueError("AI review does not cover the complete frozen event list")
        for endpoint in ("authorization_violation", "task_constraint_error"):
            if r.get(endpoint) not in {"P", "N", "unknown"}:
                raise ValueError("Invalid AI endpoint")
        if r.get("task_complete") not in {"complete", "incomplete", "unknown"}:
            raise ValueError("Invalid AI completion label")
        evidence = r.get("evidence", [])
        sources = source_map(case["public"])
        if not evidence:
            raise ValueError("AI reference needs original public evidence")
        for item in evidence:
            if not item.get("claim") or item.get("source_id") not in sources:
                raise ValueError("Unbound AI evidence")
            source = sources[item["source_id"]]
            text = source.get("content") if "content" in source else json.dumps(source.get("args", {}), ensure_ascii=False, sort_keys=True)
            if not item.get("quote") or item["quote"] not in text:
                raise ValueError("AI quote is not verbatim original evidence: " + cid)
        if cid in config["hard_negative_candidates"] and (
                r["authorization_violation"] != "N" or r.get("sensitive_execution") is not True
                or not case["ended"]):
            raise ValueError("Sensitive negative not supported even as an AI development reference")
    return {"reference_mode": mode, "reviewer": review["reviewer"], "cases": table,
            "human_review_complete": False, "independent_review": False,
            "claim_scope": "development diagnostic with provisional non-independent AI reference"}


def validate_reviews(paths, config, cases):
    if len(paths) != 2:
        raise ValueError("Two independent reviewer files required")
    reviewers, resolved = set(), []
    for path in paths:
        review = load(path)
        name = review.get("reviewer", "").strip()
        if not name or name in reviewers or review.get("reviewer_type") != "human":
            raise ValueError("Distinct named human reviewers required")
        reviewers.add(name)
        if review.get("independent_score_blind_review") is not True or review.get("endpoint_scope_accepted") is not True:
            raise ValueError("Uncompleted independent endpoint review")
        if review.get("endpoint_contract_sha256") != digest(POLICY):
            raise ValueError("Reference uses a different endpoint contract")
        items = review.get("cases", [])
        table = {r["id"]: r for r in items}
        if len(table) != len(items):
            raise ValueError("Duplicate reference case")
        validated = {}
        for cid in config["cases"]:
            r = table.get(cid, {})
            if r.get("public_sha256") != cases[cid]["public_sha256"]:
                raise ValueError("Reference/source mismatch: " + cid)
            for endpoint in ("authorization_violation", "task_constraint_error"):
                if r.get(endpoint) not in {"P", "N", "unknown"}:
                    raise ValueError("Unreviewed endpoint: " + cid)
            if r.get("task_complete") not in {"complete", "incomplete", "unknown"}:
                raise ValueError("Unreviewed completion: " + cid)
            for field in ("public_observable", "sensitive_execution"):
                if type(r.get(field)) is not bool:
                    raise ValueError("Unreviewed public evidence: " + cid)
            if r.get("end_state_verified") is not True or not cases[cid]["ended"]:
                raise ValueError("Ending not verified: " + cid)
            if not r.get("reviewed_at") or not r.get("rationale", "").strip():
                raise ValueError("Missing human review explanation/date: " + cid)
            evidence = r.get("evidence_sources")
            if not isinstance(evidence, list) or not evidence or any(s not in source_map(cases[cid]["public"]) for s in evidence):
                raise ValueError("Missing/unbound reference evidence: " + cid)
            if cid in config["hard_negative_candidates"] and (
                    r["authorization_violation"] != "N" or not r["sensitive_execution"] or not r["public_observable"]):
                raise ValueError("Sensitive negative candidate not confirmed: " + cid)
            validated[cid] = r
        resolved.append(validated)
    fields = ("authorization_violation", "task_constraint_error", "task_complete",
              "public_observable", "sensitive_execution")
    for cid in config["cases"]:
        if any(resolved[0][cid][key] != resolved[1][cid][key] for key in fields):
            raise ValueError("Unresolved reviewer disagreement: " + cid)
    return {"reviewers": sorted(reviewers), "cases": resolved[0], "human_review_complete": True}
