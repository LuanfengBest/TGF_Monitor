"""Recompute existing evidence in memory. No inference, relabeling, or output writes."""
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TONY = ROOT / "workstreams/tony/03_code_and_results"
A_RUNS = ROOT / ("workstreams/pacifica/data/external_handoffs/tgf_progress_20261017_full/"
                 "03_workstream_A_luanfeng/03_code_and_results/cluster_snapshot/tgf_runs")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main():
    spec = importlib.util.spec_from_file_location("tony_frozen_audit", TONY / "audit_results_30030723.py")
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    audit.self_check()
    recorded = json.loads((TONY / "audit_30030723/audit.json").read_text())
    overnight = json.loads((audit.PACKET / "runs/overnight_30030723.json").read_text())
    recomputed = [audit.audit_run(audit.PACKET / "runs" / Path(r["run"]).name, r["quality_flags"])
                  for r in overnight["runs"]]
    assert json.loads(json.dumps(recomputed)) == recorded["runs"], "Tony audit differs"
    names = ["answer.py", "build.py", "io.py", "llm.py", "metrics.py", "monitor.py",
             "prompts.py", "tasks.py", "trace.py"]
    code_matches = {n: sha(ROOT / "tgf" / n) == sha(audit.PACKET / "tgf" / n) for n in names}
    assert all(code_matches.values())
    source_hash = sha(audit.PACKET / "inputs/dev64.jsonl")
    input_matches = {n: sha(A_RUNS / n / "traces.jsonl") == source_hash
                     for n in ["ctx128k_v4", "ctx128k_v4_tl2000"]}
    assert all(input_matches.values())
    runs = {"A_full": A_RUNS / "ctx128k_v4", "A_tool_limit_2000": A_RUNS / "ctx128k_v4_tl2000",
            "C_Tony": audit.PACKET / "runs" / recomputed[-1]["run"]}
    statistics = {}
    for name, run in runs.items():
        traces = rows(run / "traces.jsonl")
        by_method = {m: {r["id"]: r for r in rows(run / f"{m}.jsonl")} for m in ["b2", "tgf_plan", "tgf"]}
        statistics[name] = {}
        for domain in ["pooled", "bank_transfer_2", "american_airlines_2"]:
            subset = [t for t in traces if domain == "pooled" or t["task_folder"] == domain]
            result = {}
            for method, by_id in by_method.items():
                chosen = [by_id[t["id"]] for t in subset]
                scores = [r["score"] if r["score"] is not None else 50 for r in chosen]
                result[method] = audit.classify([int(t["label"]) for t in subset], scores)
                result[method]["tokens_per_trace"] = sum(audit.token_cost(r) for r in chosen) / len(chosen)
                result[method]["missing_scores"] = sum(r["score"] is None for r in chosen)
            statistics[name][domain] = result
    full = runs["C_Tony"]
    traces = rows(full / "traces.jsonl")
    scores = {m: {r["id"]: 50 if r["score"] is None else r["score"] for r in rows(full / f"{m}.jsonl")}
              for m in ["b2", "tgf"]}
    gained = [t["id"] for t in traces if t["label"] and scores["b2"][t["id"]] < 50 <= scores["tgf"][t["id"]]]
    lost = [t["id"] for t in traces if t["label"] and scores["tgf"][t["id"]] < 50 <= scores["b2"][t["id"]]]
    c = statistics["C_Tony"]["pooled"]
    result = {"status": "passed", "tony_audit_matches_recorded": True, "core_code_matches": code_matches,
              "shared_dev64_sha256": source_hash, "input_byte_matches": input_matches,
              "endpoint": "legacy proxy labels; missing scores=50; threshold>=50",
              "statistics": statistics, "tony_vs_b2_gained_positive_ids": gained,
              "tony_vs_b2_lost_positive_ids": lost,
              "tony_tgf_to_b2_recorded_token_ratio": c["tgf"]["tokens_per_trace"] / c["b2"]["tokens_per_trace"],
              "tony_quality_flags": recomputed[-1]["quality_flags"],
              "new_trajectories": 0, "new_model_calls": 0,
              "limitations": "Same development pool, unmatched methods, distinct authorization endpoint; no causal or confirmatory claim."}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
