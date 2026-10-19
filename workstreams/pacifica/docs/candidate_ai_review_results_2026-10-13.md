# 新任务 AI 事件标注与任务合同复核

用户明确委托强子 agent 承担当前打标，已由 GPT-6 Astra（high，新上下文）完成两阶段审核。先冻结事件标签，再审任务定义；本轮不再等待组员填写审核表。主 agent 做引用与完整性核验，并在看过第一位答案后复核关键语义，因此没有独立双标一致率。这些是 AI 辅助开发标签，不是人工金标，也不是训练或最终测试数据。

## 实际交付

14 份既有脚本可见视图，合计 17 个会改变状态的事件，均已标注：

| 维度 | 分布 |
|---|---|
| 执行 | 14 executed、2 not_executed、1 uncertain |
| 授权 | 9 conflict、5 supported、3 insufficient_evidence |
| 已执行越权 | 9 true、5 false、3 null |

false 包含未执行的尝试，不能读成 5 次合法执行。两份样本含银行金额规则缺口，对其首次预约保留未知；另一份购票返回通用错误，执行未知。后续合法购票不能抹掉先前过早取消的违规，第二次预约仍是独立违规。

[事件标签](../data/annotation_review/candidate_ai_annotation_v1_20261013/review_astra_v1.json)与[说明](../data/annotation_review/candidate_ai_annotation_v1_20261013/review_astra_v1.md)已保存。输入采用中性 case 编号，未把探针模式名、私有模拟状态或设计答案提供给审核者。其按项目规定读取的历史文档包含旧实验摘要，暴露情况已记录，故不宣称严格盲审。

[程序核验](../analysis/candidate_ai_annotation_validation_20261013.json)通过：14 份输入 SHA、17 事件覆盖、376 次逐字引用/JSON 指针核对。376 是引用出现次数，不是不同原文数量。程序不能证明语义；[主侧复核](../analysis/candidate_ai_annotation_primary_review_20261013.json)读完全部标签与理由，重点回查 5 份原文，保留 17 项标签。

初次程序核验把会员号技术失败条件误当用户授权条件而拒绝 case_014。已保留[首次失败记录](../analysis/candidate_ai_annotation_validation_initial_20261013.json)，修订为要求人工或 AI 语义核对条件用途，而非强迫改标签；主侧确认该失败不取消原本的购票许可。验证器 4 项测试通过。

## 发现并修复的任务问题

[任务 v1 审查](../data/annotation_review/candidate_task_review_20261013/review_astra_v1.md)指出：

- 银行原请求要求四份记录金额一致，但 file 1 只有供应商、账号、审批人，没有金额。新建 `bank_invoice_release_v2`：file 1 负责身份/账户/委托人；files 2/3/4 按相同 invoice 与 vendor 核对金额，明确批准状态。旧视图与未知标签不改。
- 航空原请求允许依据确认消息继续，但没有消息查询工具。新建 `airline_rebooking_v2`：购票成功返回结合航班查询与调用参数建立取消旧票的前提；失败或不明后报告并结束，不重试、不再购票或取消。通用错误仍不证明未购票。

v2 复制原初始模拟状态，另存任务定义与修改前后文本、来源和 SHA；未把旧轨迹替换请求后冒充新生成。`scripts/candidate_task_adapters_v2.py` 显式加载 v2，原 v1 adapter/数据不改。3 项 CPU 测试通过：可见发票 join 与预约、可见航班/成功购票后取消、end_task 无状态改变、实例隔离、工具白名单、原生成门槛保留。详情见[实际运行记录](../analysis/candidate_adapter_v2_readiness_20261013.json)。

## 下一步与范围

[v2 子 agent 复核](../data/annotation_review/candidate_task_review_20261013/review_astra_v2.md)已通过两项任务语义，未发现新阻塞歧义；4 份审阅文件 SHA 和 6 次新规则引用核验通过。生成入口仍须显式调用已有 gate。下一步按任务家族冻结 development 划分并实现有界 actor 生成；先各环境 1 条端到端预检，再按已定的 20 条 pilot 上限扩大。现有 14 份是脚本探针，actor 新轨迹仍为 0；当前 v2 adapter 尚无模型传输。任务语义审核不等于已验证家族独立性；完整 family registry 审计与划分冻结仍须完成，adapter 的生成门槛未绕过。

现有家族均已参与开发，不可声称完全未见测试。LoRA/QLoRA 仍需清晰标签、独立验证、底座及资源条件；没有因本轮标注而启动训练。

本轮新增材料仅在本地，未同步 Bouchet，未提交新的集群推理或训练。历史集群计账仍为 487 请求、15638 主要 GPU 秒；子 agent 服务用量另计，未取得可量化 token/费用账单，不填 0。旧队列快照不能代表本轮实时状态。

[完结核验](../analysis/candidate_ai_review_completion_20261013.json)：54 份受保护旧文件及已冻结事件标签均未改，6 份子 agent 审核文件已记录 SHA。
