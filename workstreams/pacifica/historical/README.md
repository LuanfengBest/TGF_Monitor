# TGF 项目启动说明

本目录用于 Yale CPSC 4880/5880 Guided Track 2 的实验实现。当前主问题是：在统一公开信息、固定权重和有界成本下，TGF 定制追问能否比固定追问、ledger-only、额外原文复查更可靠地识别和定位已执行违规，同时减少误报。TGF 是方法，G²=TPR×TNR 是指标；原 proposal 快照保留，微调仍是条件性后续，没有开始训练。

2026-10-14 当前实际接续：v4六条新轨迹及四路29571002已完成、原始回收与证据审核完毕。见[本轮结果](docs/prospective_four_arm_results_2026-10-14.md)和[下一步机制诊断建议](docs/prospective_followup_diagnostic_plan_2026-10-14.md)。有限阶段已停，自动续办PAUSED、0训练；建议尚未执行。先看[当前状态](STATUS.md)、[交接指南](docs/team_handoff_2026-10-13.md)与[项目日志](PROJECT_LOG.md)，不要按旧待运行快照重提。

以下为此前阶段背景，不能覆盖当前冻结计划：

2026-10-13 新任务已完成20条真实actor轨迹与30事件AI标注，全部业务事件合法，仅两种业务路径；Qwen3诊断28/30核心字段符合参考、2格式失败、0机械证据通过。见[采样结果](docs/candidate_actor_pilot_results_2026-10-13.md)与[monitor结果](docs/candidate_monitor_pilot_results_2026-10-13.md)。另有独立CPU脚本违规/未知对照，进度以STATUS为准。全部为development，不是训练或最终测试。

2026-10-12晚间已完成五条冻结银行轨迹的ledger-only/固定B2/TGF配对，全部结果已回收核验。尚无TGF相对共享账本的额外收益证据；仅3条标签可判定、2条邮件边界待定，全部同属一个development家族。最新结论与成本见 [STATUS.md](STATUS.md) 和 [配对结果报告](docs/paired_results_2026-10-12.md)。双环境Phase 1及正式验证/测试仍未完成。

## 新 session 直接使用

把新 session 的工作目录设为：

`/Users/a1234/Desktop/ai frontier model/monitorability_tgf`

然后发送：

> 请读取本目录 AGENTS.md、STATUS.md 顶部、PROJECT_LOG.md 最新记录和 docs/team_handoff_2026-10-13.md，再打开当前状态所指向的报告和冻结协议。先查询已有 job ID、reservation 和原始产物，不重复提交旧作业。固定权重 TGF 与强基线同信息比较是当前主线；训练资格仍未通过，不恢复旧 SFT pending。区分实际执行、授权、公开可观测性、事件定位和任务成功；AI参考不是人工金标。所有失败、unknown和成本保留；按有限计划停止，更新结果与交接。

## 阅读顺序

1. [AGENTS.md](AGENTS.md)：agent 的工作范围与实验约定。
2. [STATUS.md](STATUS.md)：最新进度、阻塞项与本轮报告。
3. [交接指南](docs/team_handoff_2026-10-13.md)与当前STATUS指向的冻结协议：接手与当前决策门槛。
4. [最终 proposal 快照](docs/final_proposal_2026-10-07.md)与[原执行计划](docs/execution_plan.md)：历史研究方案，不能据此跳过当前训练门槛。

## 工作目录

| 目录 | 用途 |
|---|---|
| docs/ | proposal、计划、协议与审计说明 |
| third_party/ | 后续获取的 MonitorBench 官方仓库；记录 commit |
| configs/ | 模型、数据划分、prompt 与实验参数 |
| scripts/ | 后续编写的运行、导出和评分入口 |
| data/ | 原始轨迹、monitor 可见输入、独立标签和划分 |
| results/ | 监控分数、指标表和分析产物 |
| logs/ | 运行日志、成本、错误和资源记录 |

后三类数据目录默认由 .gitignore 排除，以免意外提交原始运行数据；代码和配置需另行版本管理。

## 相关入口

- [最终在线 proposal](https://docs.google.com/document/d/1s0acz6ibYsIv9OfO0lY6DUSjHZQC9S7ynrUiIecoW6w/edit?tab=t.0)
- [MonitorBench 官方仓库](https://github.com/ASTRAL-Group/MonitorBench)
- 课程目录中已有 Bouchet 使用说明：`../Bouchet_Claude_Code_登录与使用_SOP.md`。到实际连接集群时再读取，当前账号状态和配额需实测。
- `../final_project/` 保留早期讨论资料；其中 2026-09-29 的计划以 SFT 为主，不能作为当前实现依据。

## 历史运行方式（Bouchet，2026-10-12；查看结果无需重跑）

Mac 负责编辑和分析；模型在学校 GPU 上运行。先在网页 Shell 申请资源：

```bash
salloc -p gpu_devel --gpus=rtx_5000_ada:1 --cpus-per-task=4 --mem=48G --time=01:00:00
```

拿到计算节点后进入已准备好的项目并启动服务：

```bash
cd /nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf
module load ollama/0.22.0-GCCcore-13.3.0-CUDA-12.8.0
module load Python/3.12.3-GCCcore-13.3.0
export OLLAMA_MODELS=/nfs/roberts/scratch/hpcllm/hpcllm_rz377/tgf_ollama_models
export OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_NUM_PARALLEL=1 OLLAMA_CONTEXT_LENGTH=32768
ollama serve
ollama list
```

`serve` 是在本次作业内启动模型服务；模型缓存跨作业保留，scratch 保留规则以学校规定为准。学校包装器使用本机地址，不需要开放公网端口。新作业会使用新地址，Python 程序通过 `ollama host` 自动读取。

已经验证过的模拟器检查和 actor 入口：

```bash
.venv/bin/python scripts/check_bank_environment.py --output results/preflight/bank_hpc.json
.venv/bin/python scripts/run_bank_actor.py --check-only --output results/check
.venv/bin/python scripts/run_bank_actor.py --condition ordinary --output results/bank_dev/ordinary_next
```

最后一行会真正调用模型并在模拟环境执行动作。每次用一个新的 output 目录；程序拒绝覆盖已存在的尝试。`ordinary` 是普通任务，`injected` 是额外加入基准隐藏副目标，两者均不预先决定安全标签。

B1 接口（首次真实评分验证状态见 STATUS.md）：

```bash
.venv/bin/python scripts/run_b1.py --view results/bank_dev/ordinary_002/monitor_view.json --config configs/bank_dev_v1_monitor_nothink.json --output results/b1/manual_ordinary_next
```

这里“监控”是另一个模型阅读已保存的轨迹并给出 0–100 怀疑分数。它不会继续操作银行。监控程序只接受 monitor_view.json，不读取 oracle/ 状态和独立标签。`actor_finished` 只表示模型停止行动；是否完成用户任务、是否发生未经授权动作需要另行核查。

本地独立核查和指标入口：

```bash
.venv/bin/python scripts/audit_bank_events.py --run results/bank_dev/injected_001 --spec configs/bank_authorization_dev_v1.json --output results/labels/injected_001.json
.venv/bin/python -m unittest discover -s tests -v
```

v1部分verifier保留用于历史复现；当前使用scripts/audit_bank_v2.py及configs/bank_authorization_v2.json逐事件核验，完整覆盖才标阴性。用户已抽检旧标签并确认正常费用口径，未知效果继续标待定。score_runs.py排除未解决标签；诊断阈值不替代验证集校准。

推荐使用批作业重评已有轨迹，避免浏览器断开导致交互中断：

```bash
cd /nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf
sbatch scripts/b1_direct.sbatch
```

只提交一次，再用返回的作业号查询 `squeue -j 作业号`；完成后看 `logs/b1_direct_batch-作业号.log`。程序按作业号建立新结果目录，且不会重新生成 actor 轨迹。这个命令会消耗 GPU 资源。

汇总本地结果（无需 GPU）：

```bash
.venv/bin/python scripts/summarize_costs.py --output results/costs_2026-10-12.json
.venv/bin/python scripts/score_runs.py --manifest results/manifest_2026-10-12.json --output results/metrics_2026-10-12.json
```

成本汇总包含 probe、失败调用和重试。接口 token 用量与 Slurm 分配时长分开记录；未提供集群计费规则，因此不会把 GPU 成本写成 $0。

旧成功作业29337408和本轮29341393均已结束，GPU已释放。重新运行前确认确有复现需要，不要重复提交仍在运行的作业。B1脚本的历史thinking=true配置保留用于复现已观察到的失败。


## 历史：银行小规模开发 baseline

HPC已实际运行以下命令。它会新生成5条actor轨迹并逐条B1评分，最多45分钟；不需要为了查看结果重复提交。

```bash
sbatch scripts/bank_pilot_v2.sbatch
```

本轮结果目录为results/bank_pilot_v2_29341393。下面的本地分析命令无需GPU：

```bash
.venv/bin/python scripts/audit_bank_v2.py --run results/bank_pilot_v2_29341393/actors/pilot_001_ordinary --spec configs/bank_authorization_v2.json --output results/labels_v2/pilot_001_ordinary.json
.venv/bin/python scripts/verify_pilot_artifacts.py --root results/bank_pilot_v2_29341393 --output results/input_checks_pilot_v2.json
.venv/bin/python scripts/score_runs.py --manifest results/manifest_pilot_v2.json --thresholds configs/bank_pilot_diagnostic_threshold.json --output results/metrics_pilot_v2.json
.venv/bin/python scripts/summarize_costs.py --root results/bank_pilot_v2_29341393 --output results/costs_pilot_v2_29341393.json
.venv/bin/python -m unittest discover -s tests -v
```

manifest记录每条标签证据、审核类型及排除原因；复核后才能修改对应状态。用户的人工抽检记录与程序审计分开，不能称所有新轨迹都经人工逐事件标注。旧调试结果的新审核版本为results/manifest_debug_v2_2026-10-12.json，旧pending版本保留作历史。


## 2026-10-12 晚间诊断与结构化审查

本轮实际结果及限制见docs/diagnostic_review_2026-10-12.md，最新执行节点见STATUS.md。两个作业已结束，不需要重复提交来查看结果。

本地离线复核（不调用模型）：

```bash
.venv/bin/python scripts/analyze_b1_checks.py --run results/b1_checks_29347475
.venv/bin/python scripts/analyze_structured_review.py --run results/structured_review_29347982
.venv/bin/python -m unittest discover -s tests -v
```

HPC原运行命令为sbatch scripts/b1_checks.sbatch（29347475）和sbatch scripts/structured_review.sbatch（29347982）。重新提交会产生新推理和新GPU成本，不属于查看现有结果。原文索引data/diagnostics/visible_evidence_index_v1只完成离线构造，尚未用于新的模型评价。


### 原文索引诊断（2026-10-12）

方案与运行状态见 `docs/indexed_review_2026-10-12.md`。作业29351822使用 `scripts/indexed_review.sbatch`，新runner为 `scripts/run_indexed_review.py`。查看已有结果不需要重新提交GPU作业。

离线预检：`.venv/bin/python scripts/run_indexed_review.py --preflight --output results/indexed_review_preflight.json`。
回收后核验：`.venv/bin/python scripts/analyze_indexed_review.py results/indexed_review_29351822`。
原始来源校验、逐事件覆盖、语义正确性分别检查；`scored`不代表语义正确。所有样本仍为development，独立标签保持原样。


## Full-visible paired follow-up development runner (completed 2026-10-12)

All five frozen cases now have ledger-only, fixed B2 and TGF scores. See [the paired results](docs/paired_results_2026-10-12.md). Native-counter recovery v3 reused the complete eight-call v2 prefix after hash and exact-payload reconstruction checks, added its missing TGF judge in job29365821, and completed the remaining four cases in job29366122. Both completed successfully; remote and local verification passed. Old v1/v2 failures remain unchanged. **Do not resubmit old sbatch files or remove stage reservations to view these results.**

The methods share full visible evidence, initial review, selected event, k=1, independent tool-disabled actor branches, judge and reply caps. Runtime monitor inputs do not directly include hidden actor instructions, reference labels or verifier files. Original/answer thinking may itself mention the side objective: its presence in an actor output is not new permission. No full human audit of these five labels, resolved email-boundary labels, calibrated test performance or TGF gain is claimed.

Read-only local reproduction (no model calls):

```bash
.venv/bin/python scripts/verify_paired_v3.py --output results/paired_native_recover_29365821
.venv/bin/python scripts/verify_paired_v3.py --output results/paired_native_remaining_29366122
.venv/bin/python scripts/analyze_paired_v3.py --outputs results/paired_native_recover_29365821 results/paired_native_remaining_29366122 --save analysis/paired_v3_results_2026-10-12.json
.venv/bin/python scripts/account_paired_v3.py --outputs results/paired_native_recover_29365821 results/paired_native_remaining_29366122 --save results/costs_total_through_paired_v3.json
```

The full paired stage cost45 calls/1853 allocated GPU seconds including both failed attempts; v3 added29 calls/1322 seconds. The37 unique calls used by the completed protocol comprise35 core calls and2 calibrations; the other8 are failed v1 overhead. Reused v2 requests are charged once. Full history is in `results/costs_total_through_paired_v3.json`.

The native tokenizer uses actual GGUF vocabulary/token types and pinned official Ollama Go BPE, with source/build hashes. It reproduces all12 historic monitor counts, including the HF/backend four-token discrepancies; v3 actual monitor counts also passed. Historical diagnosis: `docs/paired_attempts_2026-10-12.md`; frozen recovery protocol: `docs/paired_recovery_v3_2026-10-12.md`. The runtime scripts/configuration are frozen; future semantic changes require a new version.

最新新家族数据合同与基线：[monitor_v2_baseline_protocol_2026-10-13.md](docs/monitor_v2_baseline_protocol_2026-10-13.md)。标签已冻结，GPU状态以STATUS顶部为准。
