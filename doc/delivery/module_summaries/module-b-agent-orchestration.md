# 模块 B：Agent 编排与业务化封装总结

生成日期：2026-07-19

## 1. 模块定位

模块 B 位于 TicketAgent 核心闭环的 Agent 编排层，负责把原来偏技术实现的 Agent 体系，统一整理成业务人员也能理解的工单处理链路。

它承接模块 A 稳定下来的 API、SSE、状态机和持久化契约，在不破坏后端对外结构的前提下，将系统主流程统一到五类业务 Agent：

- `ClassifierAgent`：识别工单类型、业务场景、工作流和优先级。
- `IntakeAgent`：抽取客户号、券类型、交易信息、申请编号等业务字段。
- `EscalationAgent`：判断缺失信息、敏感操作、高风险、人工确认和升级。
- `ResolutionAgent`：选择业务工具，生成工具参数。
- `NotificationAgent`：生成客户回单和处理说明。

没有模块 B 时，系统虽然可以运行，但流程解释会停留在 `IntentAgent`、`ExtractAgent`、`ToolCallingAgent` 这类技术口径上，难以向业务方说明“每个 Agent 在工单处理中到底承担什么职责”。

## 2. 做了什么

模块 B 最终完成了三件事。

第一，统一了业务 Agent 命名。代码、Agent Card、Trace、SSE 事件、前端流程展示和规划文档都切换到 `Classifier`、`Intake`、`Escalation`、`Resolution`、`Notification` 这套业务命名。

第二，重构了 Orchestrator 的主流程边界。每个 Agent 的输入、输出和异常处理被明确下来，流程从“按技术动作串联”变成“按工单业务阶段推进”。

第三，引入轻量 `workflow_config`。业务场景、必填字段、推荐工具、是否需要人工确认和通知模板不再完全散落在 Prompt 或代码里，而是沉淀为可配置的工作流信息。

## 3. 工作原理

模块 B 的核心机制是“Orchestrator 统一调度，Agent 各司其职”。

主流程如下：

```text
工单内容
  -> ClassifierAgent：识别业务场景和 workflow
  -> IntakeAgent：抽取场景所需字段
  -> EscalationAgent：检查字段、风险和人工介入条件
  -> ResolutionAgent：选择工具并生成参数
  -> Mock Tool/API：执行业务动作并返回证据
  -> EscalationAgent：复核工具结果和异常
  -> NotificationAgent：生成回单草稿
```

其中，LLM 主要负责理解自然语言工单、抽取字段、生成工具调用建议和回单文案；确定性规则负责兜底边界，例如：

- 空工单或异常类型回落到 `UNKNOWN`。
- 必填字段缺失时进入 `pending_info`。
- 交易争议、高风险和工具异常进入人工升级。
- 中风险或敏感资料变更进入人工确认。
- Agent 执行异常时，当前 Trace 步骤落为 `FAILED`，再由 Orchestrator 发出统一失败终态。

`workflow_config` 在这个过程中提供业务配置来源。Classifier 根据配置归一工作流，Intake 根据配置抽取字段，Escalation 根据配置检查必填项和人工确认要求，Resolution 根据配置选择推荐工具，Notification 可读取默认通知模板。

## 4. 核心内容

核心 Agent：

- `ai-engine/agents/classifier_agent.py`
- `ai-engine/agents/intake_agent.py`
- `ai-engine/agents/escalation_agent.py`
- `ai-engine/agents/resolution_agent.py`
- `ai-engine/agents/notification_agent.py`

核心编排：

- `ai-engine/orchestrator/orchestrator.py`
- `ai-engine/orchestrator/workflow_config.py`
- `ai-engine/data/workflow_config.json`
- `ai-engine/data/agent_cards.json`

核心兼容设计：

- 旧 Agent 文件短期作为 shim 保留，旧类名只转发到新业务 Agent。
- Orchestrator 保留旧属性别名，降低旧脚本和测试的迁移风险。
- 模块 B 清单中已新增“清理旧模块相关内容”未完成项，后续再集中移除旧 shim、旧测试和旧文档口径。

核心验证：

- `ai-engine/evaluation/smoke_module_b.py`
- 模块 A smoke 回归继续作为契约不破坏的底线。
- 前端构建验证用于确认新 Agent 口径不会破坏展示链路。

## 5. 结果表现

模块 B 完成后，系统具备了更清晰的业务表达能力。

从演示和答辩角度，处理链路可以被解释为：

```text
分类 -> 接单抽取 -> 升级判断 -> 解决执行 -> 通知回单
```

从工程角度，新 Agent 边界更稳定：

- `ClassifierAgent` 输出 `type`、`label`、`confidence`、`workflow_name` 和分类原因。
- `IntakeAgent` 输出结构化 `fields`。
- `EscalationAgent` 输出风险等级、检查项、是否可自动继续、是否缺信息。
- `ResolutionAgent` 输出 `tool_name`、`tool_params`、是否跳过工具。
- `NotificationAgent` 输出回单草稿，并为模块 D 的结构化通知能力打下基础。

从前端角度，流程条、Trace 和 AI 处理面板不再展示旧技术型 Agent 名称，而是展示业务阶段，使非技术观众更容易理解系统正在做什么。

## 6. 代表性例子

### 例子：优惠券补发

输入：客户反馈参加活动后达标，但优惠券未到账。
处理：`ClassifierAgent` 识别为 `COUPON_REISSUE`，`IntakeAgent` 抽取客户号、券类型和补发原因，`EscalationAgent` 判断字段完整且低风险。
结果：`ResolutionAgent` 选择 `coupon.reissue`，后续工具执行生成证据，`NotificationAgent` 生成补发说明。

### 例子：信息不足

输入：客户只说“活动券没收到”，没有说明券类型或活动。
处理：`IntakeAgent` 将关键字段标记为未提供，`EscalationAgent` 根据必填字段规则判断信息不足。
结果：流程暂停为 `pending_info`，系统生成补充信息提示，而不是强行调用补券工具。

### 例子：交易争议

输入：客户反馈一笔非本人消费或疑似盗刷。
处理：`ClassifierAgent` 识别为交易争议，`EscalationAgent` 判断为高风险场景，`ResolutionAgent` 跳过自动工具执行。
结果：流程进入人工升级，Trace 中能看到升级原因，回单说明后续由人工专员跟进。

### 例子：资料变更

输入：客户要求修改账单寄送地址，并提供身份核验状态。
处理：`IntakeAgent` 抽取新地址和核验状态，`EscalationAgent` 判断资料变更属于敏感/中风险操作。
结果：流程进入人工确认，避免系统在人工复核前直接执行敏感资料修改。

## 7. 边界与后续

模块 B 解决的是 Agent 口径、编排边界和配置化入口，不等同于完成所有业务场景自动化。

当前边界：

- 旧 Agent shim 仍处于兼容期，尚未完全删除。
- Dispatcher Agent 仍是 P2 进阶能力，不进入当前核心闭环。
- LangGraph 暂不迁移，当前仍采用手写 Orchestrator 和轻量配置。
- `workflow_config` 是轻量配置，不是完整工作流引擎。
- 真实业务执行能力仍依赖模块 C 的 Mock Tool/API 审计链路继续承接。

后续最直接的收口任务是清理旧模块相关内容：移除旧 Agent shim 文件，更新兼容测试、Orchestrator 旧别名和文档口径，确认系统不再依赖 `IntentAgent`、`ExtractAgent`、`VerifyAgent`、`ToolCallingAgent`、`ReplyAgent`。
