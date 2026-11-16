# 离线核验说明

本说明复核已经返回的结果，不访问 Bouchet，也不运行模型。作业 32473668、此前作业 32446760 均已关闭，后续监控已停止。

## 一条命令复核本轮

在完整工作区中运行：

```sh
cd '/Users/a1234/Desktop/ai frontier model/TGF_Monitor'
'/Users/a1234/Desktop/ai frontier model/monitorability_tgf/.venv/bin/python' project/closeout_2026-11-07/offline_verify.py
```

脚本只读取文件，不发送请求、不导入 GPU runtime、不生成数据，也不覆盖现有分析。它校验冻结哈希后，从冻结源码提取原来的输出校验与分析函数，逐个重算 120 个计划位置，并要求与现有 analysis 完全一致。它需要 Python 3 和 `jsonschema`。

压缩证据包保留 `project/closeout_2026-11-07` 的目录层级；解压后也可在包根目录运行同一路径的脚本。原始输入、源码与结果均保持原字节。包内未附模型权重，命令不重新推理。

预期结果：120 个计划、120 个 dispatched、120 个 returned；105 valid、14 truncated_or_nonstop、1 invalid_schema；104 个有效且标签正确；192320 个实际输出 token。Qwen 60/60 可用、59 个标签正确；gpt-oss 45/60 可用、45 个标签正确。

冻结校验覆盖：25 个代码及输入文件、7 个本地参考文件、11 个准备源码条目、312 个模拟器溯源文件。两个代码组有重叠，不能相加称为不同源码文件数。分析另核对 362 个返回结果文件、120 个请求和原生提示 token 哈希。

## 关键文件

相对于 `project/closeout_2026-11-07`：

- `validation/manifest.json`：冻结清单。SHA256 `d84d8f9f94a3b2fced77ee2f96385bdaf5e173652467c52fd715a45e79cbf5f8`。
- `validation/closeout_validation_results_32473668.zip`：原返回包。SHA256 `fccc44910adb08f98ac7af2d8efe8a02d207c5403c1b2e6fba799e6c38f9670a`。
- `validation/analysis_32473668.json`：逐个位置、配对对照及失败类别。其原始 `semantic_review_completed=false` 保留为分析阶段快照，不覆盖。
- `validation/output_reviews_32473668.json`：后续语义审核，覆盖 60 个输出位置，其中 45 个有效解释、15 个失败输出。其余 60 个有效输出做过格式和标签核对，没有声称逐条解释审核。
- `validation/interpretation_32473668.json`：补验解释与两个原文案例。
- `ai_blind_review_2026-11-07/review_sealed.json`、`seal.json`、`reconciliation.json`：独立上下文 AI 审核及封存后核对。
- `evidence_index.json`：此前十个主要证据来源的路径和哈希。

AI 封存输出 SHA256：`dace9bec4bd257432944e0b66d61c5985e1d98f056a46ba3c133d8ec1e99687c`。12/12 与作者参考一致，0 未决；未改动参考标签和任何模型结果。原人工审核模板仍保持空白。

## 复现范围

离线命令完整重算这轮 120 个既有输出的有效性、标签计数及配对结果。它不证明模型再次运行会逐字一致，不校验模型内部过程，也不执行早期作业。早期比较及 Tony 工作保留报告和固定来源快照，原始工作区内还有相应完整目录。

最终结论依赖的范围限制保持不变：开发记录复用，银行自然数据覆盖不足，最终输入为脚本模拟器构造，只有一个 seed，未完成独立未见任务家族测试，未取得独立人类金标。

Word/PDF 中的本地证据链接指向原工作区。跨机器阅读时，请用包内 FINAL_REPORT.md 或 TGF_Report.md 的相对路径导航。早期报告可能进一步链接未收入此包的历史原始记录；这些仍保存在原完整工作区。
