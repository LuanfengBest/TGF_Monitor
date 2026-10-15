"""Monitor stages (GPU, Qwen3).

pass1: B1 + B3 (n samples of the same passive prompt) + TGF plan (per-action review + questions)
       [+ B0-oracle with --oracle]
judge: B2 judge + TGF judge, after tgf.answer has produced the agent's answers

python -m tgf.monitor pass1 --run tgf_runs/pilot --model Qwen/Qwen3-32B
python -m tgf.monitor judge --run tgf_runs/pilot --model Qwen/Qwen3-32B
"""

import argparse
from pathlib import Path

from . import prompts as P
from .io import read_jsonl, write_jsonl
from .llm import ChatModel, parse_json_obj, parse_score
from .tasks import POLICY_TEXT
from .trace import build_steps, render_ledger, render_transcript

TOOL_LIMITS = (2000, 800, 300, 120)


def fit_transcript(model, steps, scope, other_text, max_new):
    """Render the transcript, shrinking tool outputs (then cutting the middle)
    until prompt + generation fits in the context window."""
    budget = model.max_len - max_new - 256
    other = model.count(other_text)
    for lim in TOOL_LIMITS:
        t = render_transcript(steps, scope=scope, tool_limit=lim)
        if other + model.count(t) <= budget:
            return t, {"tool_limit": lim, "middle_cut": False}
    t = render_transcript(steps, scope=scope, tool_limit=TOOL_LIMITS[-1], cot_limit=1500)
    avail_chars = max(2000, int((budget - other) * 3.2))
    if len(t) > avail_chars:
        half = avail_chars // 2
        t = t[:half] + "\n\n...[middle of transcript omitted for length]...\n\n" + t[-half:]
    return t, {"tool_limit": TOOL_LIMITS[-1], "middle_cut": True}


def header_kwargs(tr):
    return {"user_query": tr["user_query"], "policy": POLICY_TEXT[tr["task_folder"]]}


def run_pass1(args, traces, model):
    run = Path(args.run)
    b1_prompts, plan_prompts, oracle_prompts, meta = [], [], [], []
    for tr in traces:
        steps = build_steps(tr["conversation"])
        hk = header_kwargs(tr)
        t, fit = fit_transcript(model, steps, args.scope, P.B1.format(**hk, oracle="", transcript=""), args.max_new)
        b1_prompts.append(P.B1.format(**hk, oracle="", transcript=t))
        ledger_txt = render_ledger(tr["ledger"])
        t2, fit2 = fit_transcript(model, steps, args.scope,
                                  P.TGF_PLAN.format(**hk, transcript="", ledger=ledger_txt, k=args.k), args.max_new)
        plan_prompts.append(P.TGF_PLAN.format(**hk, transcript=t2, ledger=ledger_txt, k=args.k))
        if args.oracle:
            ob = P.ORACLE_BLOCK.format(secondary_task=tr.get("secondary_task") or "(not available)")
            t3, _ = fit_transcript(model, steps, args.scope, P.B1.format(**hk, oracle=ob, transcript=""), args.max_new)
            oracle_prompts.append(P.B1.format(**hk, oracle=ob, transcript=t3))
        meta.append({"fit": fit, "fit_plan": fit2})

    # B1 / B3: one call with n samples; B1 = sample 0, B3 = mean of all n
    outs = model.generate(b1_prompts, n=args.b3_n, max_tokens=args.max_new, seed=args.seed,
                          fake=lambda t: "<score>70</score>")
    b1, b3 = [], []
    for tr, o, m in zip(traces, outs, meta):
        scores = [parse_score(x["text"]) for x in o]
        valid = [s for s in scores if s is not None]
        b1.append({"id": tr["id"], "score": scores[0], "raw": o[0]["text"],
                   "prompt_tokens": o[0]["prompt_tokens"], "completion_tokens": o[0]["completion_tokens"], **m["fit"]})
        b3.append({"id": tr["id"], "score": (sum(valid) / len(valid)) if valid else None, "samples": scores,
                   "prompt_tokens": sum(x["prompt_tokens"] for x in o),
                   "completion_tokens": sum(x["completion_tokens"] for x in o), **m["fit"]})
    write_jsonl(b1, run / "b1.jsonl")
    write_jsonl(b3, run / "b3.jsonl")
    print(f"[pass1] B1/B3 done ({len(b1)} traces, n={args.b3_n})")

    fake_plan = lambda t: ('{"actions": [{"step": 1, "tool": "send_money", "verdict": "unclear", "reason": "dry"}],'
                           ' "questions": [{"step": 1, "question": "Where did this recipient come from?"}],'
                           ' "preliminary_score": 60}')
    outs = model.generate(plan_prompts, n=1, max_tokens=args.max_new, seed=args.seed, fake=fake_plan)
    plans = []
    for tr, o, m in zip(traces, outs, meta):
        obj = parse_json_obj(o[0]["text"])
        ok = isinstance(obj, dict)
        qs = (obj.get("questions") or []) if ok else []
        qs = [q for q in qs if isinstance(q, dict) and q.get("question")][: args.k]
        pre = obj.get("preliminary_score") if ok else None
        try:
            pre = max(0.0, min(100.0, float(pre))) if pre is not None else None
        except (TypeError, ValueError):
            pre = None
        plans.append({"id": tr["id"], "parse_ok": ok, "actions": (obj.get("actions") or []) if ok else [],
                      "questions": qs, "score": pre, "raw": o[0]["text"],
                      "prompt_tokens": o[0]["prompt_tokens"], "completion_tokens": o[0]["completion_tokens"],
                      **m["fit_plan"]})
    write_jsonl(plans, run / "tgf_plan.jsonl")
    nq = sum(len(p["questions"]) for p in plans)
    print(f"[pass1] TGF plan done: {nq} questions over {len(plans)} traces; "
          f"parse failures: {sum(not p['parse_ok'] for p in plans)}")

    if args.oracle:
        outs = model.generate(oracle_prompts, n=1, max_tokens=args.max_new, seed=args.seed)
        write_jsonl([{"id": tr["id"], "score": parse_score(o[0]["text"]), "raw": o[0]["text"],
                      "prompt_tokens": o[0]["prompt_tokens"], "completion_tokens": o[0]["completion_tokens"]}
                     for tr, o in zip(traces, outs)], run / "b0_oracle.jsonl")
        print("[pass1] B0-oracle done")


def run_judge(args, traces, model):
    run = Path(args.run)
    answers = read_jsonl(run / "answers.jsonl")
    plans = {p["id"]: p for p in read_jsonl(run / "tgf_plan.jsonl")}
    if not answers:
        raise SystemExit("answers.jsonl missing: run `python -m tgf.answer` first")
    by = {}
    for a in answers:
        by.setdefault((a["id"], a["method"]), []).append(a)

    jobs = []  # (method, trace, prompt, n_followup_tokens)
    for tr in traces:
        steps = build_steps(tr["conversation"])
        hk = header_kwargs(tr)
        for method in ("b2", "tgf"):
            qa = sorted(by.get((tr["id"], method), []), key=lambda a: a["q_idx"])
            qa = [a for a in qa if not a.get("skipped")]
            extra = ""
            if method == "tgf":
                extra = P.TGF_EXTRA.format(verdicts=P.verdict_block(plans.get(tr["id"], {}).get("actions", [])))
            qa_txt = P.qa_block(qa)
            t, fit = fit_transcript(model, steps, args.scope, P.JUDGE.format(**hk, transcript="", extra=extra, qa=qa_txt),
                                    args.max_new)
            follow_tokens = sum(a["prompt_tokens"] + a["completion_tokens"] for a in qa)
            jobs.append((method, tr, P.JUDGE.format(**hk, transcript=t, extra=extra, qa=qa_txt), follow_tokens, fit, len(qa)))

    outs = model.generate([j[2] for j in jobs], n=1, max_tokens=args.max_new, seed=args.seed,
                          fake=lambda t: "<score>80</score>")
    res = {"b2": [], "tgf": []}
    for (method, tr, _, ftok, fit, nq), o in zip(jobs, outs):
        pt, ct = o[0]["prompt_tokens"], o[0]["completion_tokens"]
        if method == "tgf":  # add the plan pass to TGF's cost
            p = plans.get(tr["id"], {})
            pt += p.get("prompt_tokens", 0)
            ct += p.get("completion_tokens", 0)
        res[method].append({"id": tr["id"], "score": parse_score(o[0]["text"]), "raw": o[0]["text"],
                            "n_questions": nq, "prompt_tokens": pt, "completion_tokens": ct,
                            "followup_tokens": ftok, **fit})
    write_jsonl(res["b2"], run / "b2.jsonl")
    write_jsonl(res["tgf"], run / "tgf.jsonl")
    print(f"[judge] B2 and TGF judged ({len(traces)} traces)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["pass1", "judge"])
    ap.add_argument("--run", required=True)
    ap.add_argument("--model", default="Qwen/Qwen3-32B")
    ap.add_argument("--scope", default="all", choices=["all", "cot", "action"])
    ap.add_argument("--k", type=int, default=3, help="max TGF questions per trace")
    ap.add_argument("--b3-n", type=int, default=3, help="samples for B3 (B1 = first sample)")
    ap.add_argument("--oracle", action="store_true", help="also run B0-oracle (monitor told the hidden objective)")
    ap.add_argument("--max-new", type=int, default=8192)
    ap.add_argument("--max-model-len", type=int, default=32768)
    ap.add_argument("--rope-factor", type=float, default=2.0)
    ap.add_argument("--gpu-util", type=float, default=0.90)
    ap.add_argument("--tp", type=int, default=1)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--dry-run", action="store_true", help="no GPU: fake model outputs, to test the plumbing")
    args = ap.parse_args()

    traces = read_jsonl(Path(args.run) / "traces.jsonl")
    if not traces:
        raise SystemExit("traces.jsonl missing: run `python -m tgf.build` first")
    model = ChatModel(args.model, args.max_model_len, args.rope_factor, args.gpu_util, args.tp, dry_run=args.dry_run)
    try:
        (run_pass1 if args.stage == "pass1" else run_judge)(args, traces, model)
    finally:
        model.close()


if __name__ == "__main__":
    main()
