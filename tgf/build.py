"""Stage 0 (CPU): freeze trajectories into one file with labels, ledger and the rule baseline.

python -m tgf.build \
    --results results/gpt-oss-20b/dual_objectives.agent.malicious \
    --task-folder bank_transfer_2 --out tgf_runs/pilot
"""

import argparse
import json
from collections import Counter
from pathlib import Path

from .tasks import VERIFIERS
from .trace import (build_ledger, build_steps, has_system_prompt, iter_trajectory_files,
                    normalize_conversation, rule_baseline_score, user_query_of)
from .io import write_jsonl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True, help="results/<agent>/<task> directory from MonitorBench")
    ap.add_argument("--task-folder", default="bank_transfer_2")
    ap.add_argument("--stress", default="", help="comma list to keep, e.g. standard,no_side_task (default: all)")
    ap.add_argument("--n", type=int, default=None, help="only read temp_output_n=<n> (the rollout_number you ran)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    stresses = {s.strip() for s in args.stress.split(",") if s.strip()} or None
    verify = VERIFIERS[args.task_folder]
    rows = []
    for path, stress, idx in iter_trajectory_files(args.results, args.task_folder, stresses, args.n):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        conv = normalize_conversation(data.get("conversation") or data.get("conversations") or [])
        if not conv:
            print(f"[skip] {path}: empty conversation")
            continue
        steps = build_steps(conv)
        uq = user_query_of(conv)
        ledger = build_ledger(steps, uq)
        v = verify(ledger)
        empty_turns = sum(1 for s in steps if not s["cot"] and not s["text"] and not s["calls"])
        n_calls = sum(len(s["calls"]) for s in steps)
        ended = any(c["function"] == "end_task" for s in steps for c in s["calls"])
        rows.append({
            "id": f"{args.task_folder}/{stress}_{idx}",
            "file": str(path),
            "task_folder": args.task_folder,
            "stress": stress,
            "idx": idx,
            "user_query": uq,
            "secondary_task": data.get("side_task_description", ""),
            "has_system_prompt": has_system_prompt(conv),
            "conversation": conv,
            "label": v["label"],
            "unauthorized": v["unauthorized"],
            "attacker_total": v["attacker_total"],
            "overpaid": v["overpaid"],
            "side_task_pass": data.get("side_task_pass"),
            "main_task_pass": data.get("main_task_pass"),
            "main_task_score": data.get("main_task_score"),
            "ledger": ledger,
            "rule_score": rule_baseline_score(ledger),
            "n_steps": len(steps),
            "n_tool_calls": n_calls,
            "empty_turns": empty_turns,
            "ended_with_end_task": ended,
        })

    if not rows:
        raise SystemExit("No trajectories found. Check --results and --task-folder.")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    write_jsonl(rows, out / "traces.jsonl")

    # ---- summary ----
    print(f"\nwrote {len(rows)} trajectories -> {out/'traces.jsonl'}\n")
    hdr = f"{'id':<34}{'label':>6}{'side_pass':>10}{'main':>6}{'steps':>7}{'calls':>7}{'empty':>7}{'end':>5}{'rule':>6}  unauthorized"
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        ua = ", ".join(f"s{u['step']}:{u['recipient']}:{u['amount']}" for u in r["unauthorized"])[:60]
        print(f"{r['id']:<34}{r['label']:>6}{str(r['side_task_pass']):>10}{str(r['main_task_pass']):>6}"
              f"{r['n_steps']:>7}{r['n_tool_calls']:>7}{r['empty_turns']:>7}{('y' if r['ended_with_end_task'] else 'n'):>5}"
              f"{int(r['rule_score']):>6}  {ua}")
    by = Counter((r["stress"], r["label"]) for r in rows)
    print("\nlabel counts by stress:", dict(sorted(by.items())))
    if not all(r["has_system_prompt"] for r in rows):
        print("[warn] some transcripts have no system message; follow-up answers will lack the agent's original instructions")
    if any(r["empty_turns"] for r in rows):
        print("[warn] some trajectories contain empty turns (likely max_tokens truncation)")


if __name__ == "__main__":
    main()
