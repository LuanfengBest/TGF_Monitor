"""Original-simulator witnesses and collection integration, no model client."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

from prospective_monitoring.collection import collect_case
from prospective_monitoring.reference import evaluate_reference
from prospective_monitoring.simulator import load_original_environment
from .prepare import validate_manifest, verify_sources, write_json
from .specs import CASE_LIMITS, build_task, digest


def prepare_environment(scenario):
    environment, runtime = load_original_environment(scenario["environment"])
    setup = scenario["environment_setup"]
    if scenario["environment"] == "bank":
        from environment_classes.venmo import Contact
        from environment_classes.zelle import Contact as ZelleContact
        environment.venmo.transaction_history = []
        environment.zelle.transaction_history = []
        environment.venmo.balance_value = float(setup["balance"])
        environment.zelle.balance_value = float(setup["balance"])
        environment.venmo.contacts = {}
        environment.zelle.contacts = {}
        for recipient in setup["contacts"]:
            service, account = recipient.split(":", 1)
            if service == "venmo":
                environment.venmo.add_contact(Contact(username=account, full_name=account))
            elif service == "zelle":
                environment.zelle.add_contact(ZelleContact(email=account, full_name=account))
            else:
                raise ValueError("Unsupported service")
    else:
        from environment_classes.travel_booking import Flight, Flights
        from environment_classes.ticket import TicketManager
        environment.flights = Flights(flight_list=[Flight(**f) for f in setup["flights"]])
        environment.ticket_manager = TicketManager()
        environment.flight_tickets = {}
        environment.total_spent = {}
    return environment, runtime


class WitnessActor:
    origin_kind = "scripted_cpu_fixture"

    def __init__(self, actions):
        self.actions = deepcopy(actions) + [{"function": "end_task", "args": {}}]
        self.requests = []

    def generate_actor(self, request, timeout_seconds):
        self.requests.append(deepcopy(request))
        if not self.actions:
            raise AssertionError("Unexpected extra witness call")
        action = self.actions.pop(0)
        if action["function"] == "cancel_flight_booking":
            marker = action["args"]["confirmation_number"]
            flight = marker.removeprefix("$receipt:")
            replies = [m["content"] for m in request["conversation"] if m["role"] == "tool"]
            pattern = re.compile(r"Flight ticket " + re.escape(flight) + r" \(confirmation: ([^)]+)\) bought successfully")
            found = [pattern.search(s) for s in replies if isinstance(s, str)]
            found = [m.group(1) for m in found if m]
            if len(found) != 1:
                raise ValueError("Cancellation must bind to one real booking receipt")
            action["args"]["confirmation_number"] = found[0]
        return {"messages": [{"role": "assistant", "channel": "commentary", "content": "",
                              "tool_calls": [{**action, "id": None}]}],
                "finish_reason": "stop", "model": "scripted-witness-no-model",
                "prompt_tokens": 0, "completion_tokens": 0, "inference_seconds": 0.0,
                "usage_complete": True, "usage_mode": "scripted_fixture_no_model"}


def run_witness(instance, kind, output):
    witness = instance["witnesses_PRIVATE"][kind]
    task = build_task(instance, "ordinary")
    actor = WitnessActor(witness["actions"])
    result = collect_case(task, actor, output, limits=CASE_LIMITS, environment_factory=prepare_environment)
    ref = result["reference"]
    issues = []
    if result["status"] != "completed" or ref["status"] != "resolved" or ref["label"] != witness["expected_label"]:
        issues.append("collection_or_reference_does_not_match_scripted_expectation")
    if not result["journal"]["complete"] or result["model_calls"] != 0 or result["formal_test_eligible"]:
        issues.append("provenance_or_evidence_invalid")
    if len(result["journal"]["events"]) != len(witness["actions"]) or any(e["status"] != "committed" for e in result["journal"]["events"]):
        issues.append("planned_sensitive_action_not_committed")
    if kind == "violation" and not any(v["sequence"] == witness["expected_sequence"] and
                                        witness["expected_reason"] in v["reasons"] for v in ref["violations"]):
        issues.append("expected_violation_witness_not_found")
    public = result["monitor_case"]["public"] if result["monitor_case"] else None
    if public is None or any(m["role"] == "system" for m in public["messages"]):
        issues.append("public_projection_invalid")
    future = task["authorization_messages"][1:]
    initial = [m["content"] for m in actor.requests[0]["conversation"]]
    if any(m["content"] in initial for m in future):
        issues.append("future_authorization_delivered_early")
    if future:
        updated = [m["content"] for m in actor.requests[1]["conversation"]]
        if any(m["content"] not in updated for m in future):
            issues.append("future_authorization_not_delivered_before_next_attempt")
    broken = deepcopy(result["journal"])
    broken["complete"] = False
    unknown = evaluate_reference(result["contract"], broken)
    if unknown["label"] is not None or unknown["status"] != "reference_unknown":
        issues.append("incomplete_evidence_was_treated_as_label")
    receipt = {"instance_id": instance["instance_id"], "template_id": instance["template_id"],
               "variant": instance["variant"], "kind": kind, "origin_kind": "scripted_cpu_fixture",
               "expected_label": witness["expected_label"], "actual_label": ref["label"],
               "reference_status": ref["status"], "violations": ref["violations"],
               "committed_events": ref["committed_events"], "model_calls": 0,
               "incomplete_evidence_returns_unknown": unknown["label"] is None,
               "result_sha256": hashlib.sha256((output / "result_private.json").read_bytes()).hexdigest(),
               "issues": issues, "passed": not issues}
    return result, receipt


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--prepared", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    manifest = validate_manifest(json.loads((args.prepared / "manifest_PRIVATE.json").read_text()))
    verify_sources(json.loads((args.prepared / "source_hashes.json").read_text()))
    args.out.mkdir(parents=True, exist_ok=False)
    receipts, cancellation_checks = [], []
    for instance in manifest["instances"]:
        results = {}
        for kind in ("legal", "violation"):
            result, receipt = run_witness(instance, kind, args.out / (instance["instance_id"] + "-" + kind))
            receipts.append(receipt)
            results[kind] = result
        if instance["template_id"] == "airline_forward_change_cancel":
            # Final bookings are the same; the earlier wrong-date purchase is not erased.
            same = results["legal"]["journal"]["final_state"] == results["violation"]["journal"]["final_state"]
            cancellation_checks.append({"instance_id": instance["instance_id"], "same_final_state": same,
                                        "legal_label": results["legal"]["reference"]["label"],
                                        "violation_label": results["violation"]["reference"]["label"]})
    verify_sources(json.loads((args.prepared / "source_hashes.json").read_text()))
    passed = all(r["passed"] for r in receipts) and all(c["same_final_state"] for c in cancellation_checks)
    summary = {"scope": "scripted_original_simulator_validation_only", "manifest_sha256": digest(manifest),
               "witnesses": receipts, "witness_count": len(receipts),
               "passed": passed, "actual_actor_model_calls": 0, "natural_actor_trajectories": 0,
               "cancellation_history_checks": cancellation_checks, "sources_unchanged": True}
    write_json(args.out / "summary.json", summary)
    print(json.dumps({"witnesses": len(receipts), "passed": passed, "model_calls": 0,
                      "failed": [r for r in receipts if not r["passed"]]}, ensure_ascii=False))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
