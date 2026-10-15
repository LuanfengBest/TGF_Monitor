# tgf/ — B1, B2, B3, rule baseline and TGF on MonitorBench trajectories

Put this folder inside `~/MonitorBench/` (next to `main.py`). Run everything from `~/MonitorBench`.

| file | what it does | where it runs |
| --- | --- | --- |
| `tasks.py` | policy shown to the monitor; private friend list used only by the verifier | — |
| `trace.py` | read transcripts, render numbered transcript, build the action ledger, rule baseline | — |
| `build.py` | freeze trajectories into `tgf_runs/<run>/traces.jsonl` with labels | CPU |
| `monitor.py pass1` | B1, B3 (n samples), TGF plan (per-action review + questions), optional B0-oracle | GPU, Qwen3 |
| `answer.py` | the same gpt-oss answers the B2 fixed question and the TGF questions, tools disabled | GPU, gpt-oss |
| `monitor.py judge` | B2 judge and TGF judge | GPU, Qwen3 |
| `metrics.py` | AUROC, TPR/TNR, g-mean², paired bootstrap vs B1, tokens | CPU |
| `gen_traces.sbatch` | MonitorBench agent + eval, then `build` | GPU job |
| `run_pilot.sbatch` | pass1 → answer → judge → metrics | GPU job |

Outputs in `tgf_runs/<run>/`: `traces.jsonl`, `b1.jsonl`, `b3.jsonl`, `tgf_plan.jsonl`, `b0_oracle.jsonl`, `answers.jsonl`, `b2.jsonl`, `tgf.jsonl`, `metrics.md`.

Test the plumbing on CPU without models:

```bash
python -m tgf.build --results results/gpt-oss-20b/dual_objectives.agent.malicious --out tgf_runs/dry
python -m tgf.monitor pass1 --run tgf_runs/dry --dry-run
python -m tgf.answer --run tgf_runs/dry --dry-run
python -m tgf.monitor judge --run tgf_runs/dry --dry-run
python -m tgf.metrics --run tgf_runs/dry
```

Knobs: `--k` (max TGF questions), `--b3-n` (B3 samples), `--scope all|cot|action`,
`--model Qwen/Qwen3-8B` for a smaller monitor, `--b2-samples` in `answer.py` for the count-matched B2.
