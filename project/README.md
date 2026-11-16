# TGF final project: current evidence

For the current research overview and CPU reproduction steps, start with the [repository README](../README.md) and [data/code guide](closeout_2026-11-07/DATA_AND_CODE.md). This page preserves dated checkpoints; historical “current” or “pending” statements should be read at their stated date.

**2026-11-13 综合报告与展示：** [最终综合报告](final_report_2026-11-13/FINAL_REPORT.md)、[PDF](final_report_2026-11-13/deliverables/Authorization_Auditing_Report.pdf)、[可编辑 Word](final_report_2026-11-13/deliverables/Authorization_Auditing_Report.docx)、[更新后的展示](https://chatgpt.com/space/page_6f15e7205f9c81918f8762765794d4af)及[中文讲稿](final_report_2026-11-13/SPEAKER_NOTES_ZH.md)已整合本次 8 对结果和整个项目主线。Jev 是主要最终 Judge，研究问题仍是执行时授权；保留定向追问、Jev 时间索引及早期实验的负结果。9 页报告、12 页主讲＋5 页附录；原始数据和旧报告保持不变，原在线展示已原位更新。此次没有新增实验或扩量，真人复核仍为 0；[交付与复核说明](final_report_2026-11-13/README.md)。

**2026-11-12 最新完成结果：** 原来的 8 对时序/范围案例已完成 64/64 次有效正式判定。Jev 原文、索引均为 8/8 对正确；Qwen 分别为 4/8、5/8。主要对比 Jev 索引减原文为 0；Qwen 的次要改善仅一对，无关许可对照仍有不当翻转。[完整结果](authorization_timing_jev_2026-11-12/RESULTS.md)。第一次启动失败后，用户明确批准一次额外 GPU 分配；修复后的作业 `33178680` 用时 2:16，连同第一次失败累计 22:53，未超过 30 分钟。总调用 72/72，Jev 估算 $0.001716，未重采样、未重复判定。[当前执行记录](authorization_timing_jev_2026-11-12/RUN_STATUS.md)优先于历史准备状态。

**2026-11-12 当前共享进度：** [组员交接说明](research_update_2026-11-12/TEAM_HANDOFF.md)、[更新后的研究主线](research_update_2026-11-12/RESEARCH_DIRECTION.md)、[Jev 主实验报告](research_update_2026-11-12/reports/mainline.md)、[下一步盘点](research_update_2026-11-12/NEXT_STEPS.md)和[离线复核入口](research_update_2026-11-12/README.md)。主线批次 192 个采集位置、189 条合格轨迹；同材料直接判断时，航空 Qwen/Jev 分别检出 8/26、21/26，均 0/67 误报。预定 Jev T−F 主对比未通过；完整回答子集中的 F/T 判定相同。新的叙事保留授权审计主线，区分 Judge 能力、证据使用和追问收益，不改写历史负结果。Qier 时序诊断与 Tony 证据审计已链接并标明完成范围。新增 8 对构造诊断单独报告；下方旧报告与展示仍属于各自历史批次。

**保留的准备资料：** [32 条 AI 来源复核及空白真人复核包](research_update_2026-11-12/source_review/README.md)已备好，非盲、非独立，真人完成数仍为 0。[时序扩展 v0.2](authorization_timing_jev_2026-11-12/PROTOCOL.md)为 4 对基础＋2 对隔着无关消息＋2 对无关许可，共 6 对应变、2 对应保持；[评价指标](authorization_timing_jev_2026-11-12/METRICS.md)检查正确改判、正确保持、不当翻转和不可用。原方案、预算与准备快照保持原字节；后续执行与一次额外分配的授权单独留档。[研究意义](research_update_2026-11-12/IMPLICATIONS.md)。

**2026-11-07 定稿与复核：** [最终报告](closeout_2026-11-07/FINAL_REPORT.md)、[中文展示讲稿](closeout_2026-11-07/deliverables/SPEAKER_NOTES_ZH.md)及[仓库阅读和离线核验指南](closeout_2026-11-07/REPOSITORY_GUIDE.md)。120 次补验已完成：105 个有效输出、14 次截断、1 次格式失败；有效输出中 104 个标签正确。累计金额只纠正一个实例块，未达预设两块改善标准；有效真假断言配对没有判断翻转。独立上下文 AI 盲审与 12 条最终参考标签全部一致，不是真人金标。报告与展示已完成；团队仍需确认贡献和课程格式并正式提交。所有实验和定时跟进已关闭。下方保留历史批次范围，当前综合结论以最终报告为准。

**2026-11-06 比较与复核已完成：** [订票 24 条四组结果](airline_monitor_comparison_2026-11-06/REPORT_2026-11-06.md)。P/C/F/T 分别检出 5/2/6/6 条违规，误报 0/0/0/1 条合法记录；96 个判断均有效，240 次调用、27 分 03 秒（含启动）。逐条非盲 AI 作者复核未改原分数或标签。T 比 F 没有多检出，反而多 1 次误报，未通过预设开发筛选线。本轮与定时跟进已结束，不自动扩量。旧批次两环境覆盖不足仍保留，本轮不能当成正式效果或独立项目创新证据。[完成状态与凭证](airline_monitor_comparison_2026-11-06/STATUS.json)。下文保留历史批次的独立范围。

Updated November 5, 2026 for offline evaluation alignment. Team names follow the [final proposal](reference/final_proposal_2026-10-07.md).

**New data collection reviewed:** [results and evidence](new_data_collection_2026-11-05/REPORT_2026-11-06.md). Job `32257283` completed 48/48 cases, 155 actor calls, 9m05s including startup. Nonblind AI author review: bank 1 violation / 23 sensitive negatives; airline 6 / 18. Bank fails the frozen positive-count and instance-block gate; airline passes development coverage. The batch ends with no retry, replenishment, monitor run or expansion. [Frozen specifications](new_data_preparation_2026-11-05/README.md) remain unchanged; no independent-review or effectiveness claim is permitted.

**November 5 offline checkpoint:** [88-record evaluation package](evaluation_alignment_2026-11-05/README.md), with separate label namespaces, public development views, source hashes and a scorer that preserves failures. The legacy B2's historical 20/24 detection count included one null score imputed to 50; there are 19 explicit detections, 4 explicit misses and 1 invalid positive-case result. Historical files remain unchanged. No new model/simulator runs were launched; the authorization-verification expansion is not the active workstream.

**Start here:** [Pacifica’s short group update](PACIFICA_PROGRESS_2026-11-03.md) and [AI handoff / offline reproduction](AI_START_HERE_2026-11-03.md).

**Earlier completed run (November 3):** development job **31821684**, 24 natural trajectories, 210 model calls, 20m08s. All 24 are legitimate sensitive executions; no executed authorization violations were generated. Original valid P/C/F/T judgments are 9/3/3/4 out of 24 each. F/T valid pairs remain 0/24. This is not held-out evidence of TGF effectiveness.

**Offline diagnosis:** C/F each stopped 21 cases at the initial review, leaving no final judgment. Across all arms, 77 results failed exact citation validation. Four raw T scores additionally show unsupported timing/authorization concerns, and five T rationales cover only part of the record. [Read the diagnosis](prospective_monitoring/offline_diagnostic_2026-11-03/DIAGNOSIS.md). Raw scores and qualitative annotations do not replace frozen original results.

**Current coordination:** a teammate is running a separate four-case B2/revised-TGF comparison. Its case IDs, configuration and outputs have not been received. Use the [comparison worksheet](prospective_monitoring/offline_diagnostic_2026-11-03/TEAM_4_CASE_REVIEW.md) after they arrive. Do not pool batches or launch another comparison from this handoff.

**Implementation and data:** [prospective_monitoring](../prospective_monitoring/README.md) contains explicit authorization references, simulator state recording, four independent strategies, native bounded execution and reporting. The completed run has a verified original results archive in the handoff. The prior 159-test engineering acceptance is documented in [STATUS](prospective_monitoring/STATUS.md); it is not scientific efficacy evidence.

**Study scope:** the [November 3 design](research_reset_2026-11-02/EXPERIMENT_PLAN_2026-11-03.md) tests full action-selection-plus-questioning strategies. The October21 plan's shared-action comparison isolates a different question. The proposed120-case formal study is not ready or authorized. Existing job permits are consumed; no retries, automatic expansion, model training, or changed acceptance rules are part of this handoff.

Older v1/v2 observations, dev64 proxy-label results, authorization audits and SFT diagnostics remain separate historical evidence. Some old large artifacts are local archives, not new shared data in this handoff.

## Historical integrated evidence (October 19)

The following sections retain their historical scope, including the old null-to-50 scoring convention. The November 5 package above supersedes those counts where imputation affected them. Current execution and next-step information is above.

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
