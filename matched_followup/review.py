"""Validate actual human reference files separately from all model inputs."""
from .common import digest, load
from .public import POLICY, source_map


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
