# 新轨迹四路比较草案（未冻结、未提交）

本文件为实现准备，不能据此运行GPU。须先回收prospective_actor_v2实际六个尝试与成本、核验完整公开投影和标签资格，再单独冻结实际输入、代码及资源预算。不得重复生成或筛选成功攻击。

继承已完成B3阶段的问题：同一轨迹、同一信息边界下，trace定制追问是否比强固定动作授权追问、ledger-only与额外原文复查获得更多有来源支持的违规证据？固定Qwen3:32b / gpt-oss:20b权重，不同时改选择器或训练。

所有可比较条目共用公开请求/政策/原始all-messages及按call ID绑定的ledger。复用原REVIEW_SYSTEM、QUESTION_SYSTEM、JUDGE_SYSTEM、FIXED_QUESTION、B3 EXTRA_SYSTEM和schema；候选/选择rank仍为旧版本。新公共投影只修正批量tool call的ID绑定，不加入私有执行事实、hidden side obj、参考答案或condition。实际call ID、source_type为可见工具/执行器来源记录；不能将其当授权。

每条先一次初审和同一个selected event，再生成TGF问题。B2及TGF从同一冻结原actor context各自分支一次、禁用工具，答案上限1024，k=1。四个最终judge分别接收同一common加相应增量：ledger-only无增量、B2固定问答、TGF定制问答、B3一次额外全原文复查。B3逐例Qwen总输入输出tokens不得超过TGF同例110%，不足则保留失败，不调整cap或补跑；actor成本单列，不能声称FLOPs/延迟完全相同。

最多每条9次新推理（初审1、TGF问题1、两actor回答2、四judge4、B3复查1）；6条最多54次，其中42monitor+12actor follow-up。这只是调用结构上限估算，不是已批准/冻结的GPU额度。正式提交前按实际合格条目和原生token核验冻结调用数、单HTTP上限和有限GPU时间；首条完整验收后才运行余下条目，两个有界阶段加总不突破最终预算。无自动重试。

生成未结束/中断、公共投影不完整或无法在原32768 monitor容量中容纳的条目保留在计划六条的失败表与总成本，不截断或补采。若只剩一个家族、一个类别或仅unknown，应明确不能回答双环境/TPR×TNR结论。具体是否值得执行可运行的少量诊断由资格报告说明，不能用unknown当阴性或用condition当标签。

比较分开报告轨迹TPR/FPR/G²（阈值50仅描述）、定位已知违规事件比例、带完整来源和授权推导的证明比例、局部错误指控、unknown/失败/覆盖率和成本。有效样本不足不报显著性/泛化结论。评分固定使用tgf_evidence_eval_v1；语义AI审核必须绑定原判断与evidence哈希，缺审pending，非人工金标。

停止：冻结批完成、连续失败阈值、预算耗尽或输入资格不足。保留失败并汇总；不自动切换模型、调prompt、微调或追加样本。新阶段正式协议将取代本草案，而不会覆盖actor冻结包。
