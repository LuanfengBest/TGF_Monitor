# 已批准的首批未尝试20条恢复

2026-10-15。直接用户批准见results/pilot_collection_recovery_authorization_20261015.json；只恢复29672744原计划中未尝试的011–030，不重复001–010，不改原科学采集配置。

首批现有10条/116事件主AI审核已保存analysis/pilot_collection_v1_b01_AI_review_20261015.json；来源/状态/格式核验与覆盖见analysis/pilot_collection_v1_b01_AI_coverage_20261015.json。8非错误轨迹为银行4P0N（公开可证1），航空2P2N（公开可证2），两域合法敏感执行负例均0。两个错误前缀仅记录无已观察违规，不计入负例。审核非独立、非人工金标。当前不具备效果比较资格。

恢复的问题是：原固定候选的剩余20条能否提供可信标签及原任务所缺类别，特别是合法敏感执行负例？不改变任务来凑类别，不保证达成目标，不把多seed称独立新任务。它是有界数据可行性工作，不是monitor效果实验。

原freeze的20个attempt_id/seed16011–16030/顺序/模型digest/模板/system/prompt/tools/任务资产/完整上下文保护均保持不变，直接调用原actor.rollout。固定gpu_devel、rtx_5000_ada:1、4CPU、48GiB、49分53秒。原607秒+本次至多2993秒仍在首批3600秒内；整个240候选/480单GPU分钟/9600calls上限不变。本次最多800actorcalls、0monitorcalls、0训练、0失败重试、0第二恢复。Python运行deadline2840秒，外层timeout2870秒、15秒kill grace。

仅在错误文本精确为原Context guard、完整原context/工具schema按原字节公式复算吻合、submitted=false且持久化请求响应计数吻合时，将该候选记context_guard_excluded并继续下一个原定候选。保留error、prefix、全部成本；此类不进P/N目标。任何其他运行异常、来源变化、不可解释计数、时间不足即停；不修改保护器、不截断、不扩大预算。

唯一提交前：原190来源+本次来源hash核验；原失败复现和重复提交拒绝等控制测试；远端零推理预检；用户队列空；无既有submission/reservation。无法确认sbatch结果必须查真实Slurm，不重复提交。

终态唯一归档，回收whole/perfile hashes、全部20计划位置与真实调用成本；逐项审查所有可用事件。与原30位置按原attempt_id合并时，原失败不可被覆盖，不能用新成功记录替换旧失败。恢复后的完整数据验收先于任何下一批：数量、P/N/unknown/失败、敏感合法负例、公开可证正例、来源完整性及任务相关性均公开。现有旧accept脚本不能接受失败首批，不伪造其technical_complete。恢复本身不授权自动提交第二批或任何效果比较/SFT。

Progress report独立推进：用户10月17日先与组员汇报，课程10月21日23:59截止。以真实已完成数据写作，不以等待正结果拖延。遇关键覆盖或标签问题及时说明，不事后靠改口径掩盖。
