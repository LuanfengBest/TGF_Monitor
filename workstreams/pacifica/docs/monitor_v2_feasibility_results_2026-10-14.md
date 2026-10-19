# Monitor 数据与训练可行性：阶段结论

本轮有限工作已把下一步收敛为一个研究范围选择：建议将 monitor 覆盖面扩到银行与旅行工作流，再建设独立家族数据。当前没有理由立即大规模微调，也没有证据证明换更大模型就能解决问题。暂不扩批，等待范围决定。

这次完成的是工程与数据可行性检查，不是新模型成绩。本轮0新增模型调用、0 GPU分配、0新模拟mutation、0训练；此前658次集群调用、18588主要GPU秒的累计口径不变。

## 已完成的工程检查

新增独立的 scripts/monitor_contract_v2.py，复用原字段检查器但不改冻结代码：从严格因果前缀定位来源、按来源角色取回原文、校验调用与返回ID以及选定对象字段，最后检查执行/授权/结论三字段的一致性。原文由程序取回，避免把模型重述当成原文。

9项边界测试在本地与Bouchet均通过，包含重复调用ID、未来/私有字段、两次相同取消返回文本错绑对象、thinking冒充事实或授权、未知效果错误判safe、技术拒绝不撤销许可，以及重复JSON键/非有限数字等。检查结果仅表示具体机械条件满足；binding_verified、mechanically_consistent 均不是完整授权证明，错误的授权字段仍需语义审查。未接入旧模型重新推理，也没有离线“修好”旧答案后重算分数。非盲AI只读代码复核的结论及局限单独保存。

## 数据家族审查与范围选择

本轮只提出4项，保留原稿并最多修订一轮，没有新增fixture、轨迹或test标签。每项与11个旧机制逐项比较；共享的身份、状态和时间原语仍存在，不主张统计独立。

|候选|预分组意向|判断|
|---|---|---|
|行程邮件的允许字段投影|train|可以审查信息披露边界；这是旅行工作区通信任务，不能包装成新增购票家族|
|银行既有预约的字段保持|final test|新关系是前后状态仅允许指定字段改变；须明确有效变化/no-op/协议偏差，不能复用旧success即效果的规则|
|旅行日历的全量区间排斥|final test|检查整个有效占用集合，含跨日情况；这是日历任务，须扩大当前动作审计范围|
|两张票原子提交|train候选，拒绝|原工具每次即时创建一张票，没有原子提交；不能用事后取消抹去中间违规|

邮件、预约更新和日历工具已在上游原环境注册，工具并非不存在。但当前冻结实验只审计 schedule_transaction / buy_flight_ticket / cancel_flight_booking。增加这些动作会改变事件覆盖、执行效果合同及报告的研究范围；因此需要用户决定是否从付款/购退票扩成工作流monitor。这是研究定位选择，不是登录、上传或普通代码修复的权限请求。

本轮没有通过当前范围内的新增航空train，也没有已冻结的最终未见test。不能因此断言所有未来候选都不可能；只能说这4项没有填平缺口。旧development、bank pool train以及quorum/retention validation保持原组。5条已有train配对仍是非盲AI候选，不是人工金标或训练完成。最终test目前只有提案，未生成、未推理，设计者也已看过定义，不能夸称完全未知任务。

## 底座、长度与资源

候选可训练底座记录为 Qwen/Qwen3-32B，固定修订9216db5781bf21249d130ec9da846c4624c16137，与已有HF tokenizer来源一致。只获取约59KB的配置和权重索引；17个权重分片的数据合计65524246528字节，约61.0GiB，未下载权重。来源：[官方固定修订](https://huggingface.co/Qwen/Qwen3-32B/tree/9216db5781bf21249d130ec9da846c4624c16137)。这不是GPU训练显存估计。

5条候选按当前JSON文本计算，输入1509–1678 tokens、目标3740–4477 tokens，合计5249–6155，不含chat模板；10段文本的HF/native token IDs完全一致。这只验证这些文本，不能证明所有输入或模型权重/后端等价。当前目标是详细审核草稿，后续需明确面向模型的简短证据输出合同；不能直接把全部审核metadata当训练目标。

旧Ollama Q4_K_M与HF BF16/NF4底座的精确权重等价尚未证明。未来微调对照必须使用同一固定HF修订、tokenizer、模板、输入/输出合同、量化方式、backend和解码设置，分别关闭/启用adapter比较；不能只拿旧GGUF成绩当未训练对照。QLoRA需要可训练的附加参数与准备步骤，现有GGUF缓存不等于训练checkpoint。[PEFT官方量化说明](https://huggingface.co/docs/peft/developer_guides/quantization)。

CPU作业29493425和29493455均完成。默认getquota未找到课程账号组（失败保留），按提示指定-g hpcllm成功：00:00快照project使用46/4096GiB，scratch使用59/10240GiB；文件数分别42772/5000000、28049/15000000。组配额当前有余量，不能据此预留未来空间；OOD页面仍显示10月2日的Roberts存储紧张提示，组配额并不保证底层存储健康，下载大权重前还须重新核实；scratch按30天清理规则保存，正式产物另留项目目录和本地。[Yale配额说明](https://docs.ycrc.yale.edu/data/hpc-storage/)。

远端venv仍缺torch、transformers、peft、trl、bitsandbytes、datasets、accelerate，默认HF缓存未见Qwen3-32B，未做全盘搜索。gpu_devel列出RTX5000Ada及其他卡型，但课程账号实际可分配性、等待时间和显存/梯度仍须后续验收，不能从分区列表声称大卡已可用。已用过的RTX5000Ada32GB推理成功不等于约6K序列训练可行。本阶段未安装训练栈、未下载大权重、未申请训练GPU。

只读作业29493425的sacct分配为6 CPU作业秒，29493455为7 CPU作业秒；收尾验收29494474完成（UI不足1分钟，精确时长未另查），均不能计成GPU成本。此前收尾29490480补齐为7 CPU作业秒。CPU作业秒指墙钟分配时长，不是CPU核秒。最近Your Jobs实时查询为空；无模型服务新启动。

## 可执行的下一步选择

建议选A：把目标明确为“银行与旅行工作流的已执行越权monitor”，增加对信息披露与状态修改的覆盖。先只做一个新train家族的独立adapter/效果合同/fixture审核，再冻结最多6次CPU尝试（实际mutation不超过6个，含失败/no-op，每例一次且不重试），0模型调用、0GPU、0训练；银行与日历test候选只保留定义，不能用于选择训练材料。具体顺序和门槛见本轮修订目录中的下一批方案。这里的6次是建议的下一阶段新预算，未执行，不在本轮偷偷续批。

选B则保留付款/购退票的窄范围，先交付有可靠原文与拒判路径的原型，研究主张限于已有家族上的诊断和工程可验证性；不以当前5条数据和缺失最终test支持广泛微调收益。后续若要训练，应另找可信独立数据来源，不能重新命名旧验证例子补数量。

无论哪项，都还不能直接启动SFT。数据资格通过后，再提出明确的权重下载、隔离运行环境与单批显存/梯度试验计划。当前阶段不批准这些后续资源动作。

## 复现入口

- analysis/monitor_contract_v2_tests_20261014.json：9项测试与源码SHA。
- analysis/monitor_contract_v2_review_20261014.json：AI代码审查及窄合同限制。
- data/training/monitor_v2/family_proposals_v4/：4份原稿、来源hash和未通过原因。
- data/training/monitor_v2/family_proposals_v4_revision1/：唯一修订及下一批范围方案。
- analysis/monitor_v2_train_length_readiness_20261014.json：逐候选长度和token对齐。
- data/model_manifests/qwen3_32b_train_candidate_v1/：官方小型元数据，非权重。
- results/monitor_v2_runtime_readonly_20261014.json、results/monitor_v2_runtime_supplement_20261014.json：原始只读检查含失败。
- analysis/monitor_v2_runtime_readiness_20261014.json：提炼后的资源判断。

38份文件收尾同步已通过，CPU29494474完成，冻结baseline verify与9项测试全部通过；receipt为results/monitor_v2_feasibility_closeout_receipt_20261014.json（SHA 94da6f9a7e71ddd82bf5a9778ea99dfcd5b62eec9626635c8f096a62aa47ff7d）。随后Your Jobs / All Clusters为空。阶段邮件已发本人（SENT，ID 1a138c0c005044ff），回执results/monitor_v2_feasibility_email_receipt_20261014.json；自动续办final-project-monitor已PAUSED，工具与配置确认，回执results/monitor_v2_feasibility_automation_pause_20261014.json。这里不是整个final project已完成。
