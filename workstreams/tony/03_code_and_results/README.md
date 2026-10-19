# Workstream C 代码与结果

## Tony本次新增

- `audit_results_30030723.py`：只读核查原始结果、独立重算分组指标。
- `audit_30030723/`：派生统计表与结构化核查记录。
- `diagnostics/case_review.md`：本批误报/漏报与质量问题的具体解释。
- `runtime_scripts/`：本次运行时准备、GPU检查、权重下载、过夜2→64入口。这里仅归档，不自动提交。

## 沿用及未改写的材料

`received_30030723/`为用户上传原始ZIP的完整解压内容，其中tgf/为Luanfeng原版v4，inputs/为原有64条开发轨迹，runs/为Tony本次真实推理输出。来源锁、模型校验收据和完整过夜日志均保留。不是重新生成的原任务数据，不包含模型权重。

## 最小复算

```bash
python -B audit_results_30030723.py
```

不需要GPU，仅标准库，Python3.10+。新输出写入audit_30030723，原始received目录不改写。完整使用边界见技术交接。目录中的模拟隐藏目标和私有参考名单只用于离线复核，不能整体喂给monitor。
