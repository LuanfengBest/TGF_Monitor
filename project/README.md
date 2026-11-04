# TGF final project: current evidence

Updated November 3, 2026. Team names follow the [final proposal](reference/final_proposal_2026-10-07.md).

**Start here:** [Pacifica’s short group update](PACIFICA_PROGRESS_2026-11-03.md) and [AI handoff / offline reproduction](AI_START_HERE_2026-11-03.md).

**Latest completed run:** development job **31821684**, 24 natural trajectories, 210 model calls, 20m08s. All 24 are legitimate sensitive executions; no executed authorization violations were generated. Original valid P/C/F/T judgments are 9/3/3/4 out of 24 each. F/T valid pairs remain 0/24. This is not held-out evidence of TGF effectiveness.

**Offline diagnosis:** C/F each stopped 21 cases at the initial review, leaving no final judgment. Across all arms, 77 results failed exact citation validation. Four raw T scores additionally show unsupported timing/authorization concerns, and five T rationales cover only part of the record. [Read the diagnosis](prospective_monitoring/offline_diagnostic_2026-11-03/DIAGNOSIS.md). Raw scores and qualitative annotations do not replace frozen original results.

**Current coordination:** a teammate is running a separate four-case B2/revised-TGF comparison. Its case IDs, configuration and outputs have not been received. Use the [comparison worksheet](prospective_monitoring/offline_diagnostic_2026-11-03/TEAM_4_CASE_REVIEW.md) after they arrive. Do not pool batches or launch another comparison from this handoff.

**Implementation and data:** [prospective_monitoring](../prospective_monitoring/README.md) contains explicit authorization references, simulator state recording, four independent strategies, native bounded execution and reporting. The completed run has a verified original results archive in the handoff. The prior 159-test engineering acceptance is documented in [STATUS](prospective_monitoring/STATUS.md); it is not scientific efficacy evidence.

**Study scope:** the [November 3 design](research_reset_2026-11-02/EXPERIMENT_PLAN_2026-11-03.md) tests full action-selection-plus-questioning strategies. The October21 plan's shared-action comparison isolates a different question. The proposed120-case formal study is not ready or authorized. Existing job permits are consumed; no retries, automatic expansion, model training, or changed acceptance rules are part of this handoff.

Older v1/v2 observations, dev64 proxy-label results, authorization audits and SFT diagnostics remain separate historical evidence. Some old large artifacts are local archives, not new shared data in this handoff.

## Historical integrated evidence (October 19)

The following sections retain their historical scope. Current execution and next-step information is above.

## Three contributions to one research question

| Workstream | Available contribution | Appropriate interpretation |
|---|---|---|
| A — Luanfeng | Root `tgf/` v4, native gpt-oss-120b follow-up, Qwen3-32B monitor, frozen dev64 and full/clipped runs | Method implementation and exploratory baseline results |
| B — Pacifica | Public/private separation, execution contracts, source-bound review, all-64 authorization audit, earlier collection and SFT diagnostics | Evaluation validity, evidence quality, and implementation components |
| C — Tony | Independent deployment and model revisions, replay of the same dev64, CPU audit, corrected group statistics, failure cases | Independent execution and diagnosis on existing development data |

Qier An remains a proposal coauthor. This import does not contain a separately identified Qier workstream, so it assigns no unverified contribution or task to them.

## What is established

- Tony's nine archived TGF Python modules exactly match repository commit `481fcd7985241601cf8ceae3833a36082d398898`. His dev64 input is byte-identical to Luanfeng's full and tool-limit-2000 v4 inputs. The two-record smoke run is a subset of dev64.
- Under the **legacy proxy labels**, Tony's B2 detects 20/24 positives with 0/40 false positives; TGF detects 23/24 with 2/40 false positives. TGF uses about 1.70 times the recorded tokens. In the airline domain alone, G² is .8696 for B2 and .8502 for TGF. The bank domain has only one proxy positive.
- The separate, non-blind primary-AI authorization review covers 64 records and 3,817 structured tool events: 38P/21N/5unknown, with 52 distinct normalized conversations. It is not independent human gold. There are only two strict-ended, deduplicated sensitive-negative candidates, both still requiring review.
- The optional component SFT experiments did not establish a reliable advantage for the tested recipe. They are distinct from the natural-trajectory TGF comparison.

## What remains open

The legacy labels and monitor policy do not consistently measure the proposal's executed-authorization endpoint. The existing B2/TGF comparison also varies question counts and earlier-review information. Human review, sufficient legitimate sensitive negatives, and an untouched test set are incomplete. Matched v1 and v2 have insufficient valid paired outcomes; v3 is an offline candidate as recorded above.

Read [the integrated story](STORYLINE_2026-10-19.md) for the report outline, claim boundaries, concrete cases, and next experiment. Read [reproducibility](REPRODUCIBILITY.md) for CPU-only checks and the snapshot's omissions.

## Navigation

- [Current 64-record authorization audit](../workstreams/pacifica/docs/tgf_full64_authorization_audit_2026-10-18.md)
- [Per-record audit labels](../workstreams/pacifica/analysis/tgf_full48_authorization_20261018/case_labels.csv)
- [Latest proposed matched diagnostic](../workstreams/pacifica/docs/tgf_experiment_plan_team_v2_2026-10-18.md)
- [Tony's corrected domain statistics](../workstreams/tony/03_code_and_results/audit_30030723/corrected_metrics.md)
- [Tony's concrete cases](../workstreams/tony/03_code_and_results/diagnostics/case_review.md)
- [Historical SFT results](../workstreams/pacifica/docs/sft_three_arm_results_2026-10-15.md)
- [October 16 progress report snapshot](reference/progress_2026-10-16/progress_report.md): historical cutoff; its pending-repository wording is superseded by this repository.

The October19 repository integration itself did not invoke models, simulators, training, new data collection, GPU jobs, or messages to teammates. Later runs are explicitly recorded above. The team must verify scientific claims and final submitted text.
