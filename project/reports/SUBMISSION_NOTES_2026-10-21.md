# October 21 progress report: submission and evidence notes

Prepared October 19, 2026, with evidence through that date. This is the updated course report; it has not been submitted to Gradescope or sent to course staff.

## Deliverables

- [One-page English PDF](../../output/pdf/progress_report_2026-10-21.pdf).
- [Editable Markdown source](progress_report_2026-10-21.md).
- [Renderer](build_progress_report.py): `python3 -B project/reports/build_progress_report.py`, with `reportlab` and `pypdf` installed. The renderer checks the one-page limit, names, key numeric text, and active repository hyperlink. After rebuilding, render and inspect the new PDF before using it.
- [Validation receipt](../validation/progress_report_2026-10-21.json).

The original October 16 draft and the imported scientific snapshots remain unchanged. The old report's pending-GitHub wording is superseded. The root README is now a short project introduction; its original MonitorBench section is preserved in [README_MONITORBENCH.md](../../README_MONITORBENCH.md).

## Course requirements checked

The locally supplied course template requires at most one PDF page with title, student names/netIDs, completed work, changes since the proposal, early evidence, remaining work/timeline, and a repository link with a brief README. It gives October 21, 2026, 11:59 p.m. as the Gradescope deadline; one team member submits for the group.

The roster and order match the final proposal: Pacifica Zhang (rz377), Luanfeng Wei (lw856), Qier An (qa24), Tony Zhu (jz965). Workstream descriptions reflect available artifacts; no separate unverified contribution is assigned to Qier.

**Access still requires a team action:** GitHub reports this repository as private. The course template says teams keeping a repository private should email course staff for sharing instructions. The report discloses that staff access is to be arranged. No staff access, email, visibility change, or course submission has been performed here.

## Claim-to-source map

| Report claim | Source / interpretation |
| --- | --- |
| Native v4 implementation; B1/B2/B3/TGF | Root `tgf/`, especially `monitor.py`, `answer.py`, `prompts.py`, `tasks.py`; actor and monitor roles remain distinct |
| Tony reuses the same dev64 and nine modules | [Cross-workstream validation](../validation/workstream_analysis.json): exact input and source hashes; not additional independent data |
| Original-full and Tony G² table | Same validation, `statistics.A_full` and `statistics.C_Tony`; rounded to three decimals; legacy proxy labels and null-to-50 policy retained |
| Tony TP23/24 vs20/24, FP2/40 vs0/40, token ratio 1.70 | Same validation; token ratio 1.7048946, not GPU time or FLOPs |
| Earlier review and unequal question counts | Root v4 prompts and judge; [Tony handoff](../../workstreams/tony/02_technical_handoff/TECHNICAL_HANDOFF.md) |
| Incorrect question premise and unsupported rationale | [Tony cases](../../workstreams/tony/03_code_and_results/diagnostics/case_review.md), with the [integrated interpretation](../STORYLINE_2026-10-19.md); no new causal experiment |
| 64 records, 3817 events, 38P/21N/5unknown, 52 unique, two sensitive-negative candidates | [Full64 audit](../../workstreams/pacifica/docs/tgf_full64_authorization_audit_2026-10-18.md) and [labels](../../workstreams/pacifica/analysis/tgf_full48_authorization_20261018/case_labels.csv); non-blind, non-independent primary AI |
| 23 label reversals and 14 dinner-only positives | Same full64 audit; a different task-constraint endpoint, not an automatic regrading of old model outputs |
| SFT moved from proposed 4B to 32B and showed no reliable benefit | [Final proposal](../reference/final_proposal_2026-10-07.md), [SFT results](../../workstreams/pacifica/docs/sft_three_arm_results_2026-10-15.md); a synthetic component experiment with parsing confounds |
| Eight-case matched diagnostic | [October18 team proposal](../../workstreams/pacifica/docs/tgf_experiment_plan_team_v2_2026-10-18.md); proposed, not run or newly authorized |

## Interpretation and schedule

The headline question is unchanged. The updated report connects implementation, independent execution, and evidence auditing, then motivates the missing matched comparison. It does not pool the earlier 20b collection or component SFT with the 120b dev64 results. The original full and clipped runs are different input settings; only the full run is used in the one-page table.

For the authorization audit, only initial/final simulator snapshots exist. Both sensitive-negative candidates still need review: the bank candidate completed only part of the task, and the airline candidate's actual end step 151 versus configured 150 needs source clarification. Fourteen airline positives depend solely on the dinner headcount boundary. Independent human review and a qualified held-out main study remain incomplete.

October 22-31 review/interface work and the November 30 comparison target are a proposed team schedule, not evidence of assigned tasks or confirmed compute. The eight-case plan remains limited to a possible 72 calls and 60 total H200 minutes, conditional on separate scope/configuration/budget confirmation. It tests question content given shared selection and is too small for a reliable false-alarm estimate. No new experiment was run to produce this report.
