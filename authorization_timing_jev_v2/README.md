# Authorization timing + Jev v0.2

This separately versioned extension implements the agreed eight-pair design. It adapts Qier's paired-timeline construction and public chronological links from [`407ed002`](https://github.com/LuanfengBest/TGF_Monitor/commit/407ed0026685e958ed35342b70d0a50e90da2854); it does not overwrite or claim to reproduce the original temperature/score experiment.

[Current run status](../project/authorization_timing_jev_2026-11-12/RUN_STATUS.md) · [Prespecified protocol](../project/authorization_timing_jev_2026-11-12/PROTOCOL.md) · [Metrics](../project/authorization_timing_jev_2026-11-12/METRICS.md)

The public renderer adds only nearest-user/call/receipt pointers. It never chooses which permission is applicable. Private pair IDs, expected behavior, labels and execution journals do not enter Judge contexts. `run.py` imports no reference labels or simulator.

The published attempt stopped during Qwen startup with no formal judgments. Jev returned four interface-smoke responses; no Qwen request was dispatched. See the [failure report](../project/authorization_timing_jev_2026-11-12/RUN_REPORT.md). A successful archive verification does not mean the experiment succeeded.

The published run has a one-use simulator-attempt ledger, fixed 72 request slots, exclusive dispatch claims, zero retries, a first-interface-failure stop, pinned versions and token hashes, and one 30-minute H200 allocation. Jev's 20-minute client cap is cumulative across its smoke and formal phases, excluding the intervening GPU wait. All calls use fresh contexts. The four smoke calls per Judge check interface validity, not accuracy; their two hand-authored synthetic fixtures are separate from the genuine formal simulator receipts.

For saved-result reproduction, use the offline verifier; no API key, GPU or model assets are needed:

```sh
python3 -B project/authorization_timing_jev_2026-11-12/verify_saved_run.py
```

The verifier needs only the standard library and repository files. It blocks network connections and child processes, re-parses saved native responses, checks dispatch/result hashes, preserves all planned denominators and reproduces the frozen scorer's output. One local account/balance readiness receipt is withheld from publication; its original hash stays in the input manifest and it is not used for scoring. All scientific inputs and model outputs are shared.

Runtime entrypoints document an already authorized, single-use run, not permission to spend again. Do not rerun `prepare`, `run`, `deploy submit` or `run.sbatch` to reproduce saved statistics. Human review remains zero; AI source review is explicitly author-context and nonblind.
