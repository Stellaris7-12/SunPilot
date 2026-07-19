# 模块 F/F+：Agent 测评与真实 LLM 回归总结

生成日期：2026-07-19

## 1. 模块定位

模块 F 位于 TicketAgent 核心闭环的效果评估层，负责回答一个关键问题：系统不是只在演示样例里“看起来能跑”，而是能不能用统一样本、统一指标和真实 Agent 输出证明它确实更准、更规范、更可追溯。

它承接模块 E 的标注样本集，评估模块 B 到 D 中形成的五类业务 Agent：

- `IntakeAgent`：字段抽取和缺失信息识别。
- `ClassifierAgent`：意图、工单类型、工作流和优先级判断。
- `ResolutionAgent`：工具选择、参数生成、执行结果和证据链。
- `NotificationAgent`：客户回单、内部通知、复核摘要和结案建议。
- `EscalationAgent`：缺失信息、敏感操作、高风险和未知场景兜底。

模块 F+ 是模块 F 的收口阶段：在真实 DeepSeek LLM 调用链路下完成 40 条样本全量测评，并把低分项转化为可定位、可修复、可回归的问题。

## 2. 做了什么

模块 F/F+ 最终沉淀了三类能力。

第一，建立了真实 Agent 输出的评分框架。系统不再只给固定演示分数，而是基于每条样本的实际运行记录，分别计算字段、分类、工具、通知、升级和端到端结果。

第二，打通了真实 LLM 全量测评入口。`run_module_f.py` 可以读取 40 条评测样本，逐条运行五类 Agent 链路，并保存完整 records，便于从平均指标追溯到单个样本。

第三，完成了 F+ 全量回归和链路修复。初始 40 条真实 LLM 测评暴露出未知场景误分类、人工确认状态缺失、敏感资料先执行工具等问题；修复后重新跑完 40 条样本，核心指标全部收口。

## 3. 工作原理

模块 F 的输入是 `ai-engine/data/evaluation_samples.json` 中的 40 条标注样本。每条样本包含工单原文、期望意图、期望字段、期望工具、期望状态、回单要点和是否需要人工介入。

测评链路会模拟真实处理过程：

1. `ClassifierAgent` 判断意图和工作流。
2. `IntakeAgent` 抽取结构化字段并识别缺失字段。
3. `EscalationAgent` 判断是否信息不足、敏感、风险较高或未知场景。
4. `ResolutionAgent` 在允许自动执行时选择工具并生成参数。
5. Mock Tool/API 返回业务结果和证据编号。
6. `NotificationAgent` 生成客户回单、内部通知、复核摘要和结案建议。
7. `Evaluator` 把实际输出和标注期望逐项对比，生成 Agent 分项指标和端到端指标。

这里采用“规则兜底 + LLM 理解”的机制：口语化、复杂表达交给 LLM 判断，但工作流名称、未知场景兜底、敏感操作确认、工具参数规范化和评分口径由确定性规则约束。这样做的目的不是让 LLM 自由发挥，而是让 LLM 在受控业务边界内完成理解和生成。

## 4. 核心内容

核心脚本：

- `ai-engine/evaluation/evaluator.py`：计算 Agent 分项指标和端到端指标。
- `ai-engine/evaluation/run_module_f.py`：真实 LLM 全链路测评入口，支持保存 records 和按样本 ID 回归。
- `ai-engine/evaluation/smoke_module_f.py`：不依赖真实 LLM 的评测逻辑冒烟测试。

核心指标：

- `intentAccuracy`：意图识别准确率。
- `fieldCompleteness`：字段完整率。
- `toolCorrectness`：工具选择正确率。
- `workflowConsistency`：工作流一致率。
- `replyPointCoverage`：回单要点覆盖率。
- `humanInterventionAccuracy`：人工介入判断准确率。
- `closedLoopSuccessRate`：期望状态/处理结果匹配率。
- `avgProcessingMs`：平均处理耗时。
- `avgManualStepsSaved`：平均节省人工步骤。
- `avgTimeSavedSeconds`：平均预计节省时间。

核心产物：

- 初始全量测评：`ai-engine/evaluation/module_f_full_20260719.json`
- 最终全量测评：`ai-engine/evaluation/module_f_full_final3_20260719.json`
- 详细测评报告：`doc/module_f_delivery/module_f_fplus_evaluation_report.md`

说明：`module_f_*.json` 是真实运行产物，已通过 `.gitignore` 忽略，不作为文档交付物提交。

## 5. 结果表现

最终全量测评使用真实 DeepSeek LLM 调用链路，运行来源为 `agent_run`，样本数为 40 条。

| 指标 | 初始结果 | 最终结果 |
|---|---:|---:|
| `intentAccuracy` | 0.7250 | 1.0000 |
| `fieldCompleteness` | 0.8911 | 1.0000 |
| `toolCorrectness` | 0.7778 | 1.0000 |
| `workflowConsistency` | 0.7250 | 1.0000 |
| `replyPointCoverage` | 0.8539 | 0.9888 |
| `humanInterventionAccuracy` | 0.7000 | 1.0000 |
| `closedLoopSuccessRate` | 0.6000 | 1.0000 |
| `avgProcessingMs` | 9189.1 ms | 6529.6 ms |

最终分 Agent 表现：

- `IntakeAgent`：字段完整率 1.0000，缺失字段识别准确率 1.0000。
- `ClassifierAgent`：意图准确率 1.0000，工作流一致率 1.0000，优先级一致率 0.9500。
- `ResolutionAgent`：工具选择正确率 1.0000，参数准确率 1.0000，执行成功率 1.0000。
- `NotificationAgent`：回单要点覆盖率 0.9888，模板合规性 1.0000，可读性 1.0000。
- `EscalationAgent`：异常识别正确率 1.0000，人工介入判断准确率 1.0000。

这里的 `closedLoopSuccessRate` 表示“测评样本的期望状态/处理结果匹配率”，不是生产环境真实客户结案率。

## 6. 代表性例子

### 例子：优惠券补发自动执行

输入：客户反馈参加餐饮满减活动后达标，但 App 优惠券中心未收到 `DINING_100_20` 券。
处理：`ClassifierAgent` 识别为 `COUPON_REISSUE`，`IntakeAgent` 抽取客户号、券类型和补发原因，`ResolutionAgent` 调用 `coupon.reissue`。
结果：工具返回“优惠券已补发到账”和证据编号，`NotificationAgent` 生成客户回单，状态进入 `pending_human_review`。

### 例子：优惠券补发缺少券类型

输入：客户表示活动达标但未收到优惠券，未提供具体券类型。
处理：`IntakeAgent` 识别 `couponType` 缺失，`EscalationAgent` 判定信息不足，`ResolutionAgent` 跳过工具执行。
结果：状态进入 `pending_info`，系统生成补充信息提示，要求客户补充券类型后继续处理。

### 例子：资料变更需要人工确认

输入：客户要求修改账单寄送地址，并提供新地址和身份核验通过状态。
处理：`ClassifierAgent` 识别为 `CUSTOMER_ADDRESS_UPDATE`，但 `EscalationAgent` 判定资料变更属于敏感/中风险操作。
结果：`ResolutionAgent` 不直接调用 `customer.update-address`，状态进入 `pending_human_confirm`，系统提示工作人员复核确认后继续。

### 例子：非本人消费争议直接升级

输入：客户反馈一笔非本人消费，并怀疑卡片被盗刷。
处理：`IntakeAgent` 抽取交易日期、金额、商户名和争议原因，`EscalationAgent` 识别为高风险交易争议。
结果：系统跳过自动工具执行，状态进入 `escalated`，回单说明已转人工专员跟进。

### 例子：分期提前结清咨询走未知场景兜底

输入：客户咨询信用卡账单分期提前结清的手续费和办理入口。
处理：该场景当前未接入自动化工具，`ClassifierAgent` 输出 `UNKNOWN` 和 `unknown_flow`。
结果：系统不强行套用已有工具链路，状态进入 `escalated`，由人工复核处理。

## 7. 边界与后续

模块 F 证明的是当前标注样本集上的 Agent 链路效果，不等同于生产环境全量业务效果。

当前边界：

- 工具层仍是 Mock Tool/API，真实银行业务接口接入后需要重新评测工具成功率和异常分布。
- `closedLoopSuccessRate` 是期望状态匹配率，不是真实客户结案率。
- 回单可读性当前是规则评分和少量人工判断口径，后续可增加正式人工评分。
- 样本规模为 40 条 MVP 集，适合演示和阶段性回归；后续严肃评估应扩展到 50 到 100 条以上，并增加混淆矩阵和分场景指标。

后续模块 G 应把这些结果产品化展示，让非技术观众能看到：每个 Agent 做了什么、为什么进入某个状态、工具是否执行、证据编号是什么、客户回单是否可用，以及系统预计节省了多少人工步骤和处理时间。
