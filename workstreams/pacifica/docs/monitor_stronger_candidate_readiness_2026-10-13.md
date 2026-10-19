# 单个更强候选：部署准备

## 当前状态更新（2026-10-13 19:30 EDT）

缓存作业29447985已完成，全部blob哈希/大小通过；GPU作业29457835已实际加载该27B，短/长校准输入计数分别1389/1389、22125/22125，校准后显存19130MiB/32760MiB、全部65/65层在GPU。部署可运行已得到实测支持，模型任务正确性仍在有界对照中，不能据此认定训练可行或候选胜出。当前结果和后续状态见[交接指南](team_handoff_2026-10-13.md)与[状态入口](../STATUS.md)。

以下保留最初的元数据研究与提交前记录；其中“尚未”描述的是当时状态。

## 最初准备记录

2026-10-13，仅元数据研究，尚未下载权重、未跑GPU、未冻结下一轮推理协议；不能称资源验证完成。当前唯一实际运行的是事实层对照29447280。

下一候选拟限定 Qwen3.5:27b Q4_K_M。官方registry返回qwen35/26.9B，全部层约17.48GB（十进制），manifest SHA256 64ae5b1d651fb2709d5928ccb8dcfb4bb2cc9c2c8001ac34497e36a6cf905b59。配置requires Ollama0.30.0，已有独立0.40.3满足版本要求，但27B仍须实际加载及精确输入计数预检。[官方分发页](https://ollama.com/library/qwen3.5:27b)

HF固定revision fc05daec18b0a78c049392ed2e771dde82bdf654；官方27B配置64层、每四层一个full-attention层、4KV heads、head_dim256。32768上下文的FP16 full-attention KV按该配置估计2GiB；这不包含linear状态、计算图、运行时和其他缓冲，不能作为实测显存。tokenizer_config与chat_template逐字等同本项目9B固定版本，词表仍需单独核验。[官方模型配置与推荐设置](https://huggingface.co/Qwen/Qwen3.5-27B)

选择理由是作为当前9B失败后的单一较大候选检验；官方通用基准不能证明它在本monitor任务更好。仍维持现有工程输出预算进行部署组合比较；若预算内不能可靠完成，停止，而不是无限增加推理或候选。采样、请求数、GPU时间、失败停止条件应在后续预检前另行冻结。

Bouchet 17:10附近df显示scratch约10T可用、project约4T可用，排除了文件系统整体空间不足，但未核验个人配额。下载前还应检查用户配额，使用单独CPU下载作业，哈希校验所有blob，保留旧缓存。之后单卡实测显存和最长输入，技术通过才进入同材料能力比较。

机器记录 analysis/monitor_stronger_candidate_readiness_20261013.json；下载的元数据在 tmp/stronger_candidate_research_20261013/。尚未将此候选当作已选胜者或训练底座。

## 后续缓存准备已冻结（尚未提交）

新增 configs/monitor_27b_cache_v1.json 及 scripts/prepare_monitor_27b_cache_v1.py/.sbatch：仅下载/校验，education2CPU/4GB/20分钟、0推理、0重试，独立scratch目录tgf_candidate27b_models；已有同digest blob先校验再只读复用，旧tag不覆盖。getquota返回课程用户未找到quota group，个人配额未确认；脚本检查文件系统空间并在写入错误时停，不宣称配额已验证。

27B tokenizer.json、tokenizer_config.json、chat_template.jinja均已核验与固定9B版本逐字一致；元数据已保存在data/tokenizers/qwen3_5_27b/，provenance保留准备时状态。GPU预检与能力比较尚未启动。
