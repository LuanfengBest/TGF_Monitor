# 可见执行事实层原型

2026-10-13。实现 scripts/observed_execution_v1.py，6项本地单元测试通过；对5条旧开发轨迹做了离线回归，结果 analysis/observed_execution_v1_regression.json。未接入当前冻结的候选模型对比，未测量模型收益，不是部署完成。

旧 paired ledger 已有 call_source/result_source。新原型增加具体工具返回合同的保守解释，减少把所有执行判断交给模型；它不判断授权，也不把 actor 解释当作执行证明。

- 只读 user_request、policy、messages，不读取 oracle/verifier/参考标签。每个调用和返回保留原文、来源位置、结果hash。优先明确call ID；旧串行导出仅在一个待匹配调用时按工具名配对；并行歧义保留未知。
- 首批支持单次 schedule_transaction、send_money_zelle/venmo、transfer_bank_to_zelle/venmo 的少数已核查返回形式。成功的金额/收款人必须与调用参数一致；不认识的返回、未知工具和缺失返回均为unknown。预约成功不等于结算。
- 失败后重试分成独立事件，后续成功不会改写前次失败。只有思考计划没有工具事件时不生成执行事件。缺失返回也不直接判非执行。
- “observed_nonexecution”仅适用于具体命名操作的明确返回，不表示整个工具没有任何副作用。上游部分失败/验证路径可能有手续费或其他状态变化；未经合同核验的失败保持unknown，不把通用Failed前缀映射成安全。

依据为固定上游 commit 的公开工具实现 financial_transfer.py；代码/来源hash保存于离线回归文件。原文引用匹配与工具合同解释仍不能证明真实外部系统发生了什么，只表示本模拟器可见返回所支持的事实。

旧开发回归共104条绑定记录：34条observed_success，10条observed_nonexecution，60条unknown（包括未支持的读取/邮件/其他工具）。这不是安全分类正确率，也不代表unknown都是模型难例。尚需独立任务/并发调用/中断与部分副作用案例验收，然后与同基座未使用事实层的monitor做对照。授权语义、金额分摊依据选择仍由模型及审核数据解决。
