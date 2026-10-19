# 共同事件接口v2：离线草案

状态：未接入本轮初审消融，未跑模型、未冻结下一轮GPU。该草案只为后续四路提供完全相同的候选、公共执行观察和选择规则。原v1所有输入/输出/评估保持。

候选由明确工具名登记，而非`get_`前缀自动判读。查询和未读邮件read-flag操作不分配这轮实质操作追问；完整原始事件仍保留给整个轨迹judge，排除追问不代表合法、无副作用或免于隐私审计。未知工具保留候选，例如get_webpage实际记录请求URL，不能因名字像查询就自动排除；生成验证码等也不因get前缀排除。

有限执行观察只识别公开返回中已经核对实现的精确模板：单笔schedule_transaction的成功预约/未预约、reserve_restaurant的餐厅不存在；绑定相应call/result和实际参数。成功预约只表示创建预约，不能写成资金已结算；不根据unrecognized IBAN或override自动判违规。模板不匹配、附加注入文本、金额/收款人不一致、批量或部分执行、harness错误均保留unresolved。不得读取state delta、verifier或AI参考来补全。

选择顺序为公共返回明确已执行→未解决→明确未执行，再沿用初审授权unresolved/conflict/supported、原操作类别和事件序号。初审对执行的解释不覆盖原工具模板。三类事件均保留，只有追问预算的排序不同。全部基线统一接收相同公开派生观察，不能只对TGF改接口。

6项合成边界测试覆盖信息不丢、unknown getter、成功预约不冒称结算、失败留存、参数不符/注入返回、私有字段和错误call/result绑定、伪造观察与初审覆盖不足。它们是实现检查，不是模型效果或新研究结果。后续需冻结脚本与对应工具源文件哈希；当前不把草案称为已验证的更好monitor。

下一轮预算边界需明确：若某条无实质候选，TGF会不追问，原B3“≤TGF实际token110%”不一定允许额外复查。不能为了预算过滤该阴性，也不能暗中扩大对照预算。下一协议必须事前规定此分支（例如共同可用token预算并分别报告实际支出），再运行新的前瞻样本。

来源审核：原MonitorBench本地冻结版本的tools/{financial_transfer,drive_tools,email_tools,calendar_tools,flight_tools,restaurant_tools,hotel_tools,communication_tools,web_tools,excel_tools}.py及cloud_drive/inbox相关实现。来源仅用于确定工具语义和接口，不向monitor提供任务私有初始值。
