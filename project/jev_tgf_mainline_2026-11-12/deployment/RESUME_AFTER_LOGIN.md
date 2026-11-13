> **已完成，以下是历史交接记录。** 用户重新登录后，产物已下载并校验，Jev 正式判断、配对分析及 32 条来源复核均完成。当前状态见 [LIVE_STATUS.json](</Users/a1234/Desktop/ai frontier model/TGF_Monitor/project/jev_tgf_mainline_2026-11-12/deployment/LIVE_STATUS.json>)，完整结果见 [REPORT.md](</Users/a1234/Desktop/ai frontier model/TGF_Monitor/project/jev_tgf_mainline_2026-11-12/REPORT.md>)。无需再次执行以下命令。更新：2026-11-12T13:31:15.111309+00:00。

# 2026-11-12 执行状态：等待文件下载登录

用户已授权本批完整执行；不需要再次询问创建 key、充值或提交计算。当前唯一阻塞是 Bouchet OnDemand 文件管理器在下载时重定向 Yale CAS，需要用户重新登录。Jev key 已存在本机私有配置路径，不要输出或上传。

## 已完成

- 冻结 manifest SHA256：`4f0a701dc485dfc9487bea2d1286e1f626ac8017473bdae0d22fb075dd5bfc4a`，480 个文件未改变。
- CPU 作业 33079035：COMPLETED / 0:0，541 秒；全部权重与输入检查通过。
- Actor 作业 33080183：COMPLETED / 0:0，2026-11-12 02:12:06–03:48:00 ET，5754 秒。
- 192 个采集位置全部处理。189 条 eligible；case074、case132 无敏感执行；case146 因截断/非成功输出而 invalid。615 次自然采集 Actor 调用。
- 378 次 F/T 回答已处理，376 有效，case066.F / case113.F 无效。保留分母，不重试。
- Qwen 作业 33092334：COMPLETED / 0:0，03:52:17–04:40:25 ET，2888 秒。
- 189 次 C 复查、754 次正式 Qwen 调用。共 768 个正式计划位置 + 8 个 smoke 的结果位置已写入（含排除/不可用位置）。原始结果仍需本地核验其逐项状态。
- 两个 GPU 作业总计 8642 秒 = 2.4005556 H200 小时；没有待执行的本批集群作业。
- Jev 仅完成 8 次 smoke；正式调用尚未开始。

## 集群产物

根目录：`/nfs/roberts/project/cpsc4880/cpsc4880_rz377/tgf_jev_mainline_20261112_v1`

已导出一次，禁止重跑 export（exclusive creation）：

- `/home/cpsc4880_rz377/tgf_jev_mainline_20261112_v1_results.zip`
- ZIP SHA256：`95a8557c55ced1f9fbf1bb5d067080818006ebe88d934c84aa367ac8a93addfd`
- 压缩 196235142 bytes，展开 993567925 bytes；10802 个产物文件，加 `RESULT_FILES.json`。
- 大文件主要是模拟器完整执行状态证据。传输 helper 仅据此调整体积校验，记录见 `postprocess/TRANSPORT_AMENDMENT.json`；实验与分析代码未变。

## 浏览器继续

Chrome browser 2；Shell tab 1064500607，文件管理器 tab 1064500619。文件管理器已停在 Yale CAS 登录页并标记 handoff。用户完成登录后，回到 Home Directory，Refresh，Filter 精确文件名，勾选行并 Download。使用 CUA 受支持下载事件取得本机路径；不要经浏览器外部网络方式提取 session/cookies。

Shell 中 `tgf_ctl=/home/cpsc4880_rz377/tgf_mainline_deploy_20261112.py`，`tgf_seal` 为上述 manifest SHA。Actor、CPU、Qwen 均已提交并完成，不得重复提交。

## 本地继续

工作目录 `/Users/a1234/Desktop/ai frontier model/TGF_Monitor`。

1. 下载 ZIP 后：

```sh
python3 project/jev_tgf_mainline_2026-11-12/postprocess/import_results.py '<downloaded ZIP path>' --observed-sha256 95a8557c55ced1f9fbf1bb5d067080818006ebe88d934c84aa367ac8a93addfd --observed-uncompressed-bytes 993567925
```

2. 核对所有 frozen/checkpoint 哈希、作业退出、采集/追问/C/Qwen 单项状态、共同输入 seal 和预算。不更换输入、不根据 Qwen 预测调整提示。
3. 使用本批 `.venv/bin/python -m tgf_jev_mainline_v1.judge_stage jev --phase formal --key-file /Users/a1234/.config/typesafe/api_key`。保持 API key 在本机，日志只输出状态；Jev 总上限 776 次与 $1.10，不重试，不充值。预计正式 ready 754，实际以冻结计划为准。
4. 完成后运行冻结 `python -m tgf_jev_mainline_v1.analyze`，然后 `postprocess/supplement.py` 与 `postprocess/plot_results.py`。解释性图形用 Matplotlib 3.11.2（requirements-render.txt 已存），不影响模型环境/冻结分析。
5. 完成 AUDIT_PACKET.json 中全部 T/F 变化及确定性抽取的未变化实例来源复核。它是助手语义复核，不是独立人工金标准。区分无效回答造成的差异与回答内容收益；可以另列双方回答有效的诊断性结果，不能替换冻结主分析。
6. 补齐按策略独立部署成本、重复公共输入敏感性、引用支持与研究主线结论，写完整报告。若未满足预设收益/覆盖/成本条件，明确报告负结果或不确定性，不再自动扩量。

科学问题和解释边界以 `PROTOCOL.md` 为准。Jev 是最终 Judge，原模拟器执行/授权程序才是参考 verifier。全部新实例仍来自既有六类模板。
