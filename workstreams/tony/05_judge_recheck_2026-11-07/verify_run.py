"""Verify the saved Workstream C recheck offline using the original two ZIPs."""

import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

import judge_contract as contract

PACKET_SHA = "7d663e9e66c4113c5eb6a4edb9e2f0f76867572ce09e169272dc77e5a4a35951"
RESULT_SHA = "f198ff679b9e24b0df780a56a2866ec3771915f28e2753f4469c5e3445f0016f"


def read_lines(data):
    return [json.loads(line) for line in data.splitlines() if line.strip()]


def verify(packet_path, result_path):
    for path, expected in ((packet_path, PACKET_SHA), (result_path, RESULT_SHA)):
        contract.require(hashlib.sha256(path.read_bytes()).hexdigest() == expected,
                         f"Archive hash mismatch: {path.name}")

    with ZipFile(packet_path) as packet, ZipFile(result_path) as run:
        original_code = packet.read("judge_recheck_v2_1/judge_contract.py")
        contract.require(Path(contract.__file__).read_bytes() == original_code,
                         "Validator differs from the original execution packet")
        cases = read_lines(packet.read("judge_recheck_v2_1/frozen_cases.jsonl"))
        manifest = packet.read("judge_recheck_v2_1/PACKET_MANIFEST.json")
        prefix = "runs/JUDGE_RECHECK_32376521/"
        raw_calls = read_lines(run.read(prefix + "judge_raw.jsonl"))
        saved = read_lines(run.read(prefix + "judge_results.jsonl"))
        receipt = json.loads(run.read(prefix + "capacity_receipt.json"))
        summary = json.loads(run.read(prefix + "comparison.json"))
        sources = json.loads(run.read(prefix + "sources.json"))

    jobs = contract.jobs(cases)
    contract.require(receipt["manifest_sha256"] == contract.sha(manifest), "Manifest mismatch")
    contract.require(sources == {job["id"]: job["sources"] for job in jobs}, "Source mismatch")
    contract.require(len(raw_calls) == len(saved) == len(jobs), "Missing call or result")
    contract.require(tuple(raw["job_index"] for raw in raw_calls) == contract.EXECUTION_ORDER,
                     "Call order mismatch")

    public = json.loads(Path(__file__).with_name("results.json").read_bytes())
    action_counts = dict.fromkeys(public["action_rows"], 0)
    per_call = []
    for raw, result in zip(raw_calls, saved):
        idx = raw["job_index"]
        job, cap = jobs[idx], receipt["cases"][idx]
        label = f"{job['id']} ({job['arm']})"
        ids = raw["prompt_token_ids"]
        contract.require(raw["prompt"] == job["prompt"], f"Prompt mismatch: {label}")
        for key in ("prompt_sha256", "qa_sha256", "schema_sha256"):
            contract.require(job[key] == cap[key], f"{key} mismatch: {label}")
        contract.require(contract.objsha(ids) == cap["prompt_ids_sha256"],
                         f"Prompt token IDs mismatch: {label}")
        contract.require(len(ids) == result["input_tokens"] == cap["input_tokens"],
                         f"Input token count mismatch: {label}")
        contract.require(0 < len(raw["completion_token_ids"]) == result["output_tokens"]
                         <= receipt["output_reserved"], f"Output token count mismatch: {label}")
        contract.require(raw["finish_reason"] == "stop", f"Unexpected stop reason: {label}")
        decision = contract.validate(raw["raw"], job)
        contract.require(decision == result["decision"], f"Decision mismatch: {label}")
        for row in decision["actions"]:
            refs = set(row["model_basis_ids"])
            action_counts["total"] += 1
            action_counts["model_basis_request_and_policy_only"] += refs == {"u", "p"}
            action_counts["with_model_tool_reference"] += any(
                src["kind"] == "tool_result" and src["source_id"] in refs for src in job["sources"]
            )
        per_call.append((idx, {"case_id": job["id"], "arm": job["arm"],
                              "status": result["status"], "score": decision["score"],
                              "verdict": decision["trajectory_verdict"],
                              "action_rows": len(decision["actions"]),
                              "input_tokens": result["input_tokens"],
                              "output_tokens": result["output_tokens"]}))

    computed = contract.summarize(jobs, saved)
    contract.require(all(summary[key] == value for key, value in computed.items()),
                     "Original comparison summary mismatch")
    for key in ("planned", "attempted", "not_run", "format_valid", "invalid", "abstentions",
                "format_valid_pairs", "accuracy_tpr_fpr", "independent_human_gold", "token_costs"):
        contract.require(public[key] == summary[key], f"Public summary mismatch: {key}")
    contract.require(public["cases"] == [row for _, row in sorted(per_call)],
                     "Public per-call metrics mismatch")
    contract.require(public["action_rows"] == action_counts, "Public action counts mismatch")
    print(f"Verified {computed['format_valid']}/{len(jobs)} outputs "
          f"and {computed['format_valid_pairs']} pairs against the archived run.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("execution_packet", type=Path)
    parser.add_argument("result_archive", type=Path)
    args = parser.parse_args()
    verify(args.execution_packet, args.result_archive)
