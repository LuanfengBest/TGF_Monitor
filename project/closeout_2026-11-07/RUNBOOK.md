> 收尾交付更新：报告、13 页展示、讲稿、离线核验与独立上下文 AI 盲审已完成，见 [交付指南](deliverables/README.md)。AI 标签 12/12 一致，未代签人工审核；无新实验。以下保留原流程或计划作为历史记录。

# 单次补验操作记录

本轮是用户接受收尾建议后的新阶段。所有此前作业（包括 32446760）已结束，不重新打开其许可、不修改原冻结输入。

## 当前结果

作业32473668已完成（0:0，27分02秒），120次均返回。结果包已核验收集，分析与规定范围审核已完成，见 `results_32473668.html`。105个有效输出中104个标签正确，另有14次截断和1次格式无效。60个位置已逐条审核。自动跟进已删除；下方提交/收集步骤仅保留历史操作记录，不重新执行。独立人工审核仍待真人完成。

## 当前入口

- 本地验证目录：`project/closeout_2026-11-07/validation`。
- 独立远端目录：`/nfs/roberts/project/cpsc4880/cpsc4880_rz377/closeout_validation_20261107_v1`。
- 输入包：`validation/closeout_validation_20261107_v1.zip`；SHA256 与大小见 `validation/bundle_receipt_LOCAL.json`。
- 新模型调用上限 120：Qwen 60、gpt-oss 60。单个 H200、90 分钟；无重试、无重新排队、无后续自动扩量。
- 作业 **32473668** 已单次提交；美东 2026-11-07 19:32:53 提交，首次观察为 PENDING、等待 GPU。远端 ZIP 和 manifest 哈希均一致，凭证见 `validation/submission_receipt_LOCAL.json`。
- 提交阶段已完成，以下步骤仅保留作操作记录，禁止再次执行 submit。只跟进该编号。

## 恢复后提交

1. 只通过 CUA 的 Chrome 和 Bouchet OnDemand。需要普通登录时点 SIGN IN，让现有账户自动鉴权。禁止本地 SSH、curl、浏览器外网络访问 Bouchet。
2. 先重读 `STATUS.json` 和验证目录状态，检查是否已有提交凭证。若已有 job ID，只跟进该作业，绝不再执行 submit。
3. 通过 OnDemand 文件界面上传上述 ZIP。通过 OnDemand shell UI 读取远端 `sha256sum`，与本地 receipt 一致后再使用。
4. 创建新的专用根目录；若目录已存在，先只读检查其内容与提交凭证，不覆盖、不删除、不重试。解压的输入包自身没有任何标签参考文件。
5. 在该新目录，通过 shell UI 执行 `python3 -m closeout_validation_v1.submit`。脚本会校验输入、建立一次性目录、做 `sbatch --test-only`，再至多提交一次。任何模糊/失败返回先核对调度器，不能重跑 submit。
6. 保存 UI 观察到的作业编号、远端路径、输入哈希和提交时间，再更新本地状态。不能将仅准备好的包标成已提交。

## 收集与审核

作业结束后通过 OnDemand UI 查看调度状态、退出码、日志、`results/summary.json` 与导出的 ZIP。先在远端 UI 核对 ZIP SHA256，再通过文件页面下载。下载本身不代表运行成功。

在本地仓库根目录使用既有 Python 环境执行：

```text
/Users/a1234/Desktop/ai frontier model/monitorability_tgf/.venv/bin/python -m closeout_validation_v1.collect DOWNLOAD_PATH JOB_ID REMOTE_UI_SHA256
/Users/a1234/Desktop/ai frontier model/monitorability_tgf/.venv/bin/python -m closeout_validation_v1.analyze JOB_ID
```

命令中的含空格 Python 路径在 shell 中需整体加引号；三个占位参数必须替换为实际值。收集器拒绝路径穿越、符号链接、超大/损坏包和覆盖已有结果。分析器核对返回文件、冻结输入、本地参考、原生提示哈希、调用上限、全部计划位置，并保留缺失/无效/截断。

完成脚本分析后，逐条阅读全部错误和发生判定变化的输出，并核对错误断言被抵抗的正确输出。保存独立于原始输出的审核笔记，再将审核后的结论并入报告。存在不支持结论的引用时单列，不能因标签正确而跳过。

## 独立标签审核

给实际审阅人的入口是 `validation/HUMAN_REVIEW.html`。不要先给作者标签页、断言处理或 Judge 输出。审核人自行填写并下载 JSON；填写前是否看过结果必须如实注明。当前模板全部未填写，助手不能代签为人工审核。

新增人工审核文件单独保存，不修改已冻结作者参考；分歧需要显示原判断、独立判断与理由。报告最终数字若受分歧影响，应同时报告敏感性分析。

## 终止

完成或失败后写清实际结果和局限，进入报告定稿。即使结果不复现或全部组都满分，也不自动增加题目、模型、seed 或任务。未完成的人类审核、最终展示或团队确认仍保留为待办。
