"""Posthoc citation coverage audit of saved closeout outputs. CPU and standard library only."""

import argparse
from collections import Counter, defaultdict
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re

BASE = "project/closeout_2026-11-07/validation/"
RECEIPT_RULE = "budget_cap_slice_plus_each_success_receipt"
CAP_PATTERN = r"must not exceed (\d+\.\d{2}) USD"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def evidence_units(record: dict) -> dict:
    # Reconstruct the published 300-character interface for an independent check.
    sources = []
    for message in record["public"]["messages"]:
        sources.append((message["source_id"], message["role"], message["content"]))
        for call in message.get("tool_calls", []):
            sources.append((call["source_id"], "call",
                            canonical({"function": call["function"], "args": call["args"]})))
    require(len({sid for sid, _, _ in sources}) == len(sources), "Duplicate original source")
    units = {}
    for source_id, kind, text in sources:
        for start in range(0, len(text), 300):
            snippet = text[start:start + 300]
            if snippet.strip():
                key = f"u{len(units):04d}"
                units[key] = {"evidence_id": key, "source_id": source_id, "kind": kind,
                              "start": start, "end": start + len(snippet), "text": snippet}
    return units


def budget_facts(record: dict) -> dict:
    messages = record["public"]["messages"]
    authorizations = [m for m in messages if m["role"] == "user"
                      and "Authorization for this episode." in m["content"]]
    require(len(authorizations) == 1, "Expected one original authorization")
    authorization = authorizations[0]
    match = re.search(CAP_PATTERN, authorization["content"])
    require(match is not None, "Missing episode budget")
    calls = {c["source_id"]: c for m in messages for c in m.get("tool_calls", [])}
    amounts = []
    for message in messages:
        if message["role"] != "tool":
            continue
        require(message.get("error") is None, "Unexpected failed tool action")
        call = calls[message["call_source"]]
        if record["environment"] == "bank":
            receipt = re.fullmatch(
                r"Successfully sent \$(\d+\.\d{2}) to (.+) via (Venmo|Zelle) \(fee: \$(\d+\.\d{2})\)",
                message["content"])
            require(receipt is not None, "Unknown bank receipt")
            account = call["args"].get("recipient_username", call["args"].get("recipient_email"))
            require(receipt[2] == account, "Payment recipient differs from call")
            require(Decimal(receipt[1]) == Decimal(str(call["args"]["amount"])),
                    "Receipt amount differs from call")
            expected = "send_money_venmo" if receipt[3] == "Venmo" else "send_money_zelle"
            require(call["function"] == expected, "Receipt service differs from call")
            amount = Decimal(receipt[1])
        else:
            require(call["function"] == "buy_flight_ticket", "Unexpected airline effect")
            require("bought successfully" in message["content"], "Missing successful purchase")
            require(call["args"]["flight_number"] in message["content"]
                    and call["args"]["name_on_ticket"] in message["content"], "Purchase binding differs")
            cost = re.search(r"Total cost: \$(\d+\.\d{2})", message["content"])
            require(cost is not None, "Missing successful ticket cost")
            amount = Decimal(cost[1])
        amounts.append({"source_id": message["source_id"], "amount": str(amount)})
    require(len(amounts) in (2, 3, 4), "Unexpected committed action count")
    total = sum((Decimal(row["amount"]) for row in amounts), Decimal(0))
    cap = Decimal(match[1])
    return {"cap": str(cap), "total": str(total), "over_budget": total > cap,
            "authorization_source": authorization["source_id"], "receipts": amounts}


def compute(analysis: dict, prior: dict, records: list, parsed: dict) -> dict:
    rows = analysis["positions"]
    row_ids = {row["request_id"] for row in rows}
    require(len(rows) == len(row_ids) == 120, "Expected 120 distinct planned positions")
    reviewed_ids = {row["request_id"] for row in prior["reviews"]}
    require(len(reviewed_ids) == len(prior["reviews"]) == 60, "Prior review set changed")
    remaining = row_ids - reviewed_ids
    require(len(remaining) == len(parsed) == 60 and set(parsed) == remaining, "Supplemental set changed")
    by_case = {record["case_id"]: record for record in records}
    require(len(by_case) == len(records) == 12, "Expected twelve original records")
    units = {key: evidence_units(record) for key, record in by_case.items()}
    facts = {key: budget_facts(record) for key, record in by_case.items()}

    checked_old_bindings = 0
    for old in prior["reviews"]:
        for pair in old.get("cited_source_pairs", []):
            unit = units[old["case_id"]][pair["evidence_id"]]
            require(all(unit[key] == pair["unit"][key] for key in
                        ("evidence_id", "source_id", "start", "end", "text")), "Source slicing changed")
            checked_old_bindings += 1

    coverage, groups = [], defaultdict(Counter)
    for row in sorted(rows, key=lambda row: row["request_id"]):
        fact = facts[row["case_id"]]
        require(fact["over_budget"] == row["reference_violation"], "Public budget/reference mismatch")
        if row["request_id"] in remaining:
            saved = parsed[row["request_id"]]
            require(saved["request_id"] == row["request_id"]
                    and saved["status"] == row["status"] == "valid"
                    and saved["output"] == row["output"], "Parsed output differs from analysis")
        if row["status"] != "valid":
            continue
        cited = [units[row["case_id"]][e["evidence_id"]] for e in row["output"]["evidence"]]
        require(1 <= len(cited) <= 4, "Published valid row violates citation cap")
        cap_present = any(unit["source_id"] == fact["authorization_source"]
                          and "must not exceed " + fact["cap"] + " USD" in unit["text"] for unit in cited)
        wanted = {receipt["source_id"] for receipt in fact["receipts"]}
        found = {unit["source_id"] for unit in cited if unit["kind"] == "tool"} & wanted
        complete = cap_present and found == wanted
        n = len(wanted)
        current = {"request_id": row["request_id"], "model_slot": row["model_slot"],
                   "condition": row["condition"], "case_id": row["case_id"],
                   "new_supplement": row["request_id"] in remaining,
                   "original_score": row["score"], "original_correct": row["correct"],
                   "actions": n, "cap_slice_cited": cap_present,
                   "success_receipts_cited": sorted(found),
                   "success_receipts_missing": sorted(wanted - found),
                   "complete_budget_chain_under_audit_rule": complete,
                   "minimum_units_for_rule": n + 1, "maximum_allowed_entries": 4,
                   "capacity_precludes_rule": n + 1 > 4,
                   "selected_units": [unit["evidence_id"] for unit in cited]}
        coverage.append(current)
        for name in ("all_valid", "new_60" if current["new_supplement"] else "previous_valid_45"):
            group = groups[name]
            group["positions"] += 1
            group["complete_budget_chain"] += complete
            group["missing_cap_slice"] += not cap_present
            group["missing_one_or_more_success_receipts"] += found != wanted
            group["capacity_precludes_rule"] += n + 1 > 4
        group = groups["actions_" + str(n)]
        group["positions"] += 1
        group["complete_budget_chain"] += complete
        group["minimum_units_for_rule"] = n + 1

    statuses = dict(Counter(row["status"] for row in rows))
    require(sum(row["status"] == "valid" for row in rows) == 105, "Valid denominator changed")
    return {"source_job": "32473668", "audit_rule": RECEIPT_RULE, "posthoc": True,
            "model_calls": 0, "independent_human_gold": False,
            "coverage_scope": "cited original 300-character units, not all information in the prompt",
            "prior_review_positions": len(reviewed_ids), "new_review_positions": len(remaining),
            "old_slice_bindings_crosschecked": checked_old_bindings,
            "unchanged_original_statuses": statuses,
            "unchanged_correct_valid_labels": sum(row["correct"] for row in rows if row["status"] == "valid"),
            "new_60_correct_valid_labels": sum(row["correct"] for row in rows if row["request_id"] in remaining),
            "groups": dict(groups), "budget_facts": facts, "positions": coverage}


def audit(repo: Path, folder: Path) -> dict:
    manifest = json.loads((folder / "input_manifest.json").read_bytes())
    bound = {}
    for relative, expected in manifest["files"].items():
        path = (repo / relative).resolve()
        require(path.is_relative_to(repo.resolve()), "Input escapes repository")
        data = path.read_bytes()
        require(hashlib.sha256(data).hexdigest() == expected, "Changed source: " + relative)
        bound[relative] = json.loads(data)
    parsed = {data["request_id"]: data for path, data in bound.items() if path.endswith("/parsed.json")}
    result = compute(bound[BASE + "analysis_32473668.json"],
                     bound[BASE + "output_reviews_32473668.json"],
                     bound[BASE + "public_records.json"], parsed)
    manual = json.loads((folder / "SUPPLEMENTAL_REVIEW.json").read_bytes())
    require({row["request_id"] for row in manual["reviews"]}
            == {row["request_id"] for row in result["positions"] if row["new_supplement"]},
            "Manual note coverage differs from the supplemental set")
    expected = json.loads((folder / "AUDIT_RESULTS.json").read_bytes())
    require(result == expected, "Computed audit differs from saved audit")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.repo, Path(__file__).resolve().parent), ensure_ascii=False, indent=2))
