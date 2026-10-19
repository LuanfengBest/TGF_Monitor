# 用户批准的运行预算调整 v2

2026-10-14 22:54 EDT，用户直接回答“同意调整预算，继续跑（推荐）”。完整问题与回答保存在results/sft_runtime_budget_approval_20261014.json。此次批准两训练各75分钟、固定评估210分钟、主机RAM96GiB；含原预检配额总380 A40分钟，后续最多360分钟，0额外预检/0自动重试。

原预检29594960的failed/eligible=false不改。analysis/sft_technical_qualification_v2.json独立绑定真实批准、原始预检receipt、数据manifest、原plan、权重receipt与技术指标。新资格门槛重新检查两有限loss与梯度、相同初始化、LoRA参数量、loss mask、零重载差、显存及新时限；只允许原来的纯时间断言失败，不可借此绕过其他失败。没有新模型调用或梯度步骤。

运行器v2与v1保持科学函数AST相同：模型加载/量化/LoRA、tokenizer、mask、optimizer、梯度、推理与评价循环均相同。训练只替换前置资格读取；其后数据选择、随机顺序、128微批、16更新、seed42、2epochs、最后checkpoint以及失败保存逐语句保持一致。评分只改读取v2输出目录，语义合同沿用输出前已冻版本。

独立输出results/sft_three_arm_v2，不覆盖v1。单A40/4CPU/96GiB，使用正常gpu分区；训练内部4350秒、外部4430秒、Slurm4500秒，评价内部12450秒、外部12520秒、Slurm12600秒。来源与真实批准hash冻结后执行scripts/submit_sft_stage_v2.py ordinary_sft；完整成功再evidence_sft，再evaluation。各阶段唯一提交回执、队列空与前阶段完整2epochs检查；旧v1不得存在效果训练尝试。任何失败停止，不改变数据/模型/配方或静默扩大预算。

24final一次性主结果、12validation独立报告，不选checkpoint/prompt/seed。预检生成不作为性能证据。base/ordinary/evidence仍共同输入、schema和最大1024输出tokens；引用格式不等于实质支持。数据与方法范围仍为程序+非盲AI的合成指定事件组件pilot。
