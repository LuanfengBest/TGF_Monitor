# 候选任务家族草案

这4项只用于讨论授权结构与环境实现，不是冻结family registry、可运行task definition或新数据。没有actor轨迹，没有标签，不计入训练条数。不能仅凭candidate_id不同宣称独立家族。

审查顺序：用户/组员核对任务含义和权限边界；完成模拟初始状态与工具合同；审查是否只是既有任务的改写；按独立家族分配split并冻结；最后生成20条标注试验。所有变体、seed、视图和授权对随家族，不跨split。split为null时收集器必须拒绝生成训练数据。

这些草案已在开发过程中阅读，不作为未见最终测试定义。最终银行和航空测试家族应由未参与调参的成员另外封存。第一批先只使用通过审查并分配到训练/开发的家族，最终测试不参加标注口径迭代。

2026-10-13实现补充：发票和单人改签的CPU组件及14个脚本探针已保存在data/task_design/，见[实现准备记录](../../../../docs/task_family_readiness_2026-10-13.md)。原草案不覆盖，仍未成为完整actor任务，也没有训练资格或冻结split。银行撤销候选暂缺真正的取消预约工具；update_scheduled_transaction不能替代取消。新组件是AI设计审核，未声称独立人工认可。

每项的state_work_needed列出尚未完成的具体实现，proposed_user_request是拟议允许委托，不含隐藏副目标或参考答案。bank_revoked_standing_permission尚需确认取消工具和可见时钟，不能直接运行。
