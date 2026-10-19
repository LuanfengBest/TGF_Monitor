# 27B非思考配置：一次有界补充诊断

首次推理前冻结，尚未提交。本轮动机来自29457835的c01_full原始响应：它在6144输出token内已经反复得出1695/22.5，却未结束思考并交付JSON。不能把这一失败直接解释成不会算。该条仍按原协议记cap失败，不从推理文本补造答案、不重记正确。

同一Qwen3.5:27b digest、同一13个原始允许输入、SYSTEM、schema、seed42、32768上下文与6144输出上限。使用官方enable_thinking=False模板（关闭think区块）与请求think=false。采样为官方non-thinking general：temperature.7/top_p.8/top_k20/min_p0/presence1.5/repeat1、窗口32768。模式与采样共同变化，只比较部署配置，不把结果单独归因于关闭思考。

[官方固定版本设置](https://huggingface.co/Qwen/Qwen3.5-27B/blob/fc05daec18b0a78c049392ed2e771dde82bdf654/README.md)。不增加新模型候选，不启用facts，不改已有结果，不进行更多自动参数搜索。

预算：最多15generate（647/22123输入两次16-token校准+13题），20分钟单卡GPU，runner1040秒/外层1140秒；0重试。每次精确计数，禁止截断/shift，身份与hash异常即停，连续2次cap或解析失败停。先等当前thinking作业结束并核验生命周期，再提交此独立stage。只有本轮符合工程门槛且语义审查通过，才能讨论晋级，不能从正确片段代替完整输出。

准备检查：13输入逐一匹配固定官方Jinja非思考模板；实际输入和校准均在容量内；请求think=false；3脚本编译通过。没有宣称模型已运行。

入口sbatch scripts/monitor_27b_nothink_v1.sbatch；配置configs/monitor_27b_nothink_v1.json；结果results/monitor_27b_nothink_v1_JOBID。离线scripts/analyze_monitor_27b_nothink_v1.py先完整性核验再评分。训练仍未开始；标签独立复核分工已向用户询问。

## 实际结果更新

29461498已完成并完整回收；397 GPU秒，13任务尝试/12解析/6核心通过，短例4/8，不晋级。细节见[本轮结果](monitor_iteration_results_2026-10-13.md)。冻结配置/脚本/原始输出未改。
