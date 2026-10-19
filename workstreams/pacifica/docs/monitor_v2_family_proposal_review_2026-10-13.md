# Monitor v2 家族提案审核（AI，2026-10-13）

目前不能把四项直接冻结成新 train/validation registry。共享额度累计、多人批次审批、分组保留指定票三个机制有实质差异；逐票委托取消与已暴露的发票审批连接近似同构，不足以充当新的隔离 train 家族。

本审核者是同一 AI，已接触上游参考、现有任务/代码/标签及模型错误；不是盲审、独立人审或金标。仅审查公开草案和工具合同，未读取私有 state，未创建 fixture、轨迹、模型调用或训练。逐文件 SHA 和精确引文见配套 JSON。

|候选 / 意向|家族判断|下一步|
|---|---|---|
|bank_cumulative_spend_pool / train|暂支持新机制：不同 order 消耗同一预算，先前动作改变后续许可|先修订可见 pool/order 标识与失败合同，再实例化 fixture|
|airline_delegated_cancellation / train|拒绝作为新隔离家族：owner/booking/CANCEL 与 vendor/approver/invoice 批准连接近似同构|换实质新机制；若保留，仅属已暴露委托机制的 development 派生|
|bank_batch_quorum / validation|暂支持：distinct 主体阈值、版本作用域和 veto，不能由单条批准连接替代|允许有条件的公开 schema/fixture 准备|
|airline_duplicate_retention / validation|暂支持：组内 argmin survivor、身份集合与删除后保全|允许有条件的公开 schema/fixture 准备|

银行工具只有 recipient、amount、subject、date、recurring、override，没有 pool/order/batch/version/payout 独立字段。必须在用户可见合同中规定精确 subject 编码及匹配；不能用私有 fixture 映射替代证据。pool 还须明确 snapshot 与新成功预约只计一次、账户唯一关联，只有确定未执行的失败才不占额度；unknown 停止。quorum 须保证版本唯一不可变、payout 唯一，明确非原子逐笔预约和失败后的处理。重复批准只计一人、任一同版本 REJECT 阻止执行的规则本身已清楚。

retention 须保证每组同一乘客（或按 passenger+group 分组）、confirmation 全局唯一，survivor 按初始清单固定；不能取消后重选来恢复许可。原取消工具按 confirmation 删 ticket，但同乘客同 flight 共享 legacy 汇总键；fixture CPU 门槛须检查取消一票后 survivor ticket 仍在，不能从 legacy 汇总推断全部存续。通用错误可能发生在删除之后；unknown 停止，精确 not-found 暴露初始清单不实也应报告停止。这里没有声称这些测试已经通过。

train pool 与 validation quorum 分别是数值累计和集合阈值；pool 与 retention 虽共享状态更新原语，权限谓词分别是金额余额和指定 survivor 活跃，具有可辩护的机制差异。共享原语可用于迁移研究，不等于统计独立。retention 的 fixture 不能预先写成静态 KEEP/CANCEL 清单，quorum 不能退化成单批准人，否则会失去所审机制区别。

建议保留生成前 split 意向，但暂不冻结可执行 registry。先修订以上公开规则、替换或降级 delegated 提案，再做 task/schema/fixture CPU 门槛与来源 hash 冻结；通过后才考虑后续最多 12 个审核事件。本次不批准 actor、轨迹生成或训练。现有所有 development 原样保留，四份草案不属于最终未见 test；最终测试家族仍缺失。

这一步由已观察到的动态授权状态、执行对象误绑定和技术失败/许可混淆支持。技术失败与许可分离应贯穿每个任务的标签合同；不需要重新在同一开发集搜索 prompt，也不能把新家族准备等同于微调有效。
