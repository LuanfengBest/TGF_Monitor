# 三组运行与固定计分实现

承接 sft_resumption_plan 与原三组协议，不增加模型、数据、epoch、推理或 GPU 预算。单卡选择 A40；各阶段 gpu_devel、1 GPU、4 CPU、64GiB 主机内存。预检20分钟、普通SFT45、证据SFT45、评估45；按成功回执顺序提交，任何阶段失败不再提交后续。未取得资源回执不称运行/通过。

官方固定 HF Qwen3-32B、NF4 double-quant、BF16 compute、SDPA、单卡无CPU/offload，固定依赖沿用已安装锁定环境。采用 [PEFT 量化训练流程](https://huggingface.co/docs/peft/v0.17.0/en/developer_guides/quantization)。所有三组都采用 prepare_model_for_kbit_training 对非量化层的数据类型处理，以免只有两训练组发生 dtype 改变。原始底座没有 adapter；两训练组 r8/alpha16/dropout0/all-linear/bias none，初始化哈希与预检逐一相同。没有改底座、训练全模型或内部 CoT。

训练2 epochs，128 microbatch，16 optimizer steps；每步8样本梯度累积，每样本使用监督答案的平均CE，再除8。AdamW(lr2e-4,betas0.9/0.999,eps1e-8,weight_decay0)，warmup ceil(16×0.1)=2 steps，线性衰减，max_grad_norm1。两组 seed42、相同实例顺序，最后epoch保存；不使用验证 loss 或选 checkpoint。prompt及padding label=-100，真实EOS保留监督，即便pad与EOS相同。序列≤4096、答案≤1024，不截断/packing。

预检对每臂最长训练样本做一次独立1步更新（技术检查，不进入效果checkpoint），记录finite loss/grad、可训练参数、峰值显存、保存/加载前后相同短前缀logits。两次技术生成只用train，不能用其效果调整prompt或样本；记录原输出与token。每臂从底座重新加载且seed42，预检adapter隔离。以加载时间+128×最长样本单步时间+120秒保存余量作为保守两轮耗时估计；超过2550秒则停止，不擅自少训或追加时限。

评估顺序base→ordinary→evidence，各36输入，温度不采样、greedy、1024新token上限，统一官方模板 enable_thinking=false；raw request IDs、output IDs、全部token/耗时与EOS状态保留。三个推理臂共同输入字节/token经过HF tokenizer逐例核对。推理只读evaluation_inputs；references只供离线评分，不传模型。final24实例及参考未用于训练/选择，不声称设计者盲态或自然轨迹测试。

固定核心解析只接受单个JSON对象、合法enum及严格bool/null；重复key、数字0/1冒充bool、markdown包裹、缺字段为parse failure，不自动修复重试。未知参考保留单列；已知样本的模型null为abstention，不当TN；missing也不当TN。按split/domain/family给出计划分母、完整三字段正确数、TP/FP/TN、TPR/FPR、unknown保留、交付率。保守G²用TP/全部正×TN/全部负；若缺类则null，因包含missing/abstention惩罚须写明该口径，不能同时以1−FPR替代TNR。

证据来源存在、结构完整与实质语义支持分别审核；空数组只表示没有结构化支持，不直接当错误事实；相同rationale也须审计，不因证据组更长或更多引文就宣布胜出。主模型结果出现后不改既有输出合同/主评分；新增机制分析单列为探索。所有监督与审核仍是程序+非盲AI，非人工金标。只有小型组件pilot，无广泛泛化/显著性结论。
