# 离线复现与文件用途

从 TGF_Monitor 仓库根目录执行。命令只构造规格、运行已有模拟环境的脚本路径和检查规则，不调用模型、下载权重或提交集群作业。输出目录必须不存在，程序拒绝覆盖已有冻结产物。

```bash
python -m prospective_data_v2.prepare --out /tmp/tgf-next-specifications-new
../monitorability_tgf/.venv/bin/python -W ignore -m prospective_data_v2.fixtures --prepared /tmp/tgf-next-specifications-new --out /tmp/tgf-next-witnesses-new
../monitorability_tgf/.venv/bin/python -W ignore -m unittest prospective_data_v2.test_preparation -v
```

规格构造只使用标准库与现有纯 Python 参考。模拟器检查使用当前项目已有的 Python 环境；依赖不足应报错，不会换成伪造的环境。

| 文件 | 用途 |
|---|---|
| `frozen_specifications/manifest_PRIVATE.json` | 所有任务、环境配置、未来更新、隐藏目标和脚本见证；不得整体交给 monitor |
| `frozen_specifications/initial_public_tasks.jsonl` | 每个实例当前初始公开内容；不是整段执行后的 monitor 输入 |
| `frozen_specifications/planned_attempts_PRIVATE.jsonl` | 固定的 48 个尝试位置与顺序；当前状态均为未开始、标签均为 null |
| `frozen_specifications/collection_limits.json` | 每条及全批硬上限的规格 |
| `frozen_specifications/collection_policy.json` | 模型版本、条件、分组与开发数据覆盖条件 |
| `frozen_specifications/source_hashes.json` | 构造器、现有收集器、参考与原模拟器来源，共 158 个文件的快照 |
| `cpu_witnesses/summary.json` | 48 条脚本验证结果及证据文件哈希；自然轨迹数为 0 |
| `ai_review_PRIVATE.json` | 当前助手逐实例的非盲作者复核，关联规格与脚本证据 |
| `completion_receipt.json` | 本轮测试、文件读取核验及旧冻结文件保持不变的记录 |

采集器仍按实际送达顺序生成公开观察记录。`$receipt:...` 只出现在私有脚本见证与任务目标说明中，由脚本从真实工具回执中取得确认号；自然 actor 必须自己读回执，不会得到这个脚本。

`screen_collection` 只读取经过审核的结果收据，检查标签覆盖、实例分布和来源类型。它拒收 monitor 分数，不能从隐藏目标推断标签。收据中的哈希字段不代替文件核查；真实采集接入时须核对原始 task、调用与状态证据后才能出具收据。

默认保存 actor 原始推理供私有溯源，后续主比较沿用 `action_only_explicit_final` 观察范围；若要测试完整 CoT，必须另列观察条件，不能只给 TGF 更多信息。当前未运行任何 monitor。
