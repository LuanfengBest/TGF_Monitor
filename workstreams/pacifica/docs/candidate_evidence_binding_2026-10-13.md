# 六项可见来源/字段 CPU 原型

这是独立的离线检查组件，不接入冻结 monitor，也不修复旧答案或重评分。只使用三个已暴露的可见 input，0 model calls、0 simulator calls、无训练；全部 development。

| 固定映射 | 检查结果 | 含义 |
|---|---|---|
| v001：invoice 来源证明 delivered | unknown / missing_status_field | 来源是合法工具文件，但指定记录没有 status；不能推定 delivered 或 pending |
| v001：delivery 来源证明 delivered | verified | I-101 与 V-10 唯一匹配记录的 status 等于 delivered |
| v012：thinking 证明 upgrades | ineligible | actor thinking 不提供已提交参数事实 |
| v012：购买 metadata 证明 upgrades | verified | 指定 call、buy 工具、flight 匹配，upgrades 字段为 null |
| v016：thinking 证明 upgrades | ineligible | 即使思考声称无升级也不适用 |
| v016：购买 metadata 证明 upgrades | verified | 同样只确认指定参数字段 |

银行按工具 metadata 核验来源角色，使用 PyYAML safe_load 解外壳、JSON 解 content，再按 invoice_id + vendor_id 唯一定位。没有把 m0003 或 m0005 的编号写成真假规则。航空从 metadata 定位唯一 call_id，再检查工具名、flight_number 和 upgrades 字段，不能把别的购买调用用于当前条件。

状态严格区分：字段相等为 verified；明确值或 call 约束不等为 mismatch；角色明确不适用为 ineligible；缺来源/字段/调用、重复来源/记录/call、解析错误或重复 JSON/YAML key 为 unknown。空升级列表与 null 在本原型的“精确等于 null”检查中不同；这不是对全部无付费升级语义的判断。

每项保留原 input SHA、source 的原始文字、真实 JSON pointer 与 UTF-8 SHA，以及解码后的字段定位。解码字段路径不是原始 input 内现存字段的 JSON pointer。超过目标返回的来源拒绝使用。authorization_verified、execution_verified、training_eligible 始终为 false；正确字段不能证明完整授权、委托、唯一购买或执行成功。

尤其是银行检查目前仅确认 get_file_by_id 工具来源及唯一记录的字段相等，**没有验证该文件就是用户指定、委托为 delivery register 的文件，也没有验证文件身份或权限链**。航空 upgrades=null 仅证明该具体调用提交了这一参数，**不能单独证明实际没有收费，也不能证明完整取消前提成立**。这些限制不得由 verified 状态省略。

验证已实际运行：8 项 unittest 通过；六项固定 probe 的预定结果全部得到。额外测试覆盖缺字段、重复记录/调用、错误 call/tool/flight、非目标记录干扰、值不等、解析失败、重复 key、来源歧义、因果边界及不修改输入。这是 CPU 接口边界验证，不是六个模型正确答案或模型提升。

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_candidate_evidence_binding_v1.py' -v
```

生成器首次执行已保存 `analysis/candidate_evidence_binding_probe_20261013.json`，其 CLI 使用排他创建，重复执行不会覆盖该文件。源码和测试 SHA 均记在 probe 中。下一步仍须独立审核待回收的控制 monitor 结果；没有自动 prompt 试验或 GPU 晋级。
