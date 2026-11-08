# TGF handoff: start here

**Current handoff, November 7:** [Final report](closeout_2026-11-07/FINAL_REPORT.md), [repository guide](closeout_2026-11-07/REPOSITORY_GUIDE.md) and [current closeout status](closeout_2026-11-07/STATUS.json). Materials, source audits and the explicitly disclosed independent-context AI blind reference review are complete. No general TGF advantage was established; the final cumulative-summary extension improved only one instance block, below its predeclared criterion. All experiments and monitoring are closed. Do not interpret historical execution instructions below as authorization to submit, retry or expand a run. Human annotation and formal course submission have not been completed.

**2026-11-06 比较与复核已完成：** [订票 24 条四组结果](airline_monitor_comparison_2026-11-06/REPORT_2026-11-06.md)。唯一 GPU 作业 32354336 已完成；P/C/F/T 检出 5/2/6/6 条违规，误报 0/0/0/1 条合法记录，96 个判断均有效。240 次调用、27 分 03 秒（含启动），24 条记录、96 个判断、48 个追问回答已逐条非盲 AI 作者复核；原分数和标签不变。T 相比 F 无新增检出且新增 1 次误报，未通过预设开发筛选线。本轮及定时跟进已结束；不得重复提交或自动开下一轮。旧批次覆盖不足仍保留，不能据此声称正式效果或创新。[最新 STATUS](airline_monitor_comparison_2026-11-06/STATUS.json) 是续接状态依据。以下旧批次内容是历史记录。

**Collection and review complete:** see the [November 6 report](new_data_collection_2026-11-05/REPORT_2026-11-06.md) and `new_data_collection_2026-11-05/STATUS.json`. Actor-only GPU job `32257283` completed at 2026-11-06 00:05:40 EST: 48/48 cases, 155 actor calls, 9m05s including startup. All downloaded hashes passed; current-assistant nonblind AI author review found bank 1 violation / 23 sensitive negatives (1 positive instance block), airline 6 / 18 (6 positive blocks). The exact frozen coverage screen fails bank and therefore the combined batch; airline alone meets development coverage. All failures/unknowns/non-action cases in this batch are zero. Stop here: no new GPU job, permit reuse, retries, replenishment, expansion or monitor evaluation. Review is not blind or independent human evidence. The original [frozen preparation](new_data_preparation_2026-11-05/README.md) and raw artifacts remain unchanged; earlier simulator witnesses remain scripted checks. Detailed decisions, evidence hashes, usage and coverage are in `new_data_collection_2026-11-05/author_review_2026-11-06/`; the scheduled follow-up is paused at delivery (see STATUS.json).

**November 5 offline addendum:** start with the [evaluation alignment package](evaluation_alignment_2026-11-05/README.md). It reuses all 88 existing records without mixing endpoints, corrects legacy missing-score accounting, and supplies source-bound offline scoring and teammate intake requirements. This is completed local preparation, not a new model run or confirmation of a TGF advantage. The authorization-verification branch remains an archived exploration rather than the active expansion plan.

Updated November 3, 2026. This handoff records Pacifica's bounded development run and offline diagnosis. It does not replace the teammate's pending four-case B2/revised-TGF comparison.

## Read in this order

1. [Short team update](PACIFICA_PROGRESS_2026-11-03.md).
2. [Offline diagnosis](prospective_monitoring/offline_diagnostic_2026-11-03/DIAGNOSIS.md) and [24-case matrix](prospective_monitoring/offline_diagnostic_2026-11-03/CASE_MATRIX.md).
3. [Four-case comparison worksheet](prospective_monitoring/offline_diagnostic_2026-11-03/TEAM_4_CASE_REVIEW.md). Its case IDs, outputs and comparability fields are genuinely pending.
4. [Current status](prospective_monitoring/STATUS.md), [experiment design](research_reset_2026-11-02/EXPERIMENT_PLAN_2026-11-03.md), and [implementation](../prospective_monitoring/README.md).

## Facts and interpretation

- Job31821684 completed in20m08s, with24 natural development trajectories and210 calls. All24 were legitimate sensitive executions, with30 covered writes. There are no positive violation cases or held-out test cases.
- P/C/F/T original valid judgments:9/24,3/24,3/24,4/24. F/T valid pairs:0/24. F actually asked3 follow-ups; T asked24. Both asked in3 cases, but no pair passed both final validations.
- C and F each failed21 initial reviews; those42 final judge calls never occurred. Another35 actual judge outputs failed citation validation. Missing output must remain missing.
- All77 failed arm results report `Unbound exact citation`. This does not mean all underlying reasoning was correct: four T raw scores rose to50/25/30/15 with unsupported authorization/timing concerns. Five further T rationales covered only part of the action record. Content annotations are non-blind diagnostic review, not independent human gold.
- The original scores, validation rule, results, raw evidence and failure denominators remain unchanged. Raw score extraction is not repaired efficacy evaluation.
- November3's design compares full selection-plus-questioning strategies. October21's planned matched diagnostic compared wording conditional on the same selected action. Do not silently treat these as the same estimand. Check what the teammate's actual configuration changes before interpreting its four cases.

## Safe offline reproduction

Run from the repository root with Python3.12+ (standard library only). No model downloads, credentials, inference, simulator actions, or Slurm submission are needed for these commands.

The committed results archive is `project/prospective_monitoring/shared_evidence/tgf_prospective_results_31821684.tar.gz` (14,129,265 bytes).
SHA-256: `bcfc9e2a9e382c128c3d8c22c6196b27a898e90d790d66108475143750d17053`.
It preserves all run outputs, GPU log, accounting, configuration, source snapshot and provenance. Model weights, caches, virtual environments and duplicate extracted trees are excluded.

```sh
python3 project/prospective_monitoring/reporting/unpack_shared_evidence.py --out /tmp/tgf-31821684-handoff
python3 project/prospective_monitoring/reporting/pilot_report.py --run /tmp/tgf-31821684-handoff/results_31821684/runs/development_20261103 --output /tmp/tgf-31821684-report
python3 project/prospective_monitoring/reporting/offline_diagnostic.py --run /tmp/tgf-31821684-handoff/results_31821684/runs/development_20261103 --output /tmp/tgf-31821684-diagnostic
```

Use fresh output directories. The unpacker verifies the archive and all1,405 recorded files. The diagnostics verify original run hashes and reproduce original validation before extracting raw scores. Preserve the extracted directory structure: archived protocol equality is checked. Source schema and synthetic tool data are intentionally retained for review; never expose private actor context to monitor prompts.

The qualitative files `judgment_content_review.json` and `data_yield_review.json` are saved review annotations. Deterministic scripts do not regenerate or independently validate their semantic judgments.

For implementation inspection, the full new `prospective_monitoring/` package is included. Only its needed legacy helpers are newly included from `matched_followup_v2` and `matched_followup_v3`; this is not a complete new export of the older v2/v3 experiments. The two public execution decoders and original simulated environments are already in repository history.

## What to do next

Use the worksheet when the teammate supplies the four-case artifacts. Verify the authorization endpoint and original event evidence, then compare questions, answers, score changes, evidence support and actual cost. Do not assume shared cases imply shared selection, judge inputs or budget. Keep that batch separate from this24-case development pilot.

No new study or rerun is authorized by this handoff. Job31821684's permit is consumed and `closed.json` says `retry_allowed=false`. Do not run `pilot.sbatch`, `campaign`, historical submission helpers, or issue a replacement permit. Do not expand to120 cases, train a new model, change old labels, or turn relaxed parsing into original success. Those require a separately agreed study after reviewing the existing evidence.

The project contains historical documents with earlier status text and machine-specific paths. This entrypoint and current STATUS supersede their operational instructions. The historical full32/64/8-case results, source snapshots and assumptions remain distinct evidence, not pooled new samples.
