# TicketAgent 可扩展多 Agent 与 PageAgent 架构治理计划

## Summary

目标是把当前 Demo 型链路升级为可支撑 700+ 发回单场景的可扩展架构：后端五个业务 Agent 保持不新增、不合并；收紧 Agent 数据契约；PageAgent 不编码 700+ 业务规则，而是沉淀为“页面能力层 + 页面适配器 + 结构化 PageTask 协议”。

核心原则：

- 业务规则留在后端 Agent / workflow 配置。
- PageAgent 只做页面执行，不做业务决策。
- 确定性页面动作优先用 custom tools，LLM ReAct 只处理布局不确定、控件歧义和异常恢复。
- 数据审计完整落库，便于复盘、评测和答辩展示。

## Key Changes

### 1. 多 Agent 职责收口

- 保留五个业务 Agent：`ClassifierAgent`、`IntakeAgent`、`ResolutionAgent`、`EscalationAgent`、`NotificationAgent`。
- 旧 `Intent/Extract/Tool/Verify/Reply` shim 仅作为兼容层保留，不再出现在 UI、文档、Agent 列表和答辩口径。
- `EscalationAgent` 内部拆成三个确定性 guard 模块，但不新增后端业务 Agent：
  - `CompletenessGuard`：缺字段、字段有效性。
  - `RiskGuard`：风险等级、人工确认、自动继续权限。
  - `ToolResultGuard`：工具失败、权限冲突、工具结果需人工。
- `Orchestrator.process_ticket()` 改为显式 pipeline context + 统一出口：
  - `_pause(ctx, status, reason)`
  - `_escalate(ctx, reason)`
  - `_finish_review(ctx)`
  - `_fail(ctx, error)`

### 2. Agent 数据契约规范化

新增/统一后端 DTO，Agent 间只传这些结构，不再随手拼 dict：

- `TicketContext`
- `IntentResult`
- `IntakeResult`
- `RiskDecision`
- `ToolPlan`
- `ToolResult`
- `NotificationBundle`
- `PageTaskEnvelope`

运行时启用 AgentCard schema 校验：

- `_run_agent_step()` 执行前校验 input。
- Agent 返回后校验 output。
- 校验失败进入 `FAILED` 或 `PENDING_INFO`，并写入 trace。
- 字段命名策略固定：API/前端/工具参数使用 `camelCase`，数据库使用 `snake_case`，只在 Pydantic/Repository 边界转换。

### 3. PageTask 协议

新增统一 PageTask 协议，替代自然语言 observation 作为主通道。

`PageTaskEnvelope` 最小结构：

```json
{
  "id": "page-task-xxx",
  "source": "call_intake|ai_result|human_command",
  "scene": "call-intake|ticket-reply|evidence-review|human-confirm",
  "riskLevel": "low|medium|high",
  "mode": "auto|suggest|display|stop",
  "businessPayload": {},
  "actions": [],
  "allowedTargets": [],
  "requiresHumanBeforeSubmit": true,
  "stopReason": ""
}
```

PageTask action 不按业务场景命名，只按页面能力命名：

- `fillForm`
- `fillTextarea`
- `selectOption`
- `clickSemantic`
- `locateEvidence`
- `scrollToRegion`
- `openPanel`
- `waitForState`
- `stopForHuman`

发单侧复用现有 `pageTaskHints`，升级为 `PageTaskEnvelope`。回单侧由 Orchestrator 在 `AiProcessResult` 完成时生成 `pageTask`，包含回单草稿、证据编号、风险模式和复核目标。

### 4. PageAgent 可扩展执行层

PageAgent 不写 700+ 业务流程规则，改为三层：

- `PageTaskBridge`：接收后端结构化 PageTask，决定 auto/suggest/display/stop。
- `SemanticPageAdapter`：按页面类型暴露语义目标，不按业务场景编码。
- `PageAgent customTools`：确定性执行页面能力。

新增 custom tools：

- `fill_form_by_targets(fields, targetMap)`
- `fill_textarea_by_target(target, text)`
- `click_semantic_target(target)`
- `select_option_by_label(target, value)`
- `locate_evidence(evidenceIds)`
- `scroll_to_region(region)`
- `wait_for_business_state(state)`
- `stop_for_human(reason)`

保留通用 ReAct DOM index 工具作为兜底，但默认优先 custom tools。修复 `pushObservation()` 生命周期问题：业务上下文必须作为当前 task context 进入执行，不允许在 `execute()` 开始时被清空。

### 5. 前端信息架构收口

企业壳只保留一个主操作入口，根据工单状态切换：

- `open`：启动 AI 处理。
- `pending_info`：请求客户补充。
- `pending_human_confirm`：进入人工确认。
- `pending_human_review`：复核并结案。
- `escalated/failed`：人工接管/查看失败原因。

SunPilot 面板只保留：

- 当前 PageTask 状态。
- 业务信息流。
- 执行动作日志。
- 手动输入兜底。
- 接管按钮。

把“填入 SunPilot 建议 / 插入证据 / 保存草稿 / 结案”等重复按钮合并到回单工作区主流程，二级动作放入更多菜单或上下文按钮。

### 6. 数据治理与审计

执行完整数据治理迁移：

- 新增 `call_records`：通话记录主表。
- 新增 `ticket_drafts`：发单 Agent 草稿、PageTask、确认状态。
- 新增 `page_action_logs`：PageAgent 每步操作审计。
- 新增 `agent_execution_log`：Agent 输入、输出、错误、LLM raw response、token、耗时。
- 扩展 `trace_steps`：增加 `input_json`、`output_json`、`error_message`、`duration_ms`。
- `ai_results.result_json` 作为权威快照，保留少量查询列，由 Repository 统一同步。
- `tool_call_log` 作为工具审计权威表；`mock_tool_history` 只保留 Mock 幂等用途，不再承担审计展示。

## Implementation Order

1. **契约先行**
   - 新增后端 DTO 与前端 TypeScript 类型。
   - 定义 `PageTaskEnvelope`。
   - 修正 evidenceId 获取逻辑，统一从结构化字段读取。

2. **后端编排治理**
   - 引入 `PipelineContext`。
   - 重构 Orchestrator 统一暂停/升级/失败/完成出口。
   - 接入 Agent input/output schema 校验。
   - 让 Orchestrator 产出回单侧 `pageTask`。

3. **PageAgent 能力层**
   - 增加 custom tools。
   - 新增页面语义适配器注册表。
   - 改造 bridge：结构化 PageTask 为主，自然语言 observation 仅用于展示和 LLM 辅助。
   - 修复 `execute()` 清空 observation 导致上下文丢失的问题。

4. **前端 UI 收口**
   - 合并重复按钮和快捷入口。
   - SunPilot 面板从“聊天控制台”改成“任务执行台”。
   - 企业壳按状态显示唯一主动作。

5. **数据库迁移与审计**
   - 新增治理表和 Repository。
   - 写入 Agent 执行日志、PageAgent 操作日志、草稿确认记录。
   - 历史 JSON 样本继续可作为 seed 来源，但运行态读写进入 MySQL。

6. **文档与答辩口径**
   - 更新开发计划、架构图、数据流图。
   - 明确“PageAgent 不编码 700+ 规则，而是页面能力层适配 700+ 流程”。
   - 准备低风险、中风险、高风险三条验收链路。

## Test Plan

- 后端：
  - `compileall ai-engine`
  - Agent schema 校验单测：正常、缺字段、类型错误、LLM 输出漂移。
  - Orchestrator smoke：低风险完成工具调用，中风险暂停确认，高风险升级，工具失败升级。
  - 数据迁移 smoke：新表创建、写入、查询、回放。

- 前端：
  - `npm.cmd run build`
  - PageTaskBridge 单测：auto/suggest/display/stop 分流。
  - custom tools 单测：按 `data-page-agent-target` 填表、填回单、定位证据。
  - UI 状态测试：每个工单状态只出现一个主动作。

- 端到端：
  - 通话发单：`call_records -> ticket_drafts -> PageTask -> 填表 -> 提交工单`。
  - 低风险回单：多 Agent -> Mock Tool -> PageTask -> 填回单/定位证据 -> 人工结案。
  - 中风险确认：多 Agent -> pending_human_confirm -> PageAgent 停在人工作业区。
  - 高风险/工具失败：升级人工，PageAgent 只定位风险原因，不执行保存或结案。

## Assumptions

- 本轮目标选择为“可扩展架构”，优先级高于短期 Demo 微调。
- 本轮纳入完整数据治理，执行前仍需按项目规则确认数据库 schema 变更。
- 不引入 LangGraph；当前问题优先通过类型化上下文、统一出口和 PageTask 协议解决。
- 不新增后端第六个业务 Agent。
- PageAgent 不承载 700+ 业务规则，只沉淀页面能力工具和页面类型适配器。
