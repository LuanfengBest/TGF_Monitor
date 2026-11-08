# TGF 项目收尾入口

报告、展示、用户授权的独立上下文 AI 盲审及离线核验已完成。当前研究定位为开发比较与受控诊断，未对外提交课程作业。

见 [交付材料阅读指南](deliverables/README.md)、[英文报告 PDF](deliverables/TGF_Report.pdf)、[可编辑报告](deliverables/TGF_Report.docx)、[中文讲稿](deliverables/SPEAKER_NOTES_ZH.md)、[AI 盲审结果](deliverables/AI_REVIEW_SUMMARY.md) 和 [离线核验](deliverables/OFFLINE_REPRODUCIBILITY.md)。13 页英文演示保存在本聊天的 Spaces 中，身份见 [演示记录](deliverables/presentation_metadata.json)。

原实验结果保持不变：Qwen 原事实 11/12，加累计 12/12，只有一个实例块改善，未达到至少两个块改善的预设标准；额外数字比较无新增分类收益。真假断言没有有效配对翻转。gpt-oss 45/60 有效且标签正确，14 次截断、1 次格式失败均保留。

新 AI 代理只读匿名原始记录，封存后与参考标签 12/12 一致。主助手对照检查了 198 处引文和 36 个已执行动作。该审核不是真人金标，也不是对所有旧记录和 Judge 解释的独立审核。原人工模板未填写。

作业 32473668 已结束，120 个输出经离线重算与原分析完全一致，全部冻结文件保持原哈希。此前作业及 heartbeat 均保持关闭，不追加实验。

剩余团队事项：确认作者贡献和课程格式，正式提交。原提案的独立自然测试、完整两环境样本覆盖和真人金标未实现，报告明确说明范围缩减。
