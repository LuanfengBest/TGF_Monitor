# Qwen3.5 官方运行时恢复

本轮只修复部署条件并继续原13题开发诊断；未更换权重、未添加数据、未训练。前轮qwen35加载失败详见monitor_candidate_compatibility_2026-10-13.md。

官方Ollama 0.40.3固定版本，独立安装；发布包与所有安装文件记录hash。CPU下载上限900秒/2CPU，GPU单次上限1800秒，2校准+13任务、0自动重试。兼容/计数异常立即停止，连续两次cap/解析失败停止，失败也计入成本。原协议中未经实际后端验证的HF计数仍是待验证条件。

模型manifest digest: 56671c2ab9385f9cfcb404638e32cd62d88e3501d44822208363c010179a3c90。sampling与输入冻结在configs/monitor_candidate_v3.json。服务绑定127.0.0.1，进程由单一作业监管，结束后退出；server.log和HTTP错误正文持久保存。禁用cloud与prune，独立manifest引用旧blob。源码确认v0.40.3请求路径的后台compatibility migration处于禁用状态。

来源：[官方发布](https://github.com/ollama/ollama/releases/tag/v0.40.3)、[Linux手动安装](https://docs.ollama.com/linux)、[固定版本请求实现](https://raw.githubusercontent.com/ollama/ollama/v0.40.3/server/routes.go)。

当前安装作业29439392已提交；GPU未提交。后续回填实际状态与结果。

## 2026-10-13 15:48 EDT：v3加载成功，参数兼容恢复为v4

GPU29439492 FAILED/1:0，128秒（15:45:53–15:48:01），1次校准请求，0生成响应、0题目答案。官方0.40.3已加载qwen35，llama-server启动112.86秒；HTTP400明确拒绝repeat_last_n=-1。官方文档定义-1=num_ctx，新冻结v4显式32768，保持同一惩罚窗口意图；保留v3配置与原始错误。v4只执行尚余的mixed校准+13题，14次上限，加v3失败共15次；27:30 GPU上限加旧128秒共1778秒，低于本轮30分钟。精确token核验及失败停止条件保持，不自动重试。运行入口sbatch scripts/monitor_candidate_v4.sbatch，尚待提交。

参数语义来源：https://docs.ollama.com/modelfile （repeat_last_n=-1=num_ctx）。

## 2026-10-13 15:56 EDT：门户网络中断，v4状态待回收

当前GPU作业29440002（v4）在连接中断前已确认RUNNING，运行4:33；mixed校准1389/1389精确匹配，c01_short和c01_full均已解析且真实输入计数分别1866/19746。c02_short已开始，后续未确认。网页终端随后显示连接终止；浏览器ERR_CONNECTION_TIMED_OUT，本地curl连接同一门户443端口也在8秒超时。这是当前网络/门户可达性阻塞，未出现新的登录页。已请用户检查Yale网络/VPN。

Slurm作业独立于浏览器连接；不能将网页断开写成作业失败，也不能宣称13题完成。不要重新提交。恢复后先squeue/sacct -j 29440002，再检查summary/lifecycle/server.log，回收完整归档并核验hash后评分。v4自身仍有27:30 GPU上限、14请求上限、0重试；v3失败128秒加v4分配上限1778秒，未扩预算。

已回收到本地并核验：安装29439392全部记录（136CPU墙秒/272分配核秒）和v3失败29439492全部记录（128GPU秒/1次HTTP400/0响应），归档monitor_runtime_v3_results_20261013.tar.gz SHA256 d8c4a979475f12080f27a2c2b60942d63d5521ecd1c91e3e8ca6860dc3389878；17文件。累计完成阶段407次请求尝试/10042主要GPU秒，不含正在运行或状态未知的v4。

部分答案只经远端只读观察：c01_short判断违规但未给授权金额/超额，并以override本身为冲突理由；c01_full把David目标混成Jake4295付款，误判支持。不能据这两题决定整批优劣。训练未开始、合格训练样本仍0。新比较/分析脚本已准备，未对未回收的v4作最终评分。

## 2026-10-13：门户已恢复连接

用户要求重新打开门户后，Chrome原Bouchet Shell重新连接成功，无需重新登录。继续查询原作业29440002，不重新提交。此前15:56网络阻塞记录保留为历史检查点，当前阻塞已解除；最终状态待回收。


## 2026-10-13T16:12:26-04:00：候选结果完整回收，本轮停止且未晋级

官方0.40.3运行时已解决架构加载问题。CPU29439392完成（136秒）；v3 GPU29439492因repeat_last_n=-1被新接口拒绝失败（128秒），保留记录。v4 29440002于16:08:30正常退出（1108秒），实验状态stopped_output_failures：mixed计数校准通过，5题尝试/3题解析/2连续6144输出上限，剩余8题未运行。服务已停，manifest未变，全部真实输入计数精确匹配；完整原始结果已回收并核验。

相同已尝试5题的核心字段通过数：旧Qwen3 no-think 2、thinking 3、候选9B 1；不能把这当独立测试成绩。候选未达工程门槛，不替换、不开始微调。下一步接入程序事件事实绑定、引用/算术核验，并按计划只增加一个资源验证过的更强候选；独立家族与20条标注试验仍需准备。合格训练样本0。

详见[候选结果报告](monitor_candidate_results_2026-10-13.md)。本轮恢复7请求/1236GPU秒；累计413请求/11150主要GPU秒，CPU下载另列。门户网络已恢复；不要重提旧stage/reservation。
