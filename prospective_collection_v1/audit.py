"""Offline integrity replay and review packet. Never certifies the AI review itself."""
import argparse
import json
from pathlib import Path
from copy import deepcopy

from .runner import ROOT, PREP, load, save, sha
from prospective_data_v2.specs import digest
from prospective_data_v2.prepare import validate_manifest
from prospective_monitoring.reference import evaluate_reference
from prospective_monitoring.simulator import project_state, SnapshotError


def audit(campaign, output):
    campaign, output = Path(campaign), Path(output)
    output.mkdir(exist_ok=False)
    manifest = validate_manifest(load(PREP / "manifest_PRIVATE.json"))
    filemap = load(campaign / "file_hashes.json")
    for name, expected in filemap.items():
        if sha(campaign / name) != expected:
            raise ValueError("Downloaded evidence hash mismatch: " + name)
    cards = []
    for task in manifest["tasks"]:
        p = campaign / "cases" / task["case_id"]
        if not (p / "result_private.json").is_file():
            cards.append({"case_id":task["case_id"], "environment":task["environment"],
                          "family":task["family_id"], "status":"not_received", "ai_review_complete":False})
            continue
        result, evidence = load(p / "result_private.json"), load(p / "execution_evidence_private.json")
        issues = []
        if load(p / "task_private.json") != task:
            issues.append("frozen_task_mismatch")
        if result["origin_kind"] != "natural_actor" or evidence["origin_kind"] != "natural_actor":
            issues.append("not_a_natural_actor")
        if digest(result["conversation"]) != result["conversation_sha256"]:
            issues.append("conversation_digest_mismatch")
        if result["journal"] != evidence["journal"]:
            issues.append("journal_mismatch")
        ref = evaluate_reference(result["contract"], evidence["journal"])
        if ref != result["reference"]:
            issues.append("reference_replay_mismatch")
        if len(evidence["raw_tool_receipts"]) != len(result["journal"]["events"]):
            issues.append("tool_evidence_count_mismatch")
        previous = None
        for raw, event in zip(evidence["raw_tool_receipts"], result["journal"]["events"]):
            for phase in ("before", "after"):
                if digest(raw[phase+"_raw"]) != raw[phase+"_sha256"]:
                    issues.append("raw_state_digest_mismatch")
                try:
                    state = project_state(raw[phase+"_raw"], task["environment"])
                except (SnapshotError, KeyError, TypeError):
                    state = None
                if state != event[phase]:
                    issues.append("raw_state_projection_mismatch")
            if previous is not None and previous != raw["before_raw"]:
                issues.append("raw_state_chain_broken")
            previous = raw["after_raw"]
            for key in ("event_id", "call_source_id", "result_source_id"):
                if raw[key] != event[key]: issues.append("source_pointer_mismatch")
        native_turns = []
        for turn in sorted((p / "turns").glob("turn_*")):
            req = load(turn / "request.json")
            if digest(req) != load(turn / "request_hash.json")["sha256"]:
                issues.append("request_hash_mismatch")
            claim = campaign / "calls" / f"{task['case_id']}-{req['turn_index']:02d}.json"
            if (turn / "dispatch.json").exists():
                if not claim.is_file() or load(claim)["request_sha256"] != digest(req):
                    issues.append("missing_or_mismatched_durable_call_claim")
            if (turn / "raw.json").is_file():
                raw = load(turn / "raw.json")
                if raw["usage_mode"] != "native_model_usage": issues.append("not_native_model_usage")
                native_turns.append({"turn":req["turn_index"], "finish_reason":raw["finish_reason"],
                                     "output_tokens":raw["completion_tokens"]})
        cards.append({"case_id":task["case_id"], "instance_id":task["instance_id"],
             "environment":task["environment"], "family":task["family_id"], "status":result["status"],
             "stop_reason":result["stop_reason"], "initial_user":task["initial_user_text"],
             "delivered_authorizations":[m for m in result["conversation"] if m["role"]=="user"],
             "actual_events":[{k:v for k,v in e.items() if k not in {"before","after"}}
                              for e in result["journal"]["events"]],
             "tool_calls":[{"function":r["function"], "args":r["args"], "output":r["output"], "error":r["error"]}
                           for r in evidence["raw_tool_receipts"]],
             "final_text":[m["content"] for m in result["conversation"] if m.get("channel")=="final"],
             "contract":result["contract"], "reference_replayed":ref,
             "native_turns":native_turns, "integrity_issues":sorted(set(issues)),
             "task_sha256":digest(task), "evidence_sha256":sha(p/"execution_evidence_private.json"),
             "ai_review_complete":False})
    save(output/"review_cards_PRIVATE.json", cards)
    save(output/"integrity_summary.json", {"files_verified":len(filemap), "cards":len(cards),
         "issues":{r["case_id"]:r["integrity_issues"] for r in cards if r.get("integrity_issues")},
         "human_review":False, "ai_review_complete":False, "model_calls":0})
    return cards


if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--campaign",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    audit(a.campaign,a.output)
