# 本批执行入口

工作目录是 TGF_Monitor。`PROTOCOL.md`、`config.json`、`AUTHORIZATION.json` 与 `manifest.json` 是冻结依据。

本地离线检查已完成：192 个原模拟器 witnesses、12 个隔离导出 witnesses、7 项科学约束/预算/不重试检查。CPU witnesses 不是正式效果数据。未使用新模型输出调整问题。

1. `python -m tgf_jev_mainline_v1.prepare freeze` 后执行 `python -m tgf_jev_mainline_v1.judge_stage jev --phase smoke --key-file /Users/a1234/.config/typesafe/api_key`。
2. 上传 manifest 列出的文件、manifest 本身和 Jev smoke 产物到独立目录。逐文件/压缩包验证；部署脚本先检查账户、现有队列、association 和三种 sbatch dry-run。
3. 提交一次 `cpu.sbatch`。必须取得实际成功退出和新的 `admission.json`，其中逐字节核对 Actor/Qwen 权重、容器和依赖，并检查 Harmony 与 JSON 语法。
4. 提交一次 `actor.sbatch`，完成自然采集、参考封存与工具关闭的 F/T 回答。若没有完成全部预定处理，保留失败并检查，禁止自动补跑。
5. 作业 COMPLETED / 0:0 且 actor_summary.complete 为 true 时，提交一次 `qwen.sbatch`。该阶段执行 C 复查并封存两个 Judge 完全相同的正式输入，再运行 Qwen。
6. 下载部署脚本导出的结果 ZIP，逐个验证 RESULT_FILES.json。核对 Qwen 作业 accounting、退出和全部计划位置后，本地执行 `python -m tgf_jev_mainline_v1.judge_stage jev --phase formal --key-file /Users/a1234/.config/typesafe/api_key`。
7. `python -m tgf_jev_mainline_v1.analyze` 计算预定配对结果。补齐按策略的真实部署成本、唯一输入敏感性分析、差异案例与预选未变化案例的语义复核，形成报告。

远程 `tgf_jev_mainline_v1/deploy.py` 的 status 只读取调度和结果。prepare/cpu/actor/qwen 有一次性 claim；调度响应不明确时检查 claim 与队列，不重发。sbatch --test-only 返回的预测编号不当作实际作业编号。

Jev key 始终留在本机私有配置目录，禁止打包 `.venv`、key、浏览器状态或运行时模型资产。没有新定时任务。
