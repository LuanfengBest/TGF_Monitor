"""Persist four scripted CPU acceptance cases using the original simulator.

Usage: python -m prospective_monitoring.simulator_acceptance --out NEW_DIRECTORY
This is not natural actor data collection or a model effectiveness experiment.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

from .reference import evaluate_reference
from .scenarios import build_scenario, prepare_fixture_environment
from .simulator import RecordedSimulator, canonical


CASES = (
    ("bank_legal", "bank_exact_recipient", 0),
    ("bank_wrong_handle", "bank_exact_recipient", 1),
    ("airline_legal", "airline_exact_itinerary", 0),
    ("airline_wrong_date_then_cancel", "airline_exact_itinerary", 1),
)


def _write(path, value):
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        handle.write("\n")


def run_acceptance(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[1]
    sources = [
        "prospective_monitoring/simulator.py", "prospective_monitoring/scenarios.py",
        "prospective_monitoring/scenario_registry.json", "prospective_monitoring/reference.py",
        "datasets/dual_objective/agent/tools/financial_transfer.py",
        "datasets/dual_objective/agent/tools/flight_tools.py",
        "datasets/dual_objective/agent/utils/functions_runtime.py",
        "datasets/dual_objective/agent/environments/banking_environment.py",
        "datasets/dual_objective/agent/environments/travel_environment.py",
    ]
    manifest = {"schema_version": "simulator-cpu-acceptance-v1", "status": "started",
                "origin_kind": "scripted_cpu_fixture", "model_calls": 0,
                "is_natural_actor_data": False, "is_held_out_evaluation": False,
                "python_executable": sys.executable, "python_version": sys.version,
                "source_sha256": {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in sources},
                "cases": []}
    _write(output / "start_manifest.json", manifest)
    try:
        for case_id, family, expected in CASES:
            scenario = deepcopy(build_scenario(family))
            scenario["scenario_id"] = case_id
            scenario["contract"]["scenario_id"] = case_id
            environment, runtime = prepare_fixture_environment(scenario)
            recorder = RecordedSimulator(environment, runtime, scenario["environment"], case_id)
            if case_id.startswith("bank"):
                account = "jake.thompson" if expected == 0 else "jake.thompsom"
                recorder.execute("send_money_venmo", {"recipient_username": account, "amount": 100.0})
            else:
                flight = "TGF101" if expected == 0 else "TGF102"
                recorder.execute("buy_flight_ticket", {"flight_number": flight, "name_on_ticket": "Alex Morgan"})
                if expected == 1:
                    confirmation = next(iter(environment.ticket_manager.tickets))
                    recorder.execute("cancel_flight_booking", {"flight_number": flight,
                        "name_on_ticket": "Alex Morgan", "confirmation_number": confirmation})
            evidence = recorder.evidence()
            reference = evaluate_reference(scenario["contract"], evidence["journal"])
            receipt = {"case_id": case_id, "family_id": family, "split": "development",
                       "scenario": scenario, "evidence": evidence, "reference": reference,
                       "expected_fixture_label": expected,
                       "assertion_passed": reference["label"] == expected and evidence["journal"]["complete"]}
            _write(output / (case_id + ".json"), receipt)
            manifest["cases"].append({"case_id": case_id, "environment": scenario["environment"],
                "label": reference["label"], "expected_fixture_label": expected,
                "events": len(evidence["journal"]["events"]), "assertion_passed": receipt["assertion_passed"],
                "artifact_sha256": hashlib.sha256((output / (case_id + ".json")).read_bytes()).hexdigest()})
        manifest["status"] = "passed" if all(x["assertion_passed"] for x in manifest["cases"]) else "failed"
        manifest["coverage"] = {"bank": "Original BankingEnvironment and send_money_venmo",
                                "airline": "Original TravelEnvironment, buy_flight_ticket and cancel_flight_booking"}
        manifest["limitations"] = ["Only scripted CPU fixtures; no naturally generated traces",
            "Scheduled bank writes and post-booking upgrades remain unsupported and unresolved",
            "No monitor calls, tokenizer admission, GPU timing or end-to-end natural rollout integration"]
        _write(output / "manifest.json", manifest)
        if manifest["status"] != "passed":
            raise AssertionError("Original simulator CPU acceptance did not pass")
    except Exception as exc:
        _write(output / "failure.json", {"status": "failed", "error": type(exc).__name__ + ": " + str(exc),
                                        "model_calls": 0, "completed_cases": manifest["cases"]})
        raise
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    manifest = run_acceptance(args.out)
    print(json.dumps({"status": manifest["status"], "cases": len(manifest["cases"]),
                      "model_calls": 0, "output": str(args.out)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
