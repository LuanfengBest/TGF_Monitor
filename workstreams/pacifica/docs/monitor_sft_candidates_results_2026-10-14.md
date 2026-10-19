# 11 条微调候选的格式验收结果

2026-10-14。已完成本轮有限 CPU 数据阶段：原有 5 条银行累计支出事件和 6 条行程邮件投影事件，统一编成严格因果输入、紧凑答案和答案专用 loss mask。没有新增训练样本，也没有微调模型或新的 monitor 成绩。

## 实际产物与核验

冻结配置 `configs/monitor_sft_candidates_v1.json`，SHA256 `3543d544d76e86a157a2311a43b0a0d3f5ad340ea23deb384a11bc8911a24448`。43 个来源文件在导出前冻结，正式 export 仅执行一次；verify 重建全部输入、目标、token 和 loss mask 后一致。

- `data/training/monitor_sft_candidates_v1/candidates.jsonl`：11 个候选，核心标签仍为 4 true / 5 false / 2 unknown；所有 training_eligible 仍为 false。
- 同目录 `tokenized_candidates.jsonl`：Qwen3-32B 固定修订的 tokenizer 与官方模板，enable_thinking=false；只监督答案 JSON 与结束 token。提示、轨迹和空 thinking 前缀不计 loss，未来批处理的 padding 也必须屏蔽。
- 同目录 `manifest.json`：逐例长度、来源与产物哈希、未通过门槛。
- `analysis/monitor_sft_candidates_v1_acceptance_20261014.json`：15 项本地测试通过；407 个旧保护文件逐字节未变。没有将旧 validation 错例改写进 train。

银行目标从原详细审查约 3,740–4,477 tokens 缩为 326–378 tokens；旅行目标为 546–582 tokens。实际完整序列为 2,423–2,914 tokens，均未截断。这证明格式负担下降，不能证明模型准确率提高，也不能由序列长度推断 GPU 一定装得下。

输入保持原始消息的因果前缀，禁止后续消息、私有状态、execution_facts 和参考标签。证据是可取回原文的 JSON 指针；保留全部原有条件检查（银行每例 6 或 7 项，旅行每例 21 项）。测试覆盖未知标签、失败与许可分离、调用/返回错绑、未来/私有字段污染、actor 自述不能作证明、无效证据、划分污染、模板边界和长度上限。指针有效不等于语义判断正确。

实际命令：

```bash
.venv/bin/python -m unittest discover -s tests -p test_monitor_sft_candidates_v1.py -v
.venv/bin/python scripts/monitor_sft_candidates_v1.py freeze
.venv/bin/python scripts/monitor_sft_candidates_v1.py export
.venv/bin/python scripts/monitor_sft_candidates_v1.py verify
```

freeze/export 已完成，不可重跑覆盖；复现只执行 verify。测试在补入来源完整性检查后重跑通过。本轮全部是非盲 AI 候选和主 agent 核查；expert_annotation 用量受限，未完成独立复审，不是人类金标。

## Bouchet 已恢复连接

用户完成 Yale 登录后，正常课程 OOD 确认 hpcllm_rz377 登录；Your Jobs / All Clusters 显示 0 条作业。既有项目环境在加载 `Python/3.12.3-GCCcore-13.3.0` 后可正常运行 Python。最初未加载模块的 libpython 报错已经定位，不是训练失败。

只读探测发现：tokenizers 存在；torch、transformers、peft、trl、bitsandbytes、datasets、accelerate、Jinja2 均不在该项目 venv 中。本轮没有安装训练栈或下载权重。getquota 的组数据快照最早为 10 月 14 日 00:00：project 46/4096 GiB，scratch 59/10240 GiB；门户仍有共享存储紧张通知，配额余额不能代替实际写入和资源预检。原始观察摘要见 `results/monitor_sft_candidates_runtime_observed_20261014.json`。

## 已通过什么，还缺什么

| 项目 | 本轮结论 |
|---|---|
| 格式、原标签保持、因果输入、证据定位、loss 范围 | 本地检查通过 |
| 数据覆盖与独立性 | 仅 11 个相关 AI 候选、2 个家族；不能支撑广泛泛化结论 |
| 未见最终评估 | 尚无独立最终 test 实例；旧 validation 保持原状 |
| 训练底座 | 固定 HF 修订已选；完整权重和训练运行时尚未就绪 |
| 显存、梯度、保存恢复 | 均未实际测试 |
| 微调收益 | 未训练，无法评价 |

下一阶段应先冻结一份有限的训练/未见评估方案，再补齐该方案规定的独立任务实例与标签核验。不能靠重复这 11 条、改数字或把 validation 的错误搬进 train 来假装扩大证据。通过数据门槛后，在独立环境准备同一 HF 底座并做单批显存/梯度/保存恢复预检；最后才运行一次有预算的小型 LoRA 对照。对照须同底座修订、量化、后端、输入和解码，比较 adapter 关闭/启用；旧 Ollama 分数只作历史背景。

原 B3/公开解释输出 30 调用计划和 6 例邮件 GPU 诊断继续暂缓。TGF 是可选方法，不是训练前置；G² 可继续作为有正负类的检测指标，解释证据支持另计。无需引入真人审核效果实验。

本轮新增 0 实验模型调用、0 GPU 作业、0 训练；历史累计 658 集群调用、18,588 主要 GPU 秒不变。AI 助手服务费用未知。自动续办保持 PAUSED，本轮有限数据格式阶段完成后不自动扩批。
