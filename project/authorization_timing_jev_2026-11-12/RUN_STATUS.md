# v0.2 execution update — 2026-11-12

**Completed: 64/64 formal judgments are valid, with no repeated requests or replacement data.** Jev is correct on 8/8 pairs under both presentations; Qwen is correct on 4/8 source-card and 5/8 linked-card pairs. The prespecified Jev presentation contrast is zero. [Full results, cases and limitations](RESULTS.md) · [Machine-readable outcome](recovery_01/FINAL_OUTCOME.json) · [Offline verification](verify_completed_recovery.py).

After the initial failure, the user explicitly approved fixing startup and one additional GPU allocation, keeping the same eight pairs and total budget. CPU preflight job `33178469` completed in 56 seconds, verified all 19 model assets and copied/validated 65 compiled subgraphs. GPU job `33178680` completed with exit `0:0` in 136 seconds, within its nine-minute hard limit; all 65 cached subgraphs loaded and all 36 Qwen calls completed. Jev then completed its 32 formal calls locally using the original four smoke responses. All calls have recorded usage; no API key was sent to the cluster or repository.

[Operative amendment](recovery_01/AMENDMENT.json) · [Frozen continuation inputs](recovery_01/manifest.json) · [Startup fixes and offline checks](../../authorization_timing_recovery_v1/README.md)

The original failure is retained below as history. Actual aggregate use is **1,373 GPU seconds / 1,800**, **72 attempts / 72**, and **$0.001716372 estimated Jev API usage / $0.10**. The amendment allowed at most 1,777 GPU seconds and two allocations; both are now consumed as allocation permissions even though elapsed GPU time is below its ceiling. Exactly 16 original simulator bookings remain counted, with zero during recovery. Human reviews remain zero. No third allocation, repeated request or automatic expansion is authorized.

## Initial attempt — preserved history

**Stopped during Qwen startup; no formal judgments and no scientific conclusion.** Job `33137525` ended `FAILED`, exit `1:0`, after 20 minutes 37 seconds on one H200. Jev completed its four interface-smoke requests; Qwen dispatched zero requests. Jev formal evaluation did not run because its prerequisite Qwen stage never completed.

[Failure report and evidence](RUN_REPORT.md) · [Historical recovery proposal](RECOVERY_PLAN.md) · [Original machine-readable outcome](run_01/RUN_OUTCOME.json) · [Saved-run verification](verify_saved_run.py)

The following paragraphs describe the initial attempt before the later amendment; current permissions and completed results are stated above.

The user subsequently instructed “那就开始推进吧”, authorizing this single bounded run. The original plan/config/READINESS artifacts remain unchanged as preparation-time records. The operative authorization and resource caps are in [run_01/config.json](run_01/config.json). That single GPU allocation is now consumed. No second allocation, retry, replacement data or expansion has been launched.

- Materialized 8 pairs / 16 records with exactly 16 genuine scripted simulator bookings; all references resolved, 8 violation / 8 authorized records.
- [Offline checks](run_01/OFFLINE_CHECKS.json) cover public/private separation, unchanged within-pair content, chronological links, independent narrow public-template checks, fixed denominators, and stop-on-first-interface-failure behavior.
- [AI source review](run_01/AI_SOURCE_REVIEW.json) is author-context and nonblind. Human reviews = 0.
- [Frozen manifest](run_01/manifest.json): `5be987887c181dbab8e9b5fb0d48f2fc83efaf237ed1708ff63bacd808154c35`.
- Jev interface smoke passed 4/4. These synthetic fixtures establish interface validity only. Formal coverage is **0/64**.
- GPU use: **1,237 seconds = 0.343611 H200 hours**. Jev: **2,950 input tokens, estimated $0.0001239**. The allocation limit of one is consumed despite unused GPU time in the aggregate 0.5-hour ceiling.

The frozen order was Jev smoke 4 → Qwen smoke 4 + formal 32 → Jev formal 32. Limits remain 72 total attempts, $0.10 Jev client budget and one 30-minute H200 allocation. The stop rule was applied; formal comparisons are not estimable.

Implementation: [authorization_timing_jev_v2](../../authorization_timing_jev_v2/). Qier’s source branch is preserved and attributed at commit `407ed0026685e958ed35342b70d0a50e90da2854`.
