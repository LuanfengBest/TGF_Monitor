"""Freeze a reference-based test selection BEFORE any monitor output exists.

Only metadata are accepted. Fixtures are not eligible natural actor test cases.
The result is a selection receipt, not a claim that monitoring has been run.
"""
from collections import Counter, defaultdict, deque
import hashlib
import json
import math
import random
import re

REQUIRED = {"case_id", "environment", "family_id", "split", "label", "reference_complete",
            "capacity_ok", "normalized_hash", "sensitive_negative", "origin_kind"}
OPTIONAL = {"scenario_id", "source_id", "seed"}
SPLITS = {"dev": "development", "development": "development", "validation": "validation", "test": "test"}


def _canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def validate_candidates(candidates, registry=None):
    if not isinstance(candidates, list):
        raise ValueError("candidates must be a list")
    ids, family_splits, family_envs = set(), {}, {}
    clean = []
    for candidate in candidates:
        if not isinstance(candidate, dict) or not REQUIRED <= set(candidate) or set(candidate) - REQUIRED - OPTIONAL:
            raise ValueError("candidate metadata allowlist violated; monitor outputs are forbidden")
        row = dict(candidate)
        for field in ("case_id", "environment", "family_id", "origin_kind"):
            if not isinstance(row[field], str) or not row[field].strip():
                raise ValueError("invalid " + field)
        if row["case_id"] in ids:
            raise ValueError("duplicate case_id")
        ids.add(row["case_id"])
        if row["split"] not in SPLITS:
            raise ValueError("unknown split")
        row["split"] = SPLITS[row["split"]]
        if row["label"] is not None and (type(row["label"]) is not int or row["label"] not in (0, 1)):
            raise ValueError("label must be resolved 0/1 or null")
        for flag in ("reference_complete", "capacity_ok", "sensitive_negative"):
            if type(row[flag]) is not bool:
                raise ValueError(flag + " must be boolean")
        if row["sensitive_negative"] and row["label"] != 0:
            raise ValueError("sensitive_negative requires label 0")
        for field in ("source_id", "scenario_id"):
            if field in row and (not isinstance(row[field], str) or not row[field].strip()):
                raise ValueError("optional metadata must be plain text: " + field)
        if "seed" in row and type(row["seed"]) is not int:
            raise ValueError("seed metadata must be an integer")
        if not isinstance(row["normalized_hash"], str) or not re.fullmatch("[0-9a-f]{64}", row["normalized_hash"]):
            raise ValueError("normalized_hash must be SHA-256 hexadecimal")
        family = row["family_id"]
        if family in family_splits and family_splits[family] != row["split"]:
            raise ValueError("family crosses splits: " + family)
        if family in family_envs and family_envs[family] != row["environment"]:
            raise ValueError("family crosses environments: " + family)
        family_splits[family], family_envs[family] = row["split"], row["environment"]
        clean.append(row)
    if registry is not None:
        families = registry.get("families") if isinstance(registry, dict) else registry
        if not isinstance(families, list):
            raise ValueError("registry needs a families list")
        registered = {}
        for family in families:
            if not isinstance(family, dict) or not {"family_id", "environment", "split"} <= set(family):
                raise ValueError("invalid family registry entry")
            if family["family_id"] in registered or family["split"] not in SPLITS:
                raise ValueError("duplicate or invalid registered family")
            registered[family["family_id"]] = (family["environment"], SPLITS[family["split"]])
        old_ids = set(registry.get("known_development_case_ids", [])) if isinstance(registry, dict) else set()
        old_hashes = set(registry.get("known_development_hashes", [])) if isinstance(registry, dict) else set()
        for row in clean:
            if registered.get(row["family_id"]) != (row["environment"], row["split"]):
                raise ValueError("candidate disagrees with independent family registry: " + row["case_id"])
            if row["split"] != "development" and (row["case_id"] in old_ids or row["normalized_hash"] in old_hashes):
                raise ValueError("known development case cannot become held-out data")
    return clean


def _flow_select(rows, positive_n, negative_n, required_sensitive, family_cap, rng):
    """Integral max flow avoids greedy family-cap choices falsely blocking quotas."""
    graph = defaultdict(dict)
    def edge(a, b, capacity):
        graph[a][b] = capacity
        graph[b].setdefault(a, 0)
    source, sink = ("source",), ("sink",)
    categories = (("positive", positive_n), ("sensitive", required_sensitive),
                  ("negative_extra", negative_n - required_sensitive))
    for category, count in categories:
        edge(source, ("category", category), count)
    shuffled = sorted(rows, key=lambda r: r["case_id"])
    rng.shuffle(shuffled)
    for row in shuffled:
        node = ("case", row["case_id"])
        family = ("family", row["family_id"])
        edge(node, family, 1)
        if row["label"] == 1:
            edge(("category", "positive"), node, 1)
        else:
            edge(("category", "negative_extra"), node, 1)
            if row["sensitive_negative"]:
                edge(("category", "sensitive"), node, 1)
    for family in sorted({r["family_id"] for r in rows}):
        edge(("family", family), sink, family_cap if family_cap is not None else len(rows))
    flow = 0
    while True:
        parents = {source: None}
        queue = deque([source])
        while queue and sink not in parents:
            node = queue.popleft()
            for neighbor, capacity in graph[node].items():
                if capacity > 0 and neighbor not in parents:
                    parents[neighbor] = node
                    queue.append(neighbor)
        if sink not in parents:
            break
        node = sink
        while parents[node] is not None:
            previous = parents[node]
            graph[previous][node] -= 1
            graph[node][previous] += 1
            node = previous
        flow += 1
    selected = [r for r in shuffled if graph[("family", r["family_id"])][("case", r["case_id"])] == 1]
    return selected, flow


def select_test_cases(candidates, quotas, seed=20261103, sensitive_fraction=0.5,
                      max_per_family=None, target_split="test", registry=None):
    """Select only from a fixed pool; no generation/retries or monitor scores.

    quotas is e.g. {'bank': {0: 30, 1: 30}, 'airline': {0: 30, 1: 30}}.
    An insufficient pool returns an empty final selection with explicit shortfalls.
    """
    if registry is None:
        raise ValueError("an independently frozen family registry is required")
    rows = validate_candidates(candidates, registry)
    if target_split not in SPLITS:
        raise ValueError("invalid target split")
    target_split = SPLITS[target_split]
    if isinstance(registry, dict) and target_split == "test" and registry.get("test_families_ready") is False:
        raise ValueError("registry has no ready held-out test families")
    if type(seed) is not int:
        raise ValueError("selection seed must be an integer")
    if type(sensitive_fraction) not in (int, float) or not math.isfinite(sensitive_fraction) or not 0.5 <= sensitive_fraction <= 1:
        raise ValueError("sensitive fraction must be within 0.5..1")
    if max_per_family is not None and (type(max_per_family) is not int or max_per_family < 1):
        raise ValueError("max_per_family must be a positive integer")
    if not isinstance(quotas, dict) or not quotas:
        raise ValueError("nonempty per-environment quotas required")
    normalized_quotas = {}
    for env, counts in quotas.items():
        if not isinstance(env, str) or not env or not isinstance(counts, dict):
            raise ValueError("invalid quotas")
        if set(counts) not in ({0, 1}, {"0", "1"}):
            raise ValueError("quotas must contain exactly labels 0 and 1")
        normalized = {int(k): v for k, v in counts.items()}
        if any(type(v) is not int or v <= 0 for v in normalized.values()):
            raise ValueError("each class quota must be a positive integer")
        normalized_quotas[env] = normalized
    reasons = {r["case_id"]: [] for r in rows}
    hash_groups = defaultdict(list)
    for row in rows:
        rid = row["case_id"]
        if row["split"] != target_split:
            reasons[rid].append("other_split")
        if row["environment"] not in normalized_quotas:
            reasons[rid].append("environment_not_requested")
        if row["origin_kind"] != "natural_actor":
            reasons[rid].append("not_natural_actor_trajectory")
        if row["label"] is None:
            reasons[rid].append("reference_unknown")
        if not row["reference_complete"]:
            reasons[rid].append("incomplete_reference_evidence")
        if not row["capacity_ok"]:
            reasons[rid].append("capacity_ineligible")
        hash_groups[row["normalized_hash"]].append(row)
    for group in hash_groups.values():
        known_labels = {r["label"] for r in group if r["label"] is not None}
        if len(known_labels) > 1:
            for row in group:
                reasons[row["case_id"]].append("duplicate_hash_reference_conflict")
            continue
        outside = [r for r in group if r["split"] != target_split]
        if outside:
            for row in group:
                if row["split"] == target_split:
                    reasons[row["case_id"]].append("duplicate_trace_in_other_split")
            continue
        eligible_group = sorted((r for r in group if not reasons[r["case_id"]]), key=lambda r: r["case_id"])
        for row in eligible_group[1:]:
            reasons[row["case_id"]].append("duplicate_normalized_trace")
    eligible = [r for r in rows if not reasons[r["case_id"]]]
    rng = random.Random(seed)
    provisional, shortfalls, composition = [], [], {}
    for env, quota in sorted(normalized_quotas.items()):
        pool = [r for r in eligible if r["environment"] == env]
        required_sensitive = math.ceil(quota[0] * sensitive_fraction)
        selected, flow = _flow_select(pool, quota[1], quota[0], required_sensitive, max_per_family, rng)
        provisional.extend(selected)
        actual = Counter(r["label"] for r in selected)
        actual_sensitive = sum(r["sensitive_negative"] for r in selected)
        composition[env] = {"positive": actual[1], "negative": actual[0],
                            "sensitive_negative": actual_sensitive,
                            "families": len({r["family_id"] for r in selected})}
        if flow != quota[0] + quota[1]:
            shortfalls.append({"environment": env, "requested_total": quota[0] + quota[1],
                               "feasible_selected_total": flow,
                               "positive_shortfall": quota[1] - actual[1],
                               "negative_shortfall": quota[0] - actual[0],
                               "sensitive_negative_shortfall": max(0, required_sensitive - actual_sensitive)})
    provisional_ids = sorted(r["case_id"] for r in provisional)
    selected_ids = [] if shortfalls else provisional_ids
    selected_set = set(provisional_ids)
    for row in eligible:
        if row["case_id"] not in selected_set:
            reasons[row["case_id"]].append("not_selected_by_frozen_quota_and_seed")
        elif shortfalls:
            reasons[row["case_id"]].append("selection_not_frozen_pool_insufficient")
    receipt = {
        "schema_version": "prospective-selection-v1",
        "status": "insufficient_pool" if shortfalls else "selection_ready_no_monitoring_run",
        "seed": seed, "target_split": target_split, "candidate_count": len(rows),
        "eligible_deduplicated_count": len(eligible),
        "quotas": {env: {str(k): v for k, v in q.items()} for env, q in sorted(normalized_quotas.items())},
        "sensitive_negative_minimum_fraction": sensitive_fraction,
        "max_per_family": max_per_family,
        "selected_case_ids": selected_ids,
        "provisional_case_ids": provisional_ids if shortfalls else [],
        "composition": composition, "shortfalls": shortfalls,
        "exclusions": [{"case_id": rid, "reasons": why} for rid, why in sorted(reasons.items()) if why],
        "input_sha256": hashlib.sha256(_canonical(sorted(rows, key=lambda r: r["case_id"])).encode()).hexdigest(),
        "registry_sha256": hashlib.sha256(_canonical(registry).encode()).hexdigest(),
    }
    receipt["selection_sha256"] = hashlib.sha256(_canonical(receipt).encode()).hexdigest()
    return receipt
