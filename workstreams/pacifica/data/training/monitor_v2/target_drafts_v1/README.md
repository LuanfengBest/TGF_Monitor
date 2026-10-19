# Pool 监督目标草案 v1

仅整理既定 train 的 3 份公开 CPU 脚本轨迹、5 个原有事件：1 true、3 false、1 null。没有使用 quorum/retention validation 事件作目标，没有改标签、生成变体或扩增计数。全部 `training_eligible:false`；0 模型调用、0 训练。

作者为参与任务/fixture/合同测试和原标注的同一 AI：非盲审、非人工金标、非独立双标。目标保留 execution/authorization/violation、6项必要许可条件、逐字 JSON pointer 引文、当前调用/返回绑定、初始与先前成功 commitment 的精确金额项。override 技术拒绝单列，不与授权冲突混淆；通用错误的执行和越权保持 uncertain/null。

`prospective_total_if_current_executes_usd` 是许可计算，不能当作实际效果。case_003 即使此前已知故障设计，也保留 `observed_total_after_usd:null`。case_001 第二笔累计1040越界；case_002 首笔未执行后第二笔累计620。

每个目标保留原视图/标签 SHA、原标签 pointer 和目标返回 cutoff，并记录规范化因果前缀 SHA。原视图文件含后续动作，未来 exporter 必须只取指定前缀；本草案不是可直接交给训练器的输入文件。全部 245 条目标引文已逐字核对且不晚于目标返回，5个核心三元组与冻结 AI 标签一致。

当前没有新增标签争议；缺结果报告/部分流程提前结束已与事件授权分开。5个相关脚本事件只足以检查目标数据合同，不能据此启动微调或宣称双环境覆盖。下一门槛是目标/证据复核、因果输入导出及训练格式/预算定义，validation 保持隔离。

## 已物化的因果配对

`causal_pairs.jsonl` 恰好包含上述 5 条 `{input,target,metadata}`，每条 input 只有原始 `user_request`、`policy` 和截至该目标工具返回（含该返回）的 messages。没有额外 prompt/system、未来消息、私有状态或参考标签；元数据完全在 input 之外。target 是原草案中对应的 target 对象，未改写，unknown 仍为 null。

`causal_pairs_manifest.json` 绑定原视图、原目标文件、规范化 input/target、每行（含 LF）及整个 JSONL 的 SHA256。已读回核验 5 条原前缀/目标完全一致，消息准确停止于目标 return，call_id 对应，均属既定 train，没有扩增或跨 split 混入。

这是可审计的候选配对数据，不是训练批准或可直接运行的 SFT 配置；全部 training_eligible=false。仍需单独确定模型格式、token预算、loss mask、目标/数据质量门槛及训练授权。原 `train_pool_targets.json` 和冻结来源没有修改。
