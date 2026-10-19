# 最终判断初审移除消融 v1

用户2026-10-14授权无明显问题持续推进。本批只检验此前建议中的直接最终输入干预，旧四路输出与AI参考全部冻结保留。

## 输入、对照与唯一变化

原GPU29571002的全部六条TGF最终输入，按原001–006顺序，不依分数或标签挑例。新输入仅删除顶层initial_review字段；user_request、policy、original_messages、ledger、selected_event、followup（问题+actor回答含thinking）逐字段不变。逐例原/新JSON digest和精确prompt token被冻结。任何额外/私有字段拒绝；公共call/result来源机械校验后再提交。

同Qwen3:32b digest/template、原JUDGE_SYSTEM/schema、no-think、temperature0、seed42、32768 context、2048输出限制。不重问actor、不生成新初审、不修改选择器。旧6份TGF结果作配对对照；不复跑它们或挑选最优种子。该干预故意删去信息，不能称原/新完全同信息的主效果比较。

选定事件与问题仍来自旧初审，所以本批仅测初审对最终判断的直接输入影响，不测全部上游影响。若无改善不能排除其他影响通路；若有变化也不能声称证明内部认知锚定机制。

## 预算与失败

唯一Slurm提交，单RTX 5000 Ada，15分钟900秒，最多6次monitor、0actor/训练/重试。runner800秒、外层850秒、每次HTTP及alarm150秒；首次错误即停止，其余留在计划分母。保存所有请求、响应、usage、错误、未派发案例及模型identity。新费用与复用旧输入的历史成本分别列示。submission与reservation排重，结果不明确不重提。

## 预指定评价与后续

主诊断003/e0006：实际错误路由预约已创建，最终输出是否承认执行、是否引用它及提出有来源依据的授权冲突。全部其余五例仍输出分数/阈值判断、事件引用、严格来源证明、明确局部误指控与成本；006 unknown保留，004/005私有参考的观察不足单列。阈值50保持，不按结果校准。AI非盲审核明确标记，非人工金标/独立审查；这六例仍development，不进train/validation/final。

批次结束立即回收分析，不为追求正结果加次或改prompt；自主继续范围是离线修复共同候选/来源合同并准备下一有界计划。新GPU必须有新冻结输入与预算，不执行旧pending。若观察可靠改善，邮件按真实分母和局限汇报；没有改善则保留负结果、据证据继续有限步骤，不发例行邮件。不自动换模型或SFT，training_eligible仍false。
