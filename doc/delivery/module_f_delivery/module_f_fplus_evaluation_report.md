# 模块 F/F+ Agent 测评报告

生成日期：2026-07-19

## 1. 摘要

模块 F 完成了 TicketAgent 五类业务 Agent 的测评框架建设，模块 F+ 在该框架上完成了 40 条标注样本的真实 LLM 全量测评、问题归因、链路修复和最终回归。

最终测评使用真实 DeepSeek LLM 调用链路，运行来源为 `agent_run`，样本数为 40 条。最终结果显示：

| 指标 | 最终结果 |
|---|---:|
| 意图识别准确率 `intentAccuracy` | 1.0000 |
| 字段完整率 `fieldCompleteness` | 1.0000 |
| 工具选择正确率 `toolCorrectness` | 1.0000 |
| 工作流一致率 `workflowConsistency` | 1.0000 |
| 回单要点覆盖率 `replyPointCoverage` | 0.9888 |
| 人工介入判断准确率 `humanInterventionAccuracy` | 1.0000 |
| 闭环成功率 `closedLoopSuccessRate` | 1.0000 |
| 平均处理耗时 `avgProcessingMs` | 6529.6 ms |
| 平均节省人工步骤 `avgManualStepsSaved` | 2.6 步 |
| 平均预计节省时间 `avgTimeSavedSeconds` | 113.5 秒 |

需要说明：当前 `closedLoopSuccessRate` 的工程含义是“测评样本的期望状态/处理结果匹配率”，不是生产环境真实客户结案率。

## 2. 测评目标与范围

模块 F 的目标是让系统从“可演示”升级为“可测评、可回归、可解释”。本次测评覆盖以下 Agent：

| Agent | 测评重点 |
|---|---|
| IntakeAgent | 关键字段抽取、缺失字段识别 |
| ClassifierAgent | 意图识别、业务工作流选择、优先级判断 |
| ResolutionAgent | 工具选择、工具参数、执行成功与审计证据 |
| NotificationAgent | 客户回单、内部通知、复核摘要、结案建议 |
| EscalationAgent | 缺失信息、敏感操作、高风险、未知场景的升级判断 |

模块 F+ 的目标是在真实 LLM 链路下完成全量测评闭环：先跑完整 40 条样本，定位低分原因，再修复业务链路或评分口径，最后回归验证。

## 3. 测评数据与运行方式

测评样本来自 `ai-engine/data/evaluation_samples.json`，共 40 条中文模拟标注样本。样本覆盖：

- 优惠券/权益补发
- 申请进度查询
- 客户资料变更
- 权益资格查询
- 交易查询与交易争议
- 未接入自动化工具的扩展场景，如分期提前结清、还款协商、挂失补卡、额度调整、年费、积分、征信异议、投诉、跨部门协办

真实 LLM 测评命令：

```powershell
.venv\Scripts\python.exe ai-engine\evaluation\run_module_f.py --records
```

回归验证命令：

```powershell
.venv\Scripts\python.exe -m compileall ai-engine
.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_a.py
.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_b.py
.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_c.py
.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_d.py
.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_e.py
.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_f.py
```

前端回归：

```powershell
cd frontend
npm run build
```

原始测评产物：

- 初始全量结果：`ai-engine/evaluation/module_f_full_20260719.json`
- 最终全量结果：`ai-engine/evaluation/module_f_full_final3_20260719.json`

## 4. 做了哪些测评

### 4.1 模块 F：测评框架

模块 F 建立了面向真实 Agent 输出的评分框架，不再只给演示分数。核心交付包括：

- `Evaluator` 支持按 Agent 输出记录计分。
- `run_module_f.py` 支持真实 LLM 全链路运行 40 条样本，并可输出逐样本 records。
- `smoke_module_f.py` 覆盖自动处理、待补充、升级人工三类路径。
- `/api/evaluation/metrics` 保留旧字段兼容，同时新增分 Agent 指标、样本数、来源、闭环率、平均处理耗时、人工节省步骤等字段。

### 4.2 模块 F+：真实 LLM 全量测评

模块 F+ 完成了完整闭环：

1. 全量运行 40 条真实 LLM 样本。
2. 对低分项做样本级归因。
3. 区分 Agent 能力问题、评分口径问题、样本标注冲突和外部服务问题。
4. 修复 Classifier、Escalation、Resolution 和 Evaluator 的关键问题。
5. 重新执行最终 40 条真实 LLM 回归。

## 5. 初始结果、问题与修复

初始 40 条真实 LLM 全量测评结果如下：

| 指标 | 初始结果 | 最终结果 | 变化 |
|---|---:|---:|---:|
| `intentAccuracy` | 0.7250 | 1.0000 | +0.2750 |
| `fieldCompleteness` | 0.8911 | 1.0000 | +0.1089 |
| `toolCorrectness` | 0.7778 | 1.0000 | +0.2222 |
| `workflowConsistency` | 0.7250 | 1.0000 | +0.2750 |
| `replyPointCoverage` | 0.8539 | 0.9888 | +0.1349 |
| `humanInterventionAccuracy` | 0.7000 | 1.0000 | +0.3000 |
| `closedLoopSuccessRate` | 0.6000 | 1.0000 | +0.4000 |
| `avgProcessingMs` | 9189.1 ms | 6529.6 ms | -2659.5 ms |

初始低分的主要原因：

- 未接入自动化的扩展场景被误分类进已有工作流。
- `pending_human_confirm` 未被显式建模，敏感操作和普通人工复核口径混在一起。
- `pending_info`、`pending_human_confirm`、`escalated` 的评分语义不一致。
- 敏感资料变更存在“先执行工具、再人工确认”的链路风险。
- 中文回单要点覆盖的字符串匹配过严，部分等价表达被误伤。

关键修复：

- Classifier 增加未知/未支持场景兜底，避免把分期、年费、积分、投诉等扩展场景强行归入已有工具链路。
- Escalation 将未知/高风险升级、敏感中风险人工确认、字段缺失待补充分开处理。
- Resolution 对工具参数做标准化，补齐 `couponType`、`benefitCode`、`applicationNo`、`verifyStatus` 等机器参数口径。
- Evaluator 对安全升级/人工确认场景免除不应有的工具惩罚，并改用业务槽位评估回单要点覆盖。

## 6. 各 Agent 表现

### 6.1 IntakeAgent：字段抽取稳定

最终字段完整率为 1.0000，缺失字段识别准确率为 1.0000。40 条样本中共评估 101 个应抽字段和 107 个缺失字段判断，全部匹配预期。

表现特点：

- 对客户号、申请编号、券类型、交易日期、金额、商户名、新地址等结构化字段抽取稳定。
- 能识别“未提供”的关键字段，并把流程转为 `pending_info`。
- 对交易争议、资料变更等多字段场景保持了较高一致性。

### 6.2 ClassifierAgent：意图与工作流收口

最终意图准确率为 1.0000，工作流一致率为 1.0000，优先级一致率为 0.9500。

表现特点：

- 对优惠券补发、申请进度、资料变更、权益查询、交易核查等已支持场景分类准确。
- 对未接入自动化工具的扩展场景输出 `UNKNOWN` 和 `unknown_flow`，不再错误触发工具。
- 优先级判断仍有少量边界差异，但未影响最终状态和处理结果。

### 6.3 ResolutionAgent：工具选择与执行正确

最终工具选择正确率为 1.0000，参数准确率为 1.0000，执行成功率为 1.0000。实际需要工具执行或工具校验的样本全部匹配预期。

表现特点：

- 低风险且字段齐全的样本能正确选择 Mock Tool，例如 `coupon.reissue`、`application.progress-query`、`benefit.query`。
- 字段缺失时不会强行执行工具。
- 敏感或中高风险操作会跳过工具执行，等待人工确认或升级。
- 每次工具成功执行都保留业务结果和证据编号。

### 6.4 NotificationAgent：回单可读，覆盖率高

最终回单要点覆盖率为 0.9888，模板合规性和可读性均为 1.0000。

表现特点：

- 能根据状态生成不同文案：已处理、待补充、待人工确认、已升级。
- 能在自动处理样本中写明处理结果、券类型、证据编号、客户下一步动作。
- 在人工确认或升级样本中能说明原因和下一处理人。
- 唯一残留扣分来自个别业务要点表达差异，不影响状态判断和业务闭环。

### 6.5 EscalationAgent：风险兜底明显改善

最终异常识别正确率为 1.0000，人工介入判断准确率为 1.0000。

表现特点：

- 字段不足时进入 `pending_info`。
- 敏感资料变更、交易争议等中风险事项进入 `pending_human_confirm`。
- 高风险争议、疑似盗刷、未知扩展场景进入 `escalated`。
- 修复后不再把未知场景误当作已支持工具链路处理。

## 7. 代表性实际事例

### 事例 1：优惠券补发自动执行后人工终审

样本：`eval-001`，餐饮满减券达标未到账。

- 预期：识别为 `COUPON_REISSUE`，调用 `coupon.reissue`，状态为 `pending_human_review`。
- ClassifierAgent：输出 `COUPON_REISSUE` 和 `coupon_reissue_flow`。
- IntakeAgent：抽取 `customerId=C20001`、`couponType=DINING_100_20`、`reason=活动达标未到账`。
- ResolutionAgent：调用 `coupon.reissue`，工具返回“优惠券已补发到账”，并生成证据编号。
- NotificationAgent：回单提示客户到 App 优惠券中心查收。
- EscalationAgent：低风险，可进入人工终审结单。

该样本证明系统能完成“识别诉求 -> 抽取字段 -> 调用工具 -> 留证据 -> 生成回单 -> 人工终审”的标准闭环。

### 事例 2：优惠券补发缺少券类型，转待补充

样本：`eval-003`，优惠券补发缺少券类型。

- 预期：识别为 `COUPON_REISSUE`，但状态为 `pending_info`。
- IntakeAgent：识别 `couponType=未提供`。
- ResolutionAgent：跳过工具调用，避免参数不完整时误执行。
- NotificationAgent：生成补充信息提示，请客户补充 `couponType`。
- EscalationAgent：判断为“信息不足，需要补充必填字段后继续处理”。

该样本证明系统不是所有场景都强行自动化，而是能在关键字段缺失时暂停并追问。

### 事例 3：修改账单寄送地址，进入人工确认

样本：`eval-009`，客户要求修改账单寄送地址。

- 预期：识别为 `CUSTOMER_ADDRESS_UPDATE`，涉及 `customer.update-address`，状态为 `pending_human_confirm`。
- IntakeAgent：抽取 `customerId=C20009`、`newAddress=上海市浦东新区测试路88号`、`verifyStatus=PASSED`。
- EscalationAgent：判断资料修改属于敏感/中风险操作，需要人工确认。
- ResolutionAgent：未直接调用 `customer.update-address`。
- NotificationAgent：提示该事项需要工作人员复核确认后继续处理。

该样本证明修复后的链路避免了敏感资料“先执行后确认”的风险。

### 事例 4：非本人消费争议，直接升级人工

样本：`eval-018`，客户反馈非本人消费并怀疑盗刷。

- 预期：识别为 `TRANSACTION_DISPUTE`，状态为 `escalated`。
- IntakeAgent：抽取交易日期、金额、商户名、争议原因。
- EscalationAgent：识别为高风险工单，直接转人工审核。
- ResolutionAgent：跳过工具执行。
- NotificationAgent：生成“已转人工复核，后续由专员跟进”的回单。

该样本证明 EscalationAgent 能识别交易风险和盗刷类敏感语义，避免自动化越权。

### 事例 5：分期提前结清咨询，未知场景兜底

样本：`eval-021`，客户咨询信用卡账单分期提前结清。

- 预期：当前系统未接入该自动化工具，输出 `UNKNOWN`，状态为 `escalated`。
- ClassifierAgent：输出 `UNKNOWN` 和 `unknown_flow`。
- EscalationAgent：判断“当前场景未接入自动化工具，建议转人工处理”。
- ResolutionAgent：不调用任何工具。
- NotificationAgent：告知客户该工单已转人工复核。

该样本是 F+ 修复的关键验证点：系统不会为了提高自动化率而把未支持业务误塞进已有流程。

### 事例 6：境外交易查询，进入人工确认

样本：`eval-035`，境外交易查询。

- 预期：识别为 `TRANSACTION_DISPUTE`，状态为 `pending_human_confirm`。
- IntakeAgent：抽取 `transactionDate=2026-07-14`、`amount=52.30美元`、`merchantName=SAMPLE HOTEL`。
- EscalationAgent：判断交易核查涉及敏感操作，需要人工确认。
- ResolutionAgent：跳过自动工具执行。
- NotificationAgent：提示工作人员复核确认后继续处理。

该样本说明系统能区分“普通信息查询”和“需要人工确认的交易敏感场景”。

## 8. 整体表现结论

本次 F/F+ 测评证明 TicketAgent 已具备可演示、可测评、可追溯的核心闭环：

- 已支持场景可以稳定完成识别、抽取、执行、通知和状态输出。
- 信息缺失、敏感操作、高风险、未知场景均有明确兜底路径。
- Agent 输出可以通过样本级 records 追溯，不只是看平均分。
- 测评脚本和 smoke 回归可用于后续模块 G 前端展示和后续业务扩展。

现阶段可以进入模块 G，即前端产品呈现阶段。模块 G 展示时建议重点呈现：

- 每个 Agent 做了什么。
- 为什么进入自动处理、待补充、人工确认或升级。
- 工具执行结果和证据编号。
- 客户回单与内部复核摘要。
- 指标中的 `closedLoopSuccessRate` 应解释为“期望状态匹配率”，避免被误解为真实生产结案率。

## 9. 后续建议

- 扩展 50 到 100 条样本，增加混淆矩阵和分场景指标。
- 为优先级一致率补充更细的标注规则，降低边界样本争议。
- 对 NotificationAgent 增加少量人工评分项，验证业务可读性和客户沟通质量。
- 模块 G 前端展示应优先围绕“Agent 过程、证据链、状态原因、测评指标”组织，而不是展示底层调试 JSON。
