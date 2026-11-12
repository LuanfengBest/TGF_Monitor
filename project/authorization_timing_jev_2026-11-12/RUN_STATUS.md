# v0.2 execution update — 2026-11-12

**Stopped during Qwen startup; no formal judgments and no scientific conclusion.** Job `33137525` ended `FAILED`, exit `1:0`, after 20 minutes 37 seconds on one H200. Jev completed its four interface-smoke requests; Qwen dispatched zero requests. Jev formal evaluation did not run because its prerequisite Qwen stage never completed.

[Failure report and evidence](RUN_REPORT.md) · [Unexecuted recovery proposal](RECOVERY_PLAN.md) · [Machine-readable outcome](run_01/RUN_OUTCOME.json) · [Saved-run verification](verify_saved_run.py)

The user subsequently instructed “那就开始推进吧”, authorizing this single bounded run. The original plan/config/READINESS artifacts remain unchanged as preparation-time records. The operative authorization and resource caps are in [run_01/config.json](run_01/config.json). That single GPU allocation is now consumed. No second allocation, retry, replacement data or expansion has been launched.

- Materialized 8 pairs / 16 records with exactly 16 genuine scripted simulator bookings; all references resolved, 8 violation / 8 authorized records.
- [Offline checks](run_01/OFFLINE_CHECKS.json) cover public/private separation, unchanged within-pair content, chronological links, independent narrow public-template checks, fixed denominators, and stop-on-first-interface-failure behavior.
- [AI source review](run_01/AI_SOURCE_REVIEW.json) is author-context and nonblind. Human reviews = 0.
- [Frozen manifest](run_01/manifest.json): `5be987887c181dbab8e9b5fb0d48f2fc83efaf237ed1708ff63bacd808154c35`.
- Jev interface smoke passed 4/4. These synthetic fixtures establish interface validity only. Formal coverage is **0/64**.
- GPU use: **1,237 seconds = 0.343611 H200 hours**. Jev: **2,950 input tokens, estimated $0.0001239**. The allocation limit of one is consumed despite unused GPU time in the aggregate 0.5-hour ceiling.

The frozen order was Jev smoke 4 → Qwen smoke 4 + formal 32 → Jev formal 32. Limits remain 72 total attempts, $0.10 Jev client budget and one 30-minute H200 allocation. The stop rule was applied; formal comparisons are not estimable.

Implementation: [authorization_timing_jev_v2](../../authorization_timing_jev_v2/). Qier’s source branch is preserved and attributed at commit `407ed0026685e958ed35342b70d0a50e90da2854`.
