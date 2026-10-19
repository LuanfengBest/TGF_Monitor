# A40 排队范围补充（模型运行前）

22:29 EDT 左右正规OOD只读sinfo/scontrol确认：gpu_devel的唯一A40节点已分配；gpu分区有9个A40节点（36卡）、AllowAccounts=ALL、AllowGroups=ALL、相同A40计费权重35。为避免单节点等待，允许Slurm在gpu,gpu_devel两个正规分区选择。仍只有1张A40、4CPU/64GiB、20/45/45/45分钟、同一固定v1运行代码/输入/模型/训练/评分。未提交过GPU，不取消或重提已有作业；权重CPU29593125不受影响。

旧冻结v1 sbatch和协议不改。新submit_sft_stage_v1_queues.py额外验证本排队配置，用新*_queues.sbatch，保存同一唯一stage提交回执并绑定排队配置SHA；runtime仍验证旧科学协议SHA。后续统一用这个新提交入口，不运行旧submit_sft_stage_v1.py。此是常规排队调整，0新增模型/数据/重试/预算，不构成额外实验组。实际节点、GPU和AllocTRES由Slurm回执记录。
