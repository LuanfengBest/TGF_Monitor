# 新家族提案 v4：尚无新增合格 train/test

本轮保留 4 个候选，0 个获准生成。作者是参与既有设计、标注和基线审核的非盲 AI；这不是独立人审或人工金标。现有 development、train pool、validation quorum/retention 均不改组。已读来源及 SHA256 在 manifest.json；每份提案逐一比较 11 个旧机制/草案。

| 候选 | 预分组 | 新关系 | 当前决定 |
|---|---|---|---|
| travel_itinerary_field_projection | train 意向 | 丰富行程记录→允许字段投影→所有实际邮件输出通道 | 待范围决定；是 Travel 工作区邮件任务，不是新增航空购票家族 |
| bank_scheduled_field_preservation | final_test 意向 | 既有预约的前后字段保持，仅改指定日期 | 待范围及 no-op/有效状态变化合同复核；不得称最终 test 已冻结 |
| travel_calendar_interval_exclusion | final_test 意向 | 完整 confirmed 日程集合→逐区间不相交 | 待范围决定；是 Travel 日历任务，不是航空买/取消票 |
| airline_atomic_ticket_bundle | train 意向、已拒绝 | 两张票全有或全无且不存在中间部分状态 | 原 buy 每次立即存一票，无原子提交工具；不得强行生成全非法训练集 |

邮件发送、银行预约更新、日历创建虽已在原环境注册，但都是当前 schedule/buy/cancel 实验面的扩展，不能仅凭“同一环境”声称补齐缺失的航空 train/test。航空连接、委托、重复保留、预算改写不再包装成新家族。以上关系有可讨论的机制差异，但共用身份、字段比较、状态与时间原语；没有统计独立或未见语义保证。

公开合同注意点：邮件以实际 sent-store 对象为效果，不声称真实送达；受保护字段更新不能把 ignored false/zero 参数当成已发生的字段变化；日历按空查询取得全部记录，不能用只按 start-date 查询的一天视图漏掉跨日占用，canceled 记录需按实际状态过滤。日历存入后通知可能失败，错误不能推零效果。原子购票不允许用事后取消抹去第一次购票。

银行提案仍有一个显式未关闭门槛：对忽略参数/no-op，必须在最多一轮修订内明确操作许可与实际字段效果标签合同，不能复用“updated”即一切字段变更的规则。因此本轮没有批准其最终定义冻结。其他两项也须父级审核与用户决定是否扩研究范围，然后才能分别审查公共 schema、mutation 枚举、原工具效果 decoder 和 fixture 门槛。此处不实施这些步骤。

final_test 仅为生成前的暂定归属，当前没有 test fixture、轨迹、预期标签实例或模型输出。设计者已看见定义，不称未见任务；未来只能在独立持有、冻结流程成立时主张未用于调参的实例评估。若候选被拒，保留原文件和理由，不转成 train 或换名字重提。

本次只写本目录：4 份提案、split_intent.json、manifest.json 和本文。未创建 fixture/CPU 事件、未运行模型/训练、未改冻结文件或共享状态。没有可执行合格新 train 时，下一步是由用户决定扩大工具面，或保留当前单银行 train 的有限数据合同研究主张；不能自动执行原计划中的 12 个 CPU 事件。
