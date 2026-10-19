# 第二处定位符修复及一次预检

CPU29560911以FAILED/1:0结束，分配462秒、MaxRSS380536K。8包安装/import均返回0，占145076412 bytes；任务身份门禁失败，9+12远端tests未执行。原始回执/log和6文件归档已回收，SHA3b99e87d1dc0a648ba5c59cb6b3c17b3814b32a0edc27dc0b20a6bade47aea4f。没有GPU/模型/训练。

只读诊断确认银行五项身份全等；航空请求、政策、schemas、secondary均等，15个初始状态字段中仅corporate_discounts不同。该对象的discounts映射逐项相同，差异是yaml_path机器绝对目录。我在v2只修银行路径，遗漏了航空同类字段，故原CPU失败不能改写为成功。

v3完整保留原任务运行数据和生成设计，仅对两个已核实定位符做严格允许列表的比较规范化：spam_email.spam_file与corporate_discounts.yaml_path。其他字段仍逐值hash，折扣变化会被新test检出；原文件/折扣内容/实际运行状态不修改。v1/v2配置、代码、失败不覆盖。

不增加CPU安装作业，不重装、不下载、不重提29560911；复用已安装并核验的8包目录。对新代码做一次至多120秒的只读资格检查（原任务身份及9+12 tests，低资源预检），保存单独v3 receipt，必须通过才允许GPU。原CPU1个作业上限已用，不扩大；本次实现修复不产生任何实验调用。GPU仍原计划唯一1作业35分钟/240actorcalls，全部六attempt/seed/采样参数/提示词/预算不变。v3预检若失败则保留并停止，不继续第四轮修改或自动运行GPU。

此为已授权pilot的普通实现修复，不涉及研究选型或样本范围选择；无须用户重新决定任务。自动续办仍PAUSED。成功后由v3 plan和receipt接续，旧v1/v2不能直接运行。
