# 执行事实层配对诊断 v1

本轮目标：检验固定目标事件的程序事实能否减少模型错配事件、误判执行状态。用户已授权继续；旧协议、模型结果、输入和参考答案均不改。

## 设计与预算

沿用 Qwen3:32b Q4_K_M digest 030ee887880fc378860c2dd35101da424377520441ae4bfe7be6deff8ade7840，以及原 ollama/0.22.0-GCCcore-13.3.0-CUDA-12.8.0 模块。两组均 thinking/T=.6/top_p=.95/top_k=20/min_p=0、seed42、32768上下文、6144输出。同一13输入，每条依次 without_facts/with_facts；两组系统提示、输出schema和原始sources完全相同，仅实验组增加由现有可见sources自动计算的 execution_facts。旧结果仅作历史参考，使用本轮新对照。

最多26请求、30分钟GPU、0自动重试；任一身份/哈希/token计数异常停止全作业，每组连续2次cap或解析失败停止该组，剩余未运行项如实记录。最长输入21248，留6144输出及128保护余量，无截断。配置 configs/monitor_facts_ablation_v1.json 在推理前冻结。入口 sbatch scripts/monitor_facts_ablation_v1.sbatch；一次性reservation，不重提旧stage。

## 程序事实与核验

scripts/monitor_facts_v1.py 从现有来源重建可见调用/返回，保持原message编号；调用已有保守工具合同，输出指定事件的call/result来源、参数、执行状态与原文。它不读取完整原始轨迹之外的额外信息，也不读取private_reference、oracle/verifier或隐藏标签。短视图仍然是人工事后选择；不是自动检索。

两组使用相同离线guard，检查逐字引文、目标call/result引用、内部判定一致性、执行合同、金额维度及Decimal减法。未认证执行、错配、坏引文和金额不一致导致拒判，绝不把unknown写成safe。缺少付款调用仅记“所给视图未见”，不推出全轨迹未执行。预约是创建预约，不是资金结算。

机械检查通过不等于授权语义通过；金额减法检查不证明模型选出的授权金额有原文根据。此版本不自动选择分摊人数或重算授权金额，必须单独审核。原schema无target_id响应字段，目标绑定只通过call/result引用和观察金额核验，不能保证理由里完全没有混入其他事件。程序拒判和原始模型错误分别计分。

## 评估与限制

分别报告每组13题原始核心字段正确、execution正确、解析/cap、quote匹配、机械接受覆盖与接受后的错误；同输入配对列出改变，短/全分开。拒判不是正确；合法边界误报和未知单列；先看原始判断变化，再看guard拦截了什么。仍是一个旧bank开发家族、指定事件诊断，不是部署安全保证或独立泛化分数。

六项本地测试通过：旧短/全target事实一致且sources不变；失败与重试分开；错误事件引用/金额拒绝；未知返回不被actor解释改写；NaN/算术/伪造引文拒绝；禁止标签字段/重复source。未观察模型结果前不宣称收益。

## 运行中的检查点

29447280 于17:09:19 EDT提交，17:10:09开始分配；最初PENDING/Resources，随后RUNNING。第一次加载103秒，GPU65/65层、设备日志总内存27.1GiB；17:13:45首个generate返回HTTP200。日志快照 logs/monitor_facts_runtime_check_29447280.txt（远端）。模型分配4CPU，但共享runner记录NumThreads48；保持与本轮两组相同，不中途调参数。

离线历史guard检查 analysis/monitor_facts_historical_guard_20261013.json：旧thinking13答案机械接受0/13，连核心正确答案也因引文/范围/金额不完整被拒；这说明当前guard没有足够覆盖，不能称产品已可靠。新配对结果另算。评估脚本另有2项测试通过：篡改请求/虚假完成会拒绝，正确但被拒的答案不算接受成功；未更改冻结运行代码。

当前target解析器只支持显式event ID，以及本13输入中的单个payment控制；任意自然语言target尚未验收。部署前需明确结构化target selector及源文本完整性约定，不能把此诊断接口直接暴露为通用审计服务。
