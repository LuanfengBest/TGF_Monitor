# 职责拆分接口对照 v1

## 当前进度与这轮问题

既有选型、事实层配对及三例AI证据复核已完成。事实层改善指定执行事件判断，但合法充值仍被误报，旧报告还存在引文失真和金额越界。9B与27B本轮未晋级，尚未训练。三例复核中两例建议保留证据不足，一例全文支持充值；建议不是独立人工真值，旧参考与成绩保留。

本轮只问：同一Qwen3:32b、同一13个开发输入，改由程序负责执行事件、原文与算术后，授权判断和最终报告是否更可靠？新接口同时改变系统指令、输出schema、条件证据结构和报告组合，属于系统方案比较，不能把收益单独归因于某一个字段。

## 冻结边界

* 底座沿用Qwen3:32b Q4_K_M，digest `030ee887880fc378860c2dd35101da424377520441ae4bfe7be6deff8ade7840`；共享Ollama 0.22.0模块。thinking、temperature .6、top_p .95、top_k 20、min_p 0、seed 42，32768上下文、6144输出。
* 两组接收完全相同的13份原始sources和execution_facts。旧组请求等同之前with_facts；新组仅更换系统指令及由其规定的输出接口。新提示不包含私有参考、AI复核答案或具体案例解答。
* 共26次调用，0自动重试，一次单卡GPU作业最多30分钟。runner从预检起27分钟alarm，外层1720秒timeout；每组连续两次输出cap/无效schema停止该组，身份或精确输入计数异常立即停整轮。
* 顺序在运行前冻结：c07、c08、c06控制在前，其后c03短/全、c05短/全、c04短/全、c02短/全、c01短/全；每个输入交替先运行哪个接口。控制调用计入26，不额外加免费校准。每一次实际输入token都须与本地原生计数完全相等，不截断、不加容差。
* 所有请求、原始thinking/response、解析失败、费用未知与取消缺失token均保留。唯一reservation阻止重复提交；不因结果差而自动改prompt或增加seed。

## 新接口的职责与限制

模型只给授权关系、许可来源ID、适用条件及条件来源、缺失证据、金额项与分摊分母、简短理由。程序从同一原始输入重建目标事件，计算金额/分母之和及差额，按ID附整段原文；模型不能写执行状态或拼接引文。条件未知与schema错误分别记录；没有把unknown自动转换成safe。

模型仍可能漏列条件、选错证据或分母。source ID存在、条件字段齐全、算术正确均不等于语义正确；report中明确保留authorization_semantics_verified=false及arithmetic_inputs_grounded=false。

计划控制c06的程序结论仅表示所给摘录中没有付款调用。该分支只允许目前核验的get_unread_emails读取工具；陌生工具或找不到显式事件时保留uncertain。预约只证明创建预约，named operation的失败不能证明所有副作用不存在。本轮不是全轨迹自动发现评测，也不扩展执行工具合同。

## 预先确定如何看结果

1. **历史口径**：13输入全纳入，缺失/失败不算成功；报告旧参考下的原始字段符合度，以及经过各自程序核验后的可交付符合度。拒判单列，不当作合法正确。此项保留与历史可比性，但不证明标签无歧义。
2. **问题专项**：逐案查看c03_full的条件证据与误报；c03_short是否在短视图缺余额证据时保留未知；c01_short是否交代分摊假设而非编造唯一金额。后二者与版本化AI建议的符合情况单列为provisional，不改历史分数，不汇总为新的“金标准准确率”。c01_full不自动套用短例复核。
3. **边界回归**：c02/c08越权收款人、c07授权收款人、c05指定失败事件、c06计划未执行、c04可选付款渠道。人工语义检查这里由Codex执行并明确标AI，未取得独立人类审核。
4. **工程指标**：解析、cap、目标绑定、原文附件、金额范围、机械有效、明确结论/拒判、时间与token。新组原文由程序附加，旧组由模型复述，因此不能把引用匹配上升包装成授权理解上升；两组guard定义差异需随结果披露。

仅当c03_full误报纠正且上述清晰边界未出现新的漏报/误报，才将新接口作为下一轮新家族开发候选；这不是部署或泛化验收。若仍有清晰、重复的语义错误，登记为未来LoRA目标，先完成新任务家族与20条标注试验。训练数据、验证隔离、底座/显存门槛未满足，不启动训练。不再扩展模型搜索。

## 可复现入口

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_monitor_interface_v1.py' -v
.venv/bin/python scripts/monitor_interface_ablation_v1.py verify
sbatch scripts/monitor_interface_ablation_v1.sbatch
.venv/bin/python scripts/analyze_monitor_interface_ablation_v1.py results/monitor_interface_ablation_v1_JOB_ID --output analysis/monitor_interface_ablation_v1_JOB_ID.json
```

`prepare`只供首次冻结，已有configs/monitor_interface_ablation_v1.json时拒绝覆盖。结果目录与reservation已存在时不得重跑。实际Job ID、Slurm终态、hash及回收信息追加项目日志；不要把预检通过写成模型实验成功。

提交前修订记录：第一次本地冻结后核对历史metadata，发现集群模块名是0.22.0，但打包后的API实际报告0.0.0。首次冻结从未上传或提交，原配置另存monitor_interface_ablation_v1_prelaunch_rejected_20261013.json，完整源码封存在tmp/monitor_interface_prelaunch_rejected_20261013.tar.gz。修订2明确检查已观察的API版本，并核对四个模块二进制/包装脚本的已记录SHA；不是放宽模型或输入完整性核验。修订后重新冻结，GPU调用仍为0。


## 执行完结

29469519于21:02:52 EDT COMPLETED0:0，26调用、1188 GPU秒，原始155文件已回收核验；新接口不晋级。见[完整结果](monitor_interface_results_2026-10-13.md)。协议和源码hash未改，不重提。
