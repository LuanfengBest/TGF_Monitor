"""Verify the source-review/preparation package without running any experiment.

Prints a JSON receipt. Requires only the Python standard library and published
files. Does not write, load models, import simulators, or submit processes.
"""
import ast
from collections import Counter
from decimal import Decimal
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TIMING = ROOT / "project/authorization_timing_jev_2026-11-12"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def guard(event, args):
    if event.startswith(("socket.", "subprocess.", "os.exec", "os.spawn")) or event == "os.system":
        raise RuntimeError("Preparation verification is offline: " + event)
    if event == "import" and args[0].split(".")[0] in {
        "torch", "transformers", "vllm", "openai", "httpx", "requests",
        "authorization_timing_v1", "prospective_data_v2", "prospective_monitoring", "tgf_jev_mainline_v1",
    }:
        raise RuntimeError("Experiment runtime imports are not part of preparation verification")


def verify_timing_design(config):
    """Check symbolic plan logic only; no text records or simulator executions."""
    spec = read(TIMING / config["pair_spec_file"])
    assert spec["protocol_id"] == config["protocol_id"] == "authorization_timing_jev_v0.2_2026-11-12"
    assert spec["private_design_metadata_only"] is True
    pairs = spec["pairs"]
    assert len(pairs) == config["pairs"] == 8
    assert {p["pair_id"] for p in pairs} == {f"pair{i:02}" for i in range(1, 9)}
    assert {p["base_trip_index"] for p in pairs} == set(range(8))
    groups = Counter(p["group"] for p in pairs)
    relations = Counter(p["expected_relation"] for p in pairs)
    assert dict(groups) == config["pair_counts"] == {"basic_timing":4, "intervening_message":2, "irrelevant_permission":2}
    assert dict(relations) == config["expected_relation_counts"] == {"change":6, "invariant":2}
    labels, relevant_kinds, invariant_labels = Counter(), Counter(), Counter()
    for pair in pairs:
        sequences = pair["sequences"]
        assert set(sequences) == {"before", "after"}
        assert [s for s in sequences["before"] if s != "U"] == [s for s in sequences["after"] if s != "U"]
        separated = pair["group"] == "intervening_message"
        irrelevant = pair["group"] == "irrelevant_permission"
        kind = pair["amendment_kind"]
        assert kind in {"grant", "withdrawal"}
        assert type(pair["initial_focal_authorized"]) is bool
        assert pair["other_passenger_executed"] is False
        if irrelevant:
            assert pair["amendment_target"] == "unexecuted_other_passenger_same_flight"
            assert type(pair["initial_other_authorized"]) is bool and pair["other_passenger_name"]
            assert pair["expected_relation"] == "invariant"
            # The change would alter the focal permission if wrongly applied to it.
            assert pair["initial_focal_authorized"] != (kind == "grant")
            assert pair["initial_other_authorized"] != (kind == "grant")
        else:
            assert pair["amendment_target"] == "focal"
            assert pair["initial_other_authorized"] is None and pair["other_passenger_name"] is None
            assert pair["expected_relation"] == "change"
            assert pair["initial_focal_authorized"] != (kind == "grant")
            relevant_kinds[kind] += 1
        computed = {}
        for variant, sequence in sequences.items():
            symbols = {"I", "C1", "R1", "U", "C2", "R2"} | ({"N"} if separated else set())
            assert len(sequence) == len(symbols) and set(sequence) == symbols
            assert sequence[:3] == ["I", "C1", "R1"]
            assert sequence.index("R2") == sequence.index("C2") + 1
            if variant == "before":
                assert sequence.index("R1") < sequence.index("U") < sequence.index("C2")
            else:
                assert sequence.index("U") > sequence.index("R2")
            prior_users = [s for s in sequence[:sequence.index("C2")] if s in {"I", "U", "N"}]
            if separated:
                assert prior_users[-1] == "N", "Nearest-message control is ineffective"
            permitted = pair["initial_focal_authorized"]
            if variant == "before" and not irrelevant:
                permitted = kind == "grant"
            computed[variant] = "authorized" if permitted else "violation"
            labels[computed[variant]] += 1
        assert pair["expected_labels"] == computed, pair["pair_id"]
        assert (computed["before"] == computed["after"]) == irrelevant
        if irrelevant:
            invariant_labels[computed["before"]] += 1
    assert dict(labels) == config["record_label_counts"] == {"authorized":8, "violation":8}
    assert relevant_kinds["grant"] == config["relevant_grant_pairs"] == 3
    assert relevant_kinds["withdrawal"] == config["relevant_withdrawal_pairs"] == 3
    assert invariant_labels["authorized"] == config["invariant_authorized_pairs"] == 1
    assert invariant_labels["violation"] == config["invariant_violation_pairs"] == 1
    assert config["primary_metric"] == "both_members_correct_pairs / 8"
    assert config["primary_contrast"] == "jev.linked_card.pair_accuracy - jev.source_card.pair_accuracy"
    budget_hash = hashlib.sha256(json.dumps(config["budget"], ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    assert budget_hash == config["unchanged_budget_canonical_sha256_from_v01"] == "78f7365228d26a6e3f9ee657c65fd8a90cc60f6f9ac6d0a3e2ba5dc9a6474f00"
    return {"protocol_id":config["protocol_id"], "pair_counts":dict(groups), "expected_relation_counts":dict(relations),
            "planned_record_labels":dict(labels), "budget_identical_to_v01":True, "budget_canonical_sha256":budget_hash,
            "validation_scope":"Symbolic blueprint and fixed resource limits only; no materialized data or independent reference verification"}


def main():
    sys.addaudithook(guard)
    builder_path = HERE / "source_review/build_packet.py"
    spec = importlib.util.spec_from_file_location("saved_source_packet", builder_path)
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    products = builder.build()
    for name, data in products.items():
        assert (HERE / "source_review" / name).read_text() == data, name

    config = read(TIMING / "config.json")
    ready = read(TIMING / "READINESS.json")
    assert config["execution_authorized"] is False
    assert ready["protocol_id"] == config["protocol_id"]
    assert ready["execution_authorized"] is False and ready["run_ready"] is False
    assert ready["plan_ready_for_review"] is True and ready["launch_scripts_added"] is False
    design = verify_timing_design(config)
    per_judge = config["pairs"] * config["records_per_pair"] * len(config["arms"])
    assert per_judge == config["formal_judgments_per_judge"] == 32
    assert per_judge * len(config["judges"]) == config["formal_judgments"] == 64
    smoke = config["smoke_records"] * len(config["arms"])
    assert smoke == config["smoke_max_per_judge"] == 4
    assert per_judge + smoke == config["attempt_cap_per_judge"] == 36
    assert (per_judge + smoke) * len(config["judges"]) == config["total_call_cap"] == 72
    assert config["retries"] == 0 and config["replicates_per_cell"] == 1
    budget = config["budget"]
    assert budget["gpu_count"] * budget["allocation_wall_minutes"] / 60 == budget["gpu_hour_cap"] == 0.5
    assert budget["future_scripted_simulator_booking_calls"] == config["pairs"] * 2 == 16
    assert budget["qwen_output_tokens_cap_all_attempts"] == 36 * config["judges"]["qwen"]["max_output_tokens"] == 18432
    per_attempt = Decimal(budget["jev_context_reserve_tokens_per_attempt"]) * Decimal(str(budget["jev_input_price_usd_per_million"])) / 1000000
    reserve = Decimal(str(budget["jev_reserved_usd_per_attempt"]))
    cap = Decimal(str(budget["jev_client_budget_usd"]))
    assert per_attempt <= reserve and 36 * reserve <= cap
    for key in ("new_model_calls", "new_simulator_executions", "new_gpu_jobs", "new_paid_API_usage", "human_reviews_completed_in_this_update", "new_timing_records_materialized"):
        assert ready[key] == 0

    frozen = {}
    for directory in ("jev_monitor_2x2_2026-11-11", "jev_tgf_mainline_2026-11-12"):
        manifest = ROOT / "project" / directory / "manifest.json"
        data = read(manifest)
        for name, expected in data["files"].items():
            assert digest(ROOT / name) == expected, "Frozen file changed: " + name
        frozen[directory] = {"files": len(data["files"]), "manifest_sha256": digest(manifest)}

    files = [ROOT / "README.md", ROOT / "project/README.md"]
    files += [HERE / p for p in ("README.md", "RESEARCH_DIRECTION.md", "TEAM_HANDOFF.md", "NEXT_STEPS.md", "IMPLICATIONS.md", "verify_preparation.py")]
    files += sorted(p for p in (HERE / "source_review").iterdir() if p.is_file())
    files += sorted(p for p in TIMING.iterdir() if p.is_file())
    links, json_files, python_files = 0, 0, 0
    for path in files:
        content = path.read_text()
        if path.suffix == ".json":
            json.loads(content)
            json_files += 1
        elif path.suffix == ".jsonl":
            for line in content.splitlines():
                json.loads(line)
            json_files += 1
        elif path.suffix == ".py":
            ast.parse(content)
            python_files += 1
        # Validate preparation docs; historical root links were checked at publication.
        if path.suffix == ".md" and path not in (ROOT / "README.md", ROOT / "project/README.md"):
            for target in re.findall(r"\]\(([^)]+)\)", content):
                if re.match(r"[a-z]+:", target) or target.startswith("#"):
                    continue
                target = unquote(target.split("#", 1)[0])
                if target == "PREPARATION_VERIFICATION.json":
                    continue  # This command's stdout is the generated receipt.
                assert (path.parent / target).exists(), f"Broken link: {path}: {target}"
                links += 1
    summary = read(HERE / "source_review/AI_REVIEW_SUMMARY.json")
    assert summary["human_review_completed"] == 0 and summary["label_changes"] == 0
    print(json.dumps({
        "status": "passed", "scope": "Offline source binding and plan consistency; not experiment execution or human validation",
        "source_cases": summary["cases"], "distinct_source_records": summary["distinct_full_records"],
        "human_reviews": 0, "original_label_changes": 0, "model_calls": 0, "simulator_executions": 0,
        "formal_planned_calls": 64, "maximum_planned_calls": 72,
        "timing_design": design,
        "API_capacity_estimate_usd": str(36 * per_attempt), "API_client_cap_usd": str(cap),
        "GPU_hour_cap": 0.5, "source_packet_products_verified": len(products),
        "frozen_manifests_unchanged": frozen,
        "relative_links_checked": links, "json_jsonl_parsed": json_files, "python_files_parsed": python_files,
        "files": {str(p.relative_to(ROOT)): digest(p) for p in files},
        "receipt_excluded_from_own_hash_list": True,
        "limitations": ["AI notes are nonblind and not independent", "Semantic correctness requires actual review, not hash checks", "Run adapter, scorer and runtime budget controls are not implemented or validated by this plan", "New timing data have not been materialized", "No new run is authorized"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
