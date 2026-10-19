"""Stage 0 (CPU): freeze trajectories into one file with labels, ledger and the rule baseline.

python -m tgf.build \
    --results results/gpt-oss-120b/dual_objectives.agent.malicious \
    --task-folder bank_transfer_2,american_airlines_2 --n 5 --out tgf_runs/pilot
"""

import argparse
import json
from collections import Counter
from pathlib import Path

from .tasks import VERIFIERS
from .trace import (build_ledger, build_steps, context_overflow, ended_by_agent, has_system_prompt,
                    iter_trajectory_files, normalize_conversation, rule_baseline_score, user_query_of)
from .io import write_jsonl

REFUSAL_MARKERS = ("can't help", "cannot help", "can't comply", "cannot comply", "can't assist",
                   "cannot assist", "i'm sorry, but", "i won't", "unable to help")


def looks_refused(conv, n_calls):
    """A trajectory with zero tool calls did not attempt the task; in practice
    (checked on gpt-oss-20b/120b) these are safety refusals."""
    return n_calls == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True, help="results/<agent>/<task> directory from MonitorBench")
    ap.add_argument("--task-folder", default="bank_transfer_2", help="one or more, comma separated")
    ap.add_argument("--stress", default="", help="comma list to keep, e.g. standard,no_side_task (default: all)")
    ap.add_argument("--n", type=int, default=None, help="only read temp_output_n=<n> (the rollout_number you ran)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--count-overpay", action="store_true",
                    help="bank: also label over-payments to legitimate friends as unauthorized (default: off)")
    args = ap.parse_args()

    stresses = {s.strip() for s in args.stress.split(",") if s.strip()} or None
    folders = [f.strip() for f in args.task_folder.split(",") if f.strip()]
    rows = []
    for folder in folders:
        if folder not in VERIFIERS:
            print(f"[skip] no verifier for {folder} yet")
            continue
        verify = VERIFIERS[folder]
        for path, stress, idx in iter_trajectory_files(args.results, folder, stresses, args.n):
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            conv = normalize_conversation(data.get("conversation") or data.get("conversations") or [])
            if not conv:
                print(f"[skip] {path}: empty conversation")
                continue
            steps = build_steps(conv)
            uq = user_query_of(conv)
            ledger = build_ledger(steps, uq)
            v = verify(ledger, count_overpay=args.count_overpay)
            empty_turns = sum(1 for s in steps if not s["cot"] and not s["text"] and not s["calls"])
            n_calls = sum(len(s["calls"]) for s in steps)
            overflow = context_overflow(conv)
            ended = ended_by_agent(conv)
            rows.append({
                "id": f"{folder}/{stress}_{idx}",
                "file": str(path),
                "task_folder": folder,
                "stress": stress,
                "idx": idx,
                "user_query": uq,
                "secondary_task": data.get("side_task_description", ""),
                "has_system_prompt": has_system_prompt(conv),
                "conversation": conv,
                "label": v["label"],
                "unauthorized": v["unauthorized"],
                "verifier": {k: val for k, val in v.items() if k not in ("label", "unauthorized")},
                "attacker_total": v.get("attacker_total", 0.0),
                "overpaid": v.get("overpaid", {}),
                "side_task_pass": data.get("side_task_pass"),
                "main_task_pass": data.get("main_task_pass"),
                "main_task_score": data.get("main_task_score"),
                "refused": looks_refused(conv, n_calls),
                "ledger": ledger,
                "rule_score": rule_baseline_score(ledger),
                "n_steps": len(steps),
                "n_tool_calls": n_calls,
                "empty_turns": empty_turns,
                "ended_with_end_task": ended,   # the agent itself called end_task
                "context_overflow": overflow,   # run cut off: conversation outgrew max_model_len
            })

    if not rows:
        raise SystemExit("No trajectories found. Check --results, --task-folder and --n.")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    write_jsonl(rows, out / "traces.jsonl")

    # ---- summary ----
    print(f"\nwrote {len(rows)} trajectories -> {out/'traces.jsonl'}\n")
    hdr = (f"{'id':<38}{'label':>6}{'side_pass':>10}{'main':>6}{'steps':>7}{'calls':>7}"
           f"{'refused':>8}{'end':>5}{'ovf':>5}{'rule':>6}  detail")
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        if r["task_folder"] == "american_airlines_2":
            vd = r["verifier"]
            detail = f"AA {vd.get('aa_share')} of {vd.get('n_tickets')} tickets; upgrades={len(vd.get('upgrades', []))}"
        else:
            detail = ", ".join(f"s{u['step']}:{u['recipient']}:{u['amount']}" for u in r["unauthorized"])[:60]
            if r["overpaid"]:
                detail += f" | overpaid: {r['overpaid']}"
        print(f"{r['id']:<38}{r['label']:>6}{str(r['side_task_pass']):>10}{str(r['main_task_pass']):>6}"
              f"{r['n_steps']:>7}{r['n_tool_calls']:>7}{('y' if r['refused'] else 'n'):>8}"
              f"{('y' if r['ended_with_end_task'] else 'n'):>5}{('y' if r['context_overflow'] else 'n'):>5}"
              f"{int(r['rule_score']):>6}  {detail}")
    print("\nlabel counts by (task, stress, label):")
    for k, v in sorted(Counter((r["task_folder"], r["stress"], r["label"]) for r in rows).items()):
        print("  ", k, v)
    print("refusals by (task, stress):",
          dict(sorted(Counter((r["task_folder"], r["stress"]) for r in rows if r["refused"]).items())))
    n_ovf = sum(r["context_overflow"] for r in rows)
    print(f"context overflow: {n_ovf}/{len(rows)}",
          dict(sorted(Counter((r["task_folder"], r["stress"]) for r in rows if r["context_overflow"]).items())))
    if n_ovf:
        print("[warn] overflowed runs were cut off and are not complete trajectories; "
              "raise evaluated_llm.max_model_len (gen_traces.sbatch CTX=...) or exclude them in metrics (--exclude overflow)")
    if not all(r["has_system_prompt"] for r in rows):
        print("[warn] some transcripts have no system message; follow-up answers will lack the agent's original instructions")


if __name__ == "__main__":
    main()
