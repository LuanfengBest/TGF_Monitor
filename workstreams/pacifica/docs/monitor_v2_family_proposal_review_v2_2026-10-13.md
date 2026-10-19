# Monitor v2 提案第二轮审核（AI）

三份修订草案可进入 fixture 准备：bank_cumulative_spend_pool、bank_batch_quorum、airline_duplicate_retention。这里只确认公开任务合同静态自洽及机制分组候选；没有批准模型、actor、轨迹或训练，也没有声称 CPU 测试通过。

我在 family_proposals_v2 新建三份修订稿，原文与 v1 审核保留。银行用 subject 明确 pool/order 或 batch/version/payout，补唯一账号/规格连接、初始 snapshot、实际成功累计、字面日期、nonexecution 与 unknown 区分。quorum 明确逐笔非原子，retention 明确同乘客分组、全局唯一 confirmation 和初始固定 survivor。每份草案内列静态自查及剩余 fixture 门槛；这属于作者自查，不是独立复核。

新的 airline_connection_window 仍不能作为隔离 train 家族。上游 american_airlines_2 README 第 2 行已明确要求为无直飞的两人找时间可衔接的转机；task_definition 第 28 行也要求 Phoenix→中转城市→Boston 两段。新草案的城市连接和 arrival/departure 相对窗口落在这个已暴露子机制内。指定已有 anchor、单乘客和 60–180 分钟边界不足以证明新机制；只与本地 rebooking 比较会遗漏上游来源。我没有修改这一重大机制，已通知主 agent。

因此四项整体仍不能冻结 executable registry。请另提航空 train 机制后重新检查跨 split 关系；其余三项可以准备 fixture，但仍需真实工具/schema 可见性、独立状态、失败效果、hash 冻结等 CPU 门槛。特别要检查取消一个同乘客同 flight 的确认号后 survivor ticket 仍在，不能用 legacy 汇总作替代证据。后续最多 12 个审核事件的上限不是本次生成许可。

所有现有 development 保持原组；同机制全部改名、金额、seed、授权改写和短/全视图仍同组。最终测试家族仍缺失，四份草案不具有最终未见 test 资格。完整来源 SHA、逐字依据和每项剩余条件见配套 JSON。
