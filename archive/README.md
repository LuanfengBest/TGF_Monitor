# Historical experiments and checkpoints

**Archived in place as of November 16, 2026.** Current scope is in the [repository entry](../README.md). This registry preserves the path from the original follow-up hypothesis to the completed Jev study, including negative results, invalid outputs and launch failures.

## Why scientific files stay at their original paths

Later code imports earlier modules, and frozen manifests bind exact paths and hashes. The Jev runtime uses `prospective_monitoring`, which uses `matched_followup_v2` and `matched_followup_v3`; `evidence_use_v2` also imports `evidence_use_v1`. Renaming or deduplicating them would invalidate experiment packages. Archive status changes navigation and maintenance status, not scientific bytes or imports. Historical launch instructions are not current execution authorization.

## Evidence registry

| Stage | Preserved location | Status and reading rule |
| --- | --- | --- |
| Original TGF, dev64 and component SFT | [workstreams](../workstreams/), [October story](../project/STORYLINE_2026-10-19.md), [proposal](../project/reference/final_proposal_2026-10-07.md) | Exploratory/historical; proxy labels and SFT endpoints differ from current authorization labels |
| Matched follow-up iterations | [v1 package](../project/matched_followup_v1/), [source v1](../matched_followup/), [v2](../matched_followup_v2/), [v3](../matched_followup_v3/) | Earlier protocols and dependencies; insufficient valid pairs are not success evidence |
| November 3 prospective run | [diagnosis](../project/prospective_monitoring/offline_diagnostic_2026-11-03/DIAGNOSIS.md), [source](../prospective_monitoring/) | 24 authorized records, no violations, zero jointly valid F/T pairs; citation-validation failures retained |
| Evaluation correction | [November 5 alignment](../project/evaluation_alignment_2026-11-05/README.md) | Legacy null-score imputation corrected in a separate analysis; originals unchanged |
| Collection and four-arm development | [collection](../project/new_data_collection_2026-11-05/REPORT_2026-11-06.md), [airline comparison](../project/airline_monitor_comparison_2026-11-06/REPORT_2026-11-06.md) | 48 collected records; 24-airline comparison did not show targeted benefit |
| Fixed-action and evidence diagnostics | [anchored questions](../project/anchored_question_diagnostic_2026-11-06/), [evidence use](../project/evidence_use_diagnostic_2026-11-07/), [claim probe](../project/evidence_claim_probe_2026-11-07/), [source audit](../project/evidence_content_audit_2026-11-07/) | Distinct diagnostic endpoints; labels, citations and output availability remain separate |
| November 7 closing study | [historical report](../project/closeout_2026-11-07/FINAL_REPORT.md), [reproduction](../project/closeout_2026-11-07/DATA_AND_CODE.md) | 12 records in 6 pairs, 120 calls; cumulative-evidence improvement below prespecified criterion |
| Jev 2×2 development | [frozen package](../project/jev_monitor_2x2_2026-11-11/), [results](../project/research_update_2026-11-12/reports/development_2x2.md) | Completed development evidence, 60 reused/constructed positions; not independent confirmation |
| Jev mainline | [protocol/results](../project/jev_tgf_mainline_2026-11-12/), [published package](../project/research_update_2026-11-12/README.md) | Completed, 189 eligible trajectories; primary negative result and post-hoc Judge comparison separate |
| Timing diagnostic and recovery | [results](../project/authorization_timing_jev_2026-11-12/RESULTS.md), [failure/recovery](../project/authorization_timing_jev_2026-11-12/RUN_STATUS.md) | Completed 8 pairs, 72 total calls, 1,373 GPU seconds including failure; no additional run |

The last three batches supply the current report; “archived” means execution is closed, not that evidence is excluded. No batch is pooled with another to inflate sample size. The [offline entry](../REPRODUCE.md) reproduces saved analyses without executing models or the simulator.

## Superseded narrative checkpoints

Relative destinations below are pinned to the source commit so links refer to what was known then. Original byte-for-byte files remain in Git history at `e8086cdd568dfa9162cedc9fc2da0535c47176b0`.

- [Old root overview](checkpoints/2026-11-13/ROOT_README.md)
- [Old project progress index](checkpoints/2026-11-13/PROJECT_INDEX.md)
- [Old team handoff](checkpoints/2026-11-13/TEAM_HANDOFF.md)
- [Old next-work inventory](checkpoints/2026-11-13/NEXT_STEPS.md)
- [Research-direction decision](checkpoints/2026-11-13/RESEARCH_DIRECTION.md)
- [Earlier implications explanation](checkpoints/2026-11-13/IMPLICATIONS.md)

Current presentation work is tracked in the [session handoff](../project/SESSION_HANDOFF.md). AGV's separate branch and future-ablation status are in [optional extensions](../extensions/README.md).
