# Next-work inventory — report and presentation integrated

The [November 13 final package](../final_report_2026-11-13/README.md) integrates the complete project narrative, contributions, implications and limitations. The existing presentation was updated in place; the older manuscript and all frozen scientific files remain unchanged. No experiment or expansion was initiated. The original primary negative results and the post-hoc status of the Judge comparison remain explicit.

The authorized v0.2 diagnostic is complete: 64/64 valid formal judgments on the same eight pairs, with Jev 8→8 and Qwen 4→5 correct pairs under source→linked presentation. The primary Jev contrast is zero; the Qwen difference is secondary and descriptive. After the first startup failure, the user explicitly approved one additional allocation; both together used 1,373 / 1,800 GPU seconds. All 72 allowed attempts are consumed. [Results](../authorization_timing_jev_2026-11-12/RESULTS.md) · [Authorization and accounting](../authorization_timing_jev_2026-11-12/RUN_STATUS.md). No third allocation, repeated judgment, replacement data or automatic expansion is authorized.

## Completed evidence and preparation

| Work | Artifact | Interpretation |
| --- | --- | --- |
| Existing source review | [32-case AI review](source_review/README.md), 27 distinct records and empty human forms | Nonblind author-context AI work; human review = 0 |
| Exact v0.2 design | [Protocol](../authorization_timing_jev_2026-11-12/PROTOCOL.md), [pair blueprint](../authorization_timing_jev_2026-11-12/PAIR_SPEC.json), [metrics](../authorization_timing_jev_2026-11-12/METRICS.md) | 4 basic + 2 intervening + 2 irrelevant-permission pairs; fixed eight-pair primary denominator |
| Separate implementation | [Versioned code](../../authorization_timing_jev_v2/) | Public-only links, fixed prompts, failure accounting and one-use budget controls |
| New data and execution references | [16 records](../authorization_timing_jev_2026-11-12/run_01/records.json), [private references](../authorization_timing_jev_2026-11-12/run_01/references_PRIVATE.json) | Exactly 16 genuine simulator bookings; 8 positive / 8 negative; only amendment order differs within a pair |
| Offline checks and source inspection | [Checks](../authorization_timing_jev_2026-11-12/run_01/OFFLINE_CHECKS.json), [AI review](../authorization_timing_jev_2026-11-12/run_01/AI_SOURCE_REVIEW.json) | Reference and public-template checks agree; no claim of independent human gold |
| Immutable run inputs | [Manifest](../authorization_timing_jev_2026-11-12/run_01/manifest.json), [operative config](../authorization_timing_jev_2026-11-12/run_01/config.json) | User authorization recorded; original API/GPU/call caps unchanged |
| Bounded startup recovery | [Amendment](../authorization_timing_jev_2026-11-12/recovery_01/AMENDMENT.json), [code](../../authorization_timing_recovery_v1/), [allocation receipts](../authorization_timing_jev_2026-11-12/recovery_01/cluster/accounting_final.json) | CPU asset verification, copied warm cache, unchanged scientific inputs, first failure preserved |
| Complete timing diagnostic | [Report](../authorization_timing_jev_2026-11-12/RESULTS.md), [raw/parsed outputs](../authorization_timing_jev_2026-11-12/recovery_01/results/), [pair details](../authorization_timing_jev_2026-11-12/recovery_01/DETAILS.json) | Jev ceiling/no linked gain; one Qwen improvement; specific timing/scope failures |
| Saved-result reproduction | [Verifier](../authorization_timing_jev_2026-11-12/verify_completed_recovery.py), [clean verification](../authorization_timing_jev_2026-11-12/recovery_01/VERIFICATION.json) | Standard-library CPU analysis; no new model/simulator calls |

## Remaining work in order

1. **Actual human source review.** People can complete the supplied blank forms and record whether they saw prior labels. Review the timing references and the pair08 scope/order interpretation as well as the prior mainline construction warnings. This is proposed work, not an accepted assignment; human review is still zero. Do not describe the completed AI work as human validation.
2. **Review the completed final report and slides.** The [integrated report](../final_report_2026-11-13/FINAL_REPORT.md), [slides](../final_report_2026-11-13/SLIDES.md) and [Chinese notes](../final_report_2026-11-13/SPEAKER_NOTES_ZH.md) retain the original TGF negative result, bounded post-hoc Judge comparison, source audit, Tony's citation-capacity audit and completed timing diagnostic as distinct evidence. Review the narrative and rehearse it; no new inference is required.
3. **Team review of the story and contributions.** Preserve Qier's timeline design, Tony's evidence work and the original implementation attribution. Avoid claims that the scores reveal internal reasoning or that this small test certifies production safety. Check the course's final-writing and AI-disclosure requirements before submission. This repository update is not a course submission.
4. **Decide on any future experiment separately, only if needed.** A new proposal should target a specific unresolved question, such as whether a documented timing/scope failure recurs on independently chosen tasks, or whether an escalation rule improves review quality. Repetition, calibration and external validity are separate endpoints requiring new protocols and authorization. Do not enlarge this frozen batch merely to obtain a positive result. The immediate priority is review and synthesis, not more calls.

## Keep these boundaries visible

- Preserve frozen labels, inputs, hypotheses and full-denominator negative results.
- Do not pool scripted diagnostic pairs and the 189 eligible Actor trajectories.
- Do not treat F truncation differences as improvements in valid-answer content.
- Do not equate stable labels, high confidence, semantic citation support and correctness.
- Never use Jev to create the reference labels for its own comparison.
- The task is post-execution authorization auditing; production prevention, human time savings, repeatability and calibration remain untested.
