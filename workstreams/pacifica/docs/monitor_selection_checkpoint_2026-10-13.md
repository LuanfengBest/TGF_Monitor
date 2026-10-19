# 选型诊断启动检查点

四调用试运行 **29412254 COMPLETED / 0:0 / 110秒GPU**，原始请求、响应、thinking、用量、source hashes及解析已回收并逐请求重建验证。两配置各2/2核心参考判断通过；no-think引用5/6逐字匹配、thinking引用7/9匹配，3处失败为改写或省略号而非逐字引文。thinking原生输出可见，两次均正常停止，未发生旧循环；只覆盖两个控制，不能推出总体更优或循环原因已证实。

原始结果 results/monitor_selection_smoke_29412254/；本地分析 analysis/monitor_selection_smoke_2026-10-13.json。回收包SHA256 58949edfb54914f158ce636cd135e627b7afd9256bfa041d40720096c335180e 与远端一致。

已按冻结计划提交 `sbatch --time=00:35:00 scripts/monitor_selection_v1.sbatch remaining results/monitor_selection_smoke_29412254`，作业 **29412502 已观察 RUNNING**。最多22个新调用，结果预期 results/monitor_selection_remaining_29412502/，日志 logs/monitor_selection-29412502.log。不可重复提交同stage或删除reservation；技术失败/预算耗尽即停止，保留部分产物。累计已完成成本快照382调用、9169秒主要GPU（不含正在运行作业）；成本 results/costs_total_through_selection_smoke.json。

下一步：检查29412502完成/失败状态，完整回收并执行 scripts/analyze_monitor_selection_v1.py 的两目录核验，逐案审查金额与引用语义；不改本轮输入或参考。随后才进入已列明的Qwen3.5候选兼容性/能力比较。候选当前只有本地官方manifest/tokenizer，未加载权重。训练合同与来源清单已准备，合格训练事件仍0，无训练作业。总体计划见 docs/monitor_selection_training_plan_2026-10-13.md。

