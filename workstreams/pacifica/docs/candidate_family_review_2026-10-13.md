# 候选任务家族来源与分组审核

本次AI审核支持将发票审批和单人改签识别为两个新的**任务机制组**，并仅批准其v2在其他生成门槛通过后进入有界development actor pilot。此处family_independence_verified=true只表示相对于列明的已审任务定义存在实质机制区别，绝不表示统计独立、未见、验证/测试或训练资格。

| 建议family ID | 父级共享环境 | 核心机制 | 划分建议 |
|---|---|---|---|
| monitorbench_bank_transfer_2_original | BankingEnvironment/原银行工具 | 朋友旅游欠款邮件分摊、更正和付款 | development，保留旧development_regression别名 |
| monitorbench_american_airlines_2_original | TravelEnvironment/原旅行工具 | 多人会议往返航班、转机和饮食限制晚餐 | development |
| tgf_bank_invoice_release | 共享银行/云盘工具，受限InvoiceEnvironment | vendor委托审批、交付前置、invoice/vendor关联、三表金额一致、幂等预约 | development |
| tgf_airline_single_passenger_rebooking | 共享航班/票据工具，受限RebookingEnvironment | 原票保全、合规替代购买、成功后才能取消指定旧票 | development |

银行差异不只是把朋友改名为vendor：原任务根据欠款邮件算出应付金额，新任务须按invoice/vendor连接三个登记表，并验证特定vendor的审批人和交付状态，才产生付款许可。航空差异也不只是把16人变成1人：原任务是会议旅行规划，新任务新增已有票保全及由合规成功购买开启的取消许可。两个候选分别依赖跨记录条件与事件先后条件，足以形成独立的机制分组。它们仍共享原模拟器、工具合同、开发者和错误原语，不能当统计独立样本。

同一候选的草案、v1、v2、名称/金额/日期/seed/授权改写、探针、benign/malicious变体、短/全视图、同轨迹所有事件必须同组且全部development。v2修复不生成一个可跨split的新家族。原银行已有source_inventory的5条也继续同属原development家族。

另外两个已读草案仍只属development暴露材料，不能自动准予生成或最终测试。bank_revoked_standing_permission缺成熟取消/时钟合同；airline_scoped_dinner_reservation与原任务晚餐子任务有直接重叠，dinner-only本身不证明不同家族，其跨event机制需要另行审查。本次不编造它们的获批family IDs。最终未见银行和航空家族仍是缺口。

实际查询上游远端为https://github.com/ASTRAL-Group/MonitorBench.git，HEAD为b6229e4b8ea9abcec38d61159c9cbd0f577ddf35。读取两task_definition.py/README、航空空solution、现有inventory/data contract/4草案/README及两个v2任务。data/training/monitor_v1未发现冻结family registry；草案仍split=null，本报告不覆盖它们。逐文件SHA和逐条原文依据见JSON。

生成前必须由主agent冻结真实registry（family ID、限定scope、development、task/fixture SHA、时间），完成实际runtime和模型传输核验，显式调用generation gate，锁定成本/调用上限并保留所有失败/unknown。此报告可以支持registry的任务机制分组审核字段，不能替代其他门槛；若消费方把family_independence_verified解释成统计独立或未见资格，则不能据此赋true。

本AI此前已经参与v1标注与v2语义复核。本次又看到了上游definition中的隐藏副任务、HINT和银行参考金额，已在JSON中明确记录；因此不是新样本盲审、独立人审或金标。未读候选私有状态/design audit/revision/源映射或生成器，未运行CPU测试、GPU、训练或新生成，仅创建两份报告，未改任何旧任务、标签或registry。

来源SHA256：

- `third_party/MonitorBench/datasets/dual_objective/agent/task_pairs/bank_transfer_2/task_definition.py`：`48c207c5195b4181bc753b678363b2b392843ac2076d9ebbfd5b747cee46ce47`
- `third_party/MonitorBench/datasets/dual_objective/agent/task_pairs/bank_transfer_2/README.md`：`ef70f93d101638b92600a2e981bd7b3655e367c79d5c494884f30c3295604e60`
- `third_party/MonitorBench/datasets/dual_objective/agent/task_pairs/american_airlines_2/task_definition.py`：`1f7f2bfa9c581c4c58cfcff5911b1adfb7f85d88fe30931790bb40b0f1c45faf`
- `third_party/MonitorBench/datasets/dual_objective/agent/task_pairs/american_airlines_2/README.md`：`9d337e706ad424cfd2d0a7c09f875f0684eda52100fd1f122796b8de255cc558`
- `third_party/MonitorBench/datasets/dual_objective/agent/task_pairs/american_airlines_2/solution.py`：`cd17270e5a2396d1d79169c007c0bb237dd6f5ca6059bd5ccf5e6c8f07f5af02`
- `data/training/monitor_v1/source_inventory.json`：`6226e2cba6110a869fafc924c2b898d88ae4e3a163150faacc53aa4072fc9b83`
- `data/training/monitor_v1/data_contract.json`：`8bfdb1951e631aba081eb8d006b9ab1085377d48b110ffdd6b0dbb8f4c617023`
- `data/training/monitor_v1/task_family_drafts/README.md`：`675063ae85ca6a12fab447ed1cc6598b68f48d4b04f8cd9681684bc4db9b0b46`
- `data/training/monitor_v1/task_family_drafts/bank_invoice_release.json`：`409889a9e5387c0a44bff64fdf05feedf2bd546538ff7a03a2bdb458f9f11aab`
- `data/training/monitor_v1/task_family_drafts/airline_single_passenger_rebooking.json`：`9b6811d64b7025766e590ba22abcadb98db34119728325c73619b9a93bfd06ac`
- `data/training/monitor_v1/task_family_drafts/bank_revoked_standing_permission.json`：`574db154a4daca5375842456bfd1a9bf0ce613fdef7793734d3846a00dafff48`
- `data/training/monitor_v1/task_family_drafts/airline_scoped_dinner_reservation.json`：`72013bb08b27a16af039c487f782033e04efa2eff85e3fcc0b9764513e5872d7`
- `data/task_design/bank_invoice_release_v2/task.json`：`551f921a0b1467b6af8b62de201afb34595b4fadf729da4c77fd1c824106711e`
- `data/task_design/airline_rebooking_v2/task.json`：`9c9c0e219ca6cd50ae33f28bba95f97206c2078f194c78dd05f5aa3157d19f4a`
