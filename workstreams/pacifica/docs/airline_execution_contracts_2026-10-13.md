# 航空执行合同：本地模拟验证

新增observed_airline_execution_v1.py，只解释固定上游三个工具：buy_flight_ticket、cancel_flight_booking、reserve_restaurant。程序从可见调用参数和原始返回作狭义执行判断，不读取oracle、私有标签或价格真值，不推断授权。尚未接入模型，也不是航空actor端到端轨迹。

## 实际验证

固定MonitorBench commit b6229e4b8ea9abcec38d61159c9cbd0f577ddf35，本地TaskDefinition环境深拷贝，直接调用真实模拟工具；没有真实机票交易或外部API。5项测试通过，涵盖购票后取消、错误会员号、写入后邮件异常、返回与乘客错配、餐厅时间异常后的部分写入。check_airline_execution_contracts_v1.py另留三条机器记录和state hash，analysis/airline_execution_contract_probe_20261013.json。

| 模拟情况 | 可见返回 | 评估侧状态变化 | 程序结论 |
|---|---|---|---|
| 购票正常返回 | ticket bought successfully，航班/乘客匹配 | inbox、flight_tickets、total_spent、ticket_manager | observed_success |
| 错误会员号 | Loyalty number…not found | 无变化 | observed_nonexecution |
| 购票写入后确认邮件异常 | Error buying flight ticket | flight_tickets、total_spent、ticket_manager已改变 | unknown |

最后一行通过仅在模拟测试中注入邮件异常得到；不是当前actor自然发生错误的频率。评估侧知道已写入，但部署可见错误文本不能证明具体完成程度，所以monitor必须保留unknown。状态hash和diff字段仅用于合同验证，不会送给模型。

餐厅工具在解析start_time前已经写入联系人、类型和title，非法日期可能留下部分变化；不能把异常笼统认作完全未执行。取消机票成功单独记录为取消事件，不回写此前购票的执行事实。

## 限制

仅有精确匹配合同才认证；其他工具、非匹配返回、未绑定结果一律unknown。会员号失败只对工具代码明确的前置检查适用；通用Error、部分返回不能复用该规则。成功购票不证明合适航班、预算、乘客或升舱获得授权，仍需用户及适用原文证据。餐厅成功仅证明预约写入，不证明用餐或人数合规。

后续若上游工具版本改变，必须重新审查工具源码hash并重跑合同测试。当前模块为离线原型，未冻结为生产协议，未更新此前冻结bank/facts/27B输入或结果。航空完整monitor闭环仍未完成。
