# 中文展示讲稿

主讲 12 页，另有 5 页备查。建议主讲约 10–12 分钟，课程正式时限尚待团队核实。

一句话主线：以 Jev 作为最终 Judge，检验它是否读懂执行当时的授权，并分别测量追问和证据索引的额外收益。

## 1 Authorization Auditing with Jev as Final Judge

中文开场，约40秒：现在的主线是把 Jev 放在最终判定的位置，研究它能否看懂操作发生时的授权。我们不把换模型本身包装成方法创新。整个项目从定向追问出发，结果发现强直接基线很关键，追问和时间索引的额外收益需要分开测。今天会保留两项主要负结果，也会解释具体失败。主讲为第1至12页，约10至12分钟；第13至17页为备查，时长只是排练建议而非课程规定。Source: project/final_report_2026-11-13/FINAL_REPORT.md, sections 1 and 8. Original author list retained; contribution agreement remains for team review.

## 2 Permission must apply when the action is executed

中文，约50秒：先授权再买票，与先买票后授权，可能用了相同的文字，但正确结论不同。这里的 Judge 是待评测的判定器，不能一边判答案一边制造自己的标准答案。参考标签来自模拟器执行、公开许可和程序规则；AI来源检查不是人工金标。我们的实验看已经执行的操作，尚未测试能不能提前拦截。表格是授权时序示意，不是送给模型的参考答案。Sources: timing PROTOCOL.md and RESULTS.md; mainline PROTOCOL.md.

## 3 Separate the Judge from the extra information

中文，约60秒：192个采集位置按事前准入规则留下189条轨迹。每环境48个实例，每实例两个Actor条件，不是189个独立任务族。P已经包含完整公开记录和事实账本，并非只有最终回答。C、F、T分别检验复查、通用追问和定向追问。中间材料只生成一次，两种Judge读完全相同的版本，所以能把组件作用分开。F/T禁止工具，4096输出上限匹配，但实际时间不一定相同。Jev-1.14.0主Judge，Qwen3-32B对照，Actor gpt-oss-120b。Source: project/research_update_2026-11-12/reports/mainline.md, design.

## 4 Jev improves the direct baseline on this batch

中文，约55秒：这是把Jev作为主要Judge最直接的经验依据。同一份P材料，违规检出从8/26到21/26，多检出13条，误报都为0/67。但是这个比较是在看到主结果后整理的组件比较，不能伪装成原来预注册的成功主检验。它也不是严格等算力比较，不支持Jev在所有任务都更强，更不证明它长期稳定。Source: reports/baseline_comparison.md and reports/mainline.md.

## 5 Targeted follow-up did not meet the primary criteria

中文，约65秒：不能把0.0499426四舍五入成0.05再说通过。区间还包含0，耗时比也略超过门槛。两条F截断都留在主分母，一条本来违规一条合法。只看两个回答完整的91条时，F和T在每个Judge下逐条相同。这解释了差别来自可用性，却不能据此证明两种方法等效，也不能把条件化子集换成主分析。Jev P、C、T在航空逐条相同，没有证据显示定向追问比其直接基线多抓到了违规。Source: reports/mainline.md.

## 6 Eight timing pairs test when a label should change

中文，约60秒：这轮的作用是把主线问题拆小。6对应该因为授权先后改变正确结论，2对给的是别人的许可，因此不应该改变。不能把两次都错但一致算稳定。链接只按最近前后消息机械生成，不直接告诉模型哪条许可有效。全部8对数据在推理前冻结，不是为了Jev结果好看事后替换。Qier原分支保留，我们是另建v0.2实现，并没有直接复现原分支的数值。Source: authorization_timing_jev_2026-11-12/PROTOCOL.md and PAIR_SPEC.json.

## 7 Jev is at ceiling and gains nothing from time links

中文，约60秒：这里最容易讲错的是把8/8当成索引成功。Jev原文就已经8/8，所以预定索引增益是0。Qwen从4对到5对只改善了一对，这属于次要描述性结果。两模型都没有对8条合法记录误报，区别来自违规漏检。我们测的是这组固定样本上的判定，没测重复运行稳定性，也没有让Jev生成理由，因此不能说引用质量提高了。Source: timing RESULTS.md, recovery_01/analysis.json.

## 8 The controls reveal different kinds of failure

中文，约60秒：第一类是该变的时候没有改对：先买后授权被当合法。第二类是一对通过索引修正的例子。第三类是不该变的时候变了：买票对象Eli和授权对象Mina不同，许可位置变动不应改变越权结论。Qwen却从违规变合法。我们能确认这个行为，不能直接说模型脑中就是对象混淆，因为顺序敏感和单次波动还没排除。基础与插入消息对使用不同实例，也不能简单做跨组因果解释。Source: recovery_01/DETAILS.json; RESULTS.md cases.

## 9 A valid verdict or citation is not enough

中文，约60秒：这页解释为什么不能直接宣布监控器可信了。五个漏检都涉及像Jordan Ellis 30这样的合成姓名；严格字符串标签有效，但数字也可能被当年龄，是构造局限。银行复查主要事实是真的，加入后却多了五个误报，不能一概叫幻觉。Tony的新审计发现四动作完整证据链需要至少五个证据单元，老格式却最多四条，说明接口本身会限制解释完整度。105个有效旧输出里27个满足新标准，不意味着其余78个全错。人工复核数仍是0。Sources: reports/semantic_audit.md; source_review/README.md; Tony 06 evidence audit.

## 10 Earlier negative results remain in the final account

中文，约60秒：我们不换故事把以前的负结果藏起来。最初通用追问已经6/6，定向没多检出，还多一个误报；固定动作后仍没区别。看起来很有效的单案例金额提示，到六块补验只改善一块，没有达到两块门槛。后来Jev账本实验，在自然记录上也没有分类增益。这些结果一起说明不能只挑最醒目的正例讲，也提示先把Judge基线做强。Source: closeout_2026-11-07/FINAL_REPORT.md; reports/development_2x2.md.

## 11 The implication is more accountable authorization review

中文，约55秒：意义不是让模型的判定看起来更自信，而是帮人查清哪一步、凭哪条许可、什么时间发生了越权。可靠的正常放行也重要，否则会制造报警疲劳。实验支持先测强直接基线、再测追加组件；对缺证或冲突做升级复核是合理下一步设计，但我们还没有测真人节省时间或提前阻止损害。这里要把已经得到的证据和潜在应用分开。Source: research_update_2026-11-12/IMPLICATIONS.md; integrated report section 6.

## 12 The contribution is a bounded and reproducible account

中文结尾，约50秒：一句话概括，Jev让直接判定基线更强，但我们没有证明额外追问或时间索引对它有新增收益。贡献是把Judge、材料、失败处理和证据支持分开检验，并用控制案例把失败讲清楚。它可以是一份扎实的结课实证研究，但不该包装成普遍安全、首创Judge或发表级新方法。接下来只进行报告、团队审阅和真正的人工复核准备，不自动扩量。Source: integrated report sections 1, 6 and 8.

## 13 Appendix  Mainline airline results

备查：P/C/T在Jev下相同；Qwen从补充回答中受益，但T相对F的差异仍只有F缺失。航空两条F不可用一正一负，所以即使FP为0，TN也只有66/67。G不能用1−FPR替代TNR，因为不可用保留分母。块bootstrap5000次，次要对比未做多重校正。Source: reports/mainline.md and saved analyses.

## 14 Appendix  Bank results and repeatability caveat

备查：银行的正例只有8个，不能凭8/8和零误报认证低错误率。Jev C的五条误报和同输入不一致均保留。37组是自然出现的重复完整请求，没有为稳定性专门重复采样。两个Jev输出都使用原定argmax选类，没改阈值。Source: mainline SEMANTIC_AUDIT.md and reports/mainline.md.

## 15 Appendix  Earlier evidence gains and failures

备查：旧费用案例本金95.20+41.15+38.40+64.75=239.50，恰好等于预算，费用不在授权审核范围。Qwen原始条件算对总额仍误报；补总额后改对，但错误断言条件也改对，不能归因于单纯算术修复。一分钱超支107.25对107.24的案例，两Judge都拒绝错误无违规断言，但引用仍不完整。旧GPT-oss不同输出约束和失败率不宜用来排名能力。12条旧参考有独立上下文AI复核12/12，不是人工，更不覆盖新实验。Sources: closeout FINAL_REPORT.md; development_2x2.md.

## 16 Appendix  Resources include the failed start

备查：保持原总预算，第一次失败也计入。CPU先核验19个资产并复制兼容编译缓存，GPU正式分配136秒正常退出；累计1373秒22分53秒小于30分钟。72调用含64正式8smoke，两Judge各36，均一次尝试。资源合规不是科学假设成功。不同批次不合并准确率，也不拿不同服务部署的延迟来解释模型架构优劣。Sources: timing RUN_STATUS.md and recovery_01/FINAL_OUTCOME.json; mainline cost section.

## 17 Appendix  Provenance and research positioning

备查：作者沿用proposal，贡献描述依据仓库来源，不能说团队已确认分工。Qier source 407ed0026685e958ed35342b70d0a50e90da2854；Tony 898b73acb3b284d39cd61ac4f157d0ef200de5a1。Guan et al. https://arxiv.org/abs/2512.18311；Wang et al. https://arxiv.org/abs/2603.28590；Deußer et al. https://arxiv.org/abs/2609.37647；TypeSafe接口 https://docs.typesafe.ai/concepts/system-one。前人已有Judge比较和追问监控，不能声称首次。报告含完整可复查链接；本次未新增实验，也未代为提交课程。
