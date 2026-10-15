"""Agent answers follow-up questions (GPU, the same gpt-oss that produced the traces).

Each question is appended on its own to the frozen trajectory (tools disabled);
the trajectory itself is never modified. B2 = the fixed SHADE-Arena question,
TGF = the questions written in `tgf.monitor pass1`.

python -m tgf.answer --run tgf_runs/pilot --model openai/gpt-oss-20b
"""

import argparse
from pathlib import Path

from . import prompts as P
from .io import read_jsonl, write_jsonl
from .llm import HarmonyAgent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--model", default="openai/gpt-oss-20b")
    ap.add_argument("--b2-samples", type=int, default=1,
                    help="how many times to ask the fixed question (count-matched B2 = TGF's k)")
    ap.add_argument("--max-new", type=int, default=4096)
    ap.add_argument("--max-model-len", type=int, default=65536)
    ap.add_argument("--gpu-util", type=float, default=0.90)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    run = Path(args.run)
    traces = read_jsonl(run / "traces.jsonl")
    plans = {p["id"]: p for p in read_jsonl(run / "tgf_plan.jsonl")}
    if not plans:
        print("[warn] tgf_plan.jsonl missing: only B2 questions will be asked")

    jobs = []  # (row meta, conversation, question text)
    for tr in traces:
        for i in range(args.b2_samples):
            jobs.append(({"id": tr["id"], "method": "b2", "q_idx": i, "step": None, "question": P.FIXED_QUESTION},
                         tr["conversation"], P.FIXED_QUESTION))
        for i, q in enumerate(plans.get(tr["id"], {}).get("questions", [])):
            text = str(q["question"]).strip()
            jobs.append(({"id": tr["id"], "method": "tgf", "q_idx": i, "step": q.get("step"), "question": text},
                         tr["conversation"], text + P.FOLLOWUP_SUFFIX))

    agent = HarmonyAgent(args.model, args.max_model_len, args.gpu_util, dry_run=args.dry_run)
    try:
        outs = agent.answer([(c, q) for _, c, q in jobs], max_tokens=args.max_new, seed=args.seed)
    finally:
        agent.close()
    rows = [{**meta, **o} for (meta, _, _), o in zip(jobs, outs)]
    write_jsonl(rows, run / "answers.jsonl")
    print(f"[answer] {len(rows)} answers "
          f"(b2={sum(r['method']=='b2' for r in rows)}, tgf={sum(r['method']=='tgf' for r in rows)}); "
          f"skipped for length: {sum(r['skipped'] for r in rows)}; tried tool calls: {sum(r['tried_tool_call'] for r in rows)}")


if __name__ == "__main__":
    main()
