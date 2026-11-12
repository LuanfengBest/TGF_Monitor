"""Verify the source-review/preparation package without running any experiment.

Prints a JSON receipt. Requires only the Python standard library and published
files. Does not write, load models, import simulators, or submit processes.
"""
import ast
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
        "authorization_timing_v1", "prospective_monitoring", "tgf_jev_mainline_v1",
    }:
        raise RuntimeError("Experiment runtime imports are not part of preparation verification")


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
    assert ready["execution_authorized"] is False and ready["run_ready"] is False
    assert ready["plan_ready_for_review"] is True and ready["launch_scripts_added"] is False
    assert config["pairs"] == config["grant_pairs"] + config["withdrawal_pairs"] == 8
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
    for key in ("new_model_calls", "new_simulator_executions", "new_gpu_jobs", "new_paid_API_usage", "human_reviews_completed_in_this_update"):
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
