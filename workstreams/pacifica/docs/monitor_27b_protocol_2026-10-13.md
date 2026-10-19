# 唯一较强候选：27B v1冻结协议

2026-10-13准备；本协议在首次推理前冻结。沿用13个原始开发输入、SYSTEM、schema、seed42、Qwen3.5官方general-thinking参数及6144输出/32768上下文；不加execution_facts。原9B和Qwen3结果保持原样。本轮比较实际部署组合，不能把差异单独归因于参数规模。

模型qwen3.5:27b Q4_K_M，digest 64ae5b1d651fb2709d5928ccb8dcfb4bb2cc9c2c8001ac34497e36a6cf905b59。HF revision fc05daec18b0a78c049392ed2e771dde82bdf654。使用独立官方Ollama0.40.3及独立缓存；缓存29447985已完成、每blob大小/hash验证。启动核查完整运行时inventory、模型manifest及缓存结果/文件大小；不改旧cache/tag。

最多15次generate：混合Unicode/JSON校准1389输入、长输入校准22125（均16输出），再按原顺序13题；每次必须与HF精确token计数相等，禁止truncate/shift。技术、身份、完整性异常即停；连续两次任务cap或解析失败即停；不按正确率中途删题、重试或改配置。校准后的/api/ps与nvidia-smi观察记录实际部署内存和加载信息，不额外生成。GPU单RTX5000Ada32GB/4CPU48GB/30分钟，runner1640秒；超时保留部分结果。禁止重复reservation。

6144输出是部署预算，低于官方常规32768建议；若输出耗尽，只能说明当前预算组合失败，不能外推无限预算下模型能力。[官方固定版本说明](https://huggingface.co/Qwen/Qwen3.5-27B/blob/fc05daec18b0a78c049392ed2e771dde82bdf654/README.md)

入口：sbatch scripts/monitor_27b_v1.sbatch。配置configs/monitor_27b_v1.json。结果results/monitor_27b_v1_JOBID/，日志logs/monitor_27b_v1-JOBID.log。离线scripts/analyze_monitor_27b_v1.py核验再评分，private_reference只在离线评估侧使用。训练未启动；不添加第二个更强候选。

本地2测试通过（官方模板/完整容量、身份/输入隔离与旧对照字段一致），3脚本编译通过。尚未提交时不得把它记为运行成功。

## 实际结果更新

29457835已预算停止并完整回收；1686 GPU秒，5任务尝试/3解析/2核心通过，8未尝试，不晋级。细节见[本轮结果](monitor_iteration_results_2026-10-13.md)。冻结配置/脚本/原始输出未改。
