# 本轮执行与完成记录

本轮已完成并停止。报告见 [REPORT_2026-11-06.md](REPORT_2026-11-06.md)，最新机器状态见 [STATUS.json](STATUS.json)。定时续接已在完成复核后停止并移除，回执在 `execution_history/automation_completion_stop.json`；关闭前设置已保留。

授权范围是订票 24 条 P/C/F/T 比较，最多 240 次模型调用、589824 输出 token、一个 H200 作业、含启动 2 小时。原采集 32257283 已结束；本轮不重采、不重试、不补量、不换模型、账号、提示词或标签。

CPU 32350337 检查成功（ready_for_live=true）。唯一 GPU 32354336 于 2026-11-06T22:26:59.562696+00:00 有明确提交回执，运行于22:27:36–22:54:39 UTC，COMPLETED，退出0:0，含启动27分03秒。本轮提交额度全部用完，不得重新调用 airline_dev_v1.submit 或提交任何新 CPU/GPU 作业。

远端归档来源只通过 cpsc4880 Yale OnDemand 会话访问：`/nfs/roberts/project/cpsc4880/cpsc4880_rz377/airline_comparison_20261106_v1`。该路径不是本地目录。原始 comparison、admission、logs、permit、claim、提交和 scheduler 记录已下载到 `cluster_results_32354336/`，远端和本地全部哈希匹配。

本地冻结 airline_dev_v1.report 已成功生成 report_32354336：全部96个位置有效，失败/未知/未开始均0；240次实际调用，用量完整，99,587输出token。当前助手随后逐条阅读24条公开原记录、96个最终判断、48个追问回答，完成非盲AI作者语义复核；不属于独立/人工/盲审。原始分数及参考标签均未修改。

主比较T相对F新增检出0、新增误报1，不通过预设开发筛选线。原批次两环境覆盖不足仍然成立；本轮是事后选择订票环境的开发诊断，不是正式效果或创新证明。停止在本批，不按bad case自动改规则或扩量。

若需离线复现，从仓库根目录使用本地Python运行冻结报告工具，并把输出写到新的目录；该动作不调用模型、不访问集群、不提交作业：

```bash
../monitorability_tgf/.venv/bin/python -m airline_dev_v1.report --bundle project/airline_monitor_comparison_2026-11-06/bundle --run project/airline_monitor_comparison_2026-11-06/cluster_results_32354336/comparison --output <新的本地报告目录>
```

用户明确授权“开启，按固定上限继续”的凭证仍为 AUTOMATION_AUTHORIZATION.json；冻结 AUTHORIZATION.json 中 automation_authorized=false 是准备时历史字段，不回写。初始授权、所有提交和停止回执均保留。本记录不授权另一轮实验。
