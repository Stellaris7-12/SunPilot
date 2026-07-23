# TicketAgent 进度日志

> 当前 active 进度只保留高信号摘要；长篇历史见 `doc/planning/backup/` 与 git 历史。

## 2026-07-21 至 2026-07-22 汇总

### 已完成

- 模块 K：系统默认收口到 MySQL/TDSQL，移除 SQLite 运行口径；I1/I2/I3 smoke 使用 `ticket_agent_test`，演示库与测试库分离。
- Mock Tools：补齐客户、卡、交易、权益、申请等 seed 与查询容错；权益码、交易流水、非数字金额等演示问题已修复。
- 模块 O：`ResolutionAgent` 接入原生 tool calling；工具 schema、候选工具过滤、参数归一化、未知工具兜底和人工边界已收口。
- 模块 M：`frontend/src/page-agent/` 切换为 Ali page-agent fork 的 ReAct 执行层，包含 `PageAgentCore`、`PageController`、DOM 脱水、W3C actions、SimulatorMask、LLM client 与 Vue Panel。
- PageAgent/SunPilot：通过后端 `/api/llm/proxy` 调用阿里云百炼，默认 `ALI_API_KEY + qwen3.7-plus`，Key 不暴露到前端。
- 业务 Agent：继续使用 DeepSeek，默认 `DEEPSEEK_API_KEY + deepseek-chat`。
- 发单链路：通话样本生成标准工单草稿，SunPilot 可见填表、提交并进入工单详情。
- 回单链路：SunPilot 可启动/跟随后端多 Agent，填入回单草稿，定位证据与审计区域，停在人工复核结案节点。
- UI 收口：PageAgent 命名为 SunPilot；侧边栏改浅色；模型选择放入输入框右下角；Key 配置移到底部；右侧隐藏按钮改为贴边小箭头；禁用自动进入页面即执行，改为业务信息到达后等待坐席唤起。
- 识别边界：SunPilot 侧边栏和运行遮罩被排除出 PageAgent DOM 观察与高亮范围；鼠标与识别框改小、改淡。
- 配置收口：`ai-engine/config.py` 增加 `get_env()`，先读当前进程环境变量，Windows 下再读 User/Machine 环境变量；真实 Key 仍不写入代码。
- 文档收口：启动指南改为全项目指南，配置口径改为通过 `config.py` 读取系统环境变量。

### 验证记录

- `.venv\Scripts\python.exe -m compileall ai-engine` 通过。
- `frontend` 下 `npm.cmd run build` 多次通过。
- `smoke_module_i3_mock_tools.py`、`smoke_module_k_workflow_routing.py`、`smoke_module_o_tool_calling.py` 曾通过。
- PageAgent Qwen proxy 直连探针曾返回 200 且包含 tool call。
- 浏览器运行态曾完成：生成发单草稿 -> SunPilot 可见填单提交 -> 新工单详情 -> 多 Agent 处理 -> 回单草稿写入 -> 证据定位。

### 当前边界

- 自动流程不能直接结案，仍需人工复核。
- MVP 暂不实现生产级 PolicyLayer、风险分级拦截、持久化 PageActionLog、真实 ASR、外部遗留系统自动化。
- SunPilot 侧栏里的 Key/模型设置只影响当前后端进程；长期配置仍以系统环境变量为准。

### 下一步

- 模块 N：准备演示脚本和答辩材料。
- 可选增强：PageActionLog 持久化、PolicyLayer、更多高风险门禁、真实 ASR、外部系统自动化样例。

## 2026-07-23 架构治理计划执行

### 已完成

- 分支已切换到 `feature/sunpilot-agent-architecture`，使用常规 feature 分支命名。
- 按 `doc/planning/PLAN1.md` 推进契约先行：新增 `orchestrator/schema_validator.py`，支持 AgentCard 当前使用的 JSON Schema 子集（object/string/number/integer/boolean/array/null、required、properties、items、enum、additionalProperties=false）。
- `Orchestrator._run_agent_step()` 已在 Agent 执行前校验 input、执行后校验 output；失败会进入原有 trace/SSE failed 路径并让流程终止为 failed。
- 新增 `smoke_module_p_agent_contracts.py`，覆盖正常 payload、缺字段、类型错误、枚举漂移。
- 按 `PLAN1.md` 将 `EscalationAgent` 内部确定性逻辑拆为 `CompletenessGuard`、`RiskGuard`、`ToolResultGuard`；仍然只保留一个后端业务 Agent，不新增第六个 Agent。
- 按 `PLAN1.md` 推进 Orchestrator 统一出口第一阶段：新增 `_complete_with_notification()`，先收敛待补充、升级、人工确认、工具缺参、高风险这些早退路径，不改变 SSE event、状态枚举或 `AiProcessResult` 契约。

### 验证记录

- `.venv\Scripts\python.exe -m compileall ai-engine` 通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_p_agent_contracts.py` 通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_k_workflow_routing.py` 通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_o_tool_calling.py` 通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_m_call_intake.py` 通过。
- `frontend` 下 `npm.cmd run build` 通过。
- guard 拆分后复跑 `.venv\Scripts\python.exe -m compileall ai-engine`、`smoke_module_k_workflow_routing.py`、`smoke_module_p_agent_contracts.py` 通过。
- 统一出口第一阶段后复跑 `.venv\Scripts\python.exe -m compileall ai-engine`、`smoke_module_p_agent_contracts.py`、`smoke_module_k_workflow_routing.py`、`smoke_module_o_tool_calling.py`、`smoke_module_m_call_intake.py` 通过。
- `smoke_module_d.py` 已修复并通过：切换到 `ticket_agent_test` reset 流程，移除同步 `TestClient` 多 loop 生命周期，改为直接调用 async endpoint/编排函数；同时修复旧 SQLite 时间函数、缺失 `customer_id`、MySQL count row 映射，以及字段补全后缺失字段预期。
- PageAgent 能力层继续收口：新增前端 `semanticAdapter.ts` 与 `taskBridge.ts`，把页面语义目标注册、PageTask 执行策略/指令生成从 `bridge.ts` 和 Panel 中拆出；补齐 `wait_for_business_state` custom tool。
- 前端信息架构继续收口：详情页顶部不再重复展示结案主按钮，保存草稿/提交复核并结案统一放在回单工作区，并把 `page-agent-save-draft`、`page-agent-close-ticket` 语义 target 迁移到回单工作区按钮。
- 前端 `npm.cmd run build` 复跑通过。

### 当时边界

- `PLAN1.md` 中数据库治理与审计迁移涉及新增表和 schema 变更，按项目规则当时需用户明确确认后再执行；该项已在后续收到用户确认后落地并验证。

### 2026-07-23 本轮继续推进

- 按 `PLAN1.md` 补齐非 DB 的 Agent 数据契约收口：新增 `ai-engine/models/agent_contracts.py`，将 `TicketContext`、`IntakeResult`、`RiskDecision`、`ToolPlan` 以及 5 个 Orchestrator-to-Agent input DTO 作为统一构造入口。
- `Orchestrator` 已改为通过 `ClassifierInput`、`IntakeInput`、`EscalationInput`、`ResolutionInput`、`NotificationInput` 构造 Agent payload，再交给 AgentCard schema 校验；同时对 `IntentResult`、`IntakeResult`、`RiskDecision`、`ToolPlan` 做运行时归一化。
- `TicketContext` 统一生成三类上下文：给分类/抽取 Agent 的文本摘要、给 ResolutionAgent 的结构化工单快照、给 Escalation/Notification 的风险与通知上下文，减少字段散拼和命名漂移。
- 补强 `smoke_module_p_agent_contracts.py`，覆盖 DTO 构造、`TicketContext` camelCase/snake_case 边界、`ToolPlan` 与 `RiskDecision` 基本结构。
- 前端新增 `frontend/scripts/smoke-page-agent.mjs` 与 `npm.cmd run smoke:page-agent`，静态校验 PageTask mode/scene/action 枚举、SemanticPageAdapter 场景覆盖、自定义工具注册，以及 auto-run 必须受 `requiresHumanBeforeSubmit` 门禁约束。

### 本轮验证记录

- `.venv\Scripts\python.exe -m compileall ai-engine` 通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_p_agent_contracts.py` 通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_k_workflow_routing.py` 通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_o_tool_calling.py` 通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_m_call_intake.py` 通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_d.py` 通过。
- `frontend` 下 `npm.cmd run smoke:page-agent` 通过。
- `frontend` 下 `npm.cmd run build` 通过。

### 当时仍需继续

- 数据库治理与审计迁移当时仍需用户确认；该项已在后续确认后完成：`call_records`、`ticket_drafts`、`page_action_logs`、`agent_execution_log`，以及 `trace_steps` 扩展字段。
- 前端 smoke 当前为静态协议检查，后续可在引入测试框架或 Playwright 后升级为真实 DOM 操作测试。
- Legacy `PageAssistantPanel.vue` 仍作为兼容 wrapper 存在，但旧路由和主文档口径已收口到 SunPilot `AgentPanel`。

### 2026-07-23 前端 AI 入口继续收口

- 旧版详情页 `LegacyTicketDetailView.vue` 已从 `PageAssistantPanel` 切换为新的 SunPilot `AgentPanel`，旧路由下也不再单独渲染旧 AI 动作栏。
- `AppHeader.vue` 移除“启动 AI 辅助 / 清空当前建议”按钮，只保留案件标题、场景和状态信息，避免 SunPilot 外出现 AI 处理入口。
- `PageAssistantPanel.vue` 改为兼容 wrapper，内部直接挂载 `AgentPanel` 并映射旧事件，不再保留旧按钮 UI。
- `AgentTraceTimeline.vue` 与旧版空状态文案改为提示“在 SunPilot 中启动辅助”，避免形成第二个 AI 入口的认知。
- `frontend/scripts/smoke-page-agent.mjs` 增加前端入口治理检查：`AppHeader` 不得出现 AI 处理按钮，旧详情页必须挂载 `AgentPanel`，`PageAssistantPanel` 不得再渲染旧 AI 按钮文案。

### 本轮前端验证记录

- `frontend` 下 `npm.cmd run smoke:page-agent` 通过。
- `frontend` 下 `npm.cmd run build` 通过。
- `rg -n "启动 AI 辅助|重新生成建议|清空当前建议|PageAssistantPanel" frontend\src` 无匹配。

### 2026-07-23 PageTask 确定性执行层

- `PageAgentCore` 新增公开 `runTool(toolName, toolInput, signal)`，可在不进入 LLM ReAct 循环的情况下执行已注册 custom tool，并沿用现有 activity 事件给 SunPilot 展示执行过程。
- 新增 `frontend/src/page-agent/pageTaskExecutor.ts`，将结构化 PageTask action 映射为确定性工具调用：`fillForm -> fill_form_by_targets`、`fillTextarea -> fill_textarea_by_target`、`selectOption -> select_option_by_label`、`locateEvidence -> locate_evidence`、`scrollToRegion -> scroll_to_region`、`waitForState -> wait_for_business_state`、`stopForHuman -> stop_for_human`。
- `AgentPanel.vue` 的“执行当前结构化 PageTask”路径已优先走确定性执行器；若确定性动作失败，才切换 ReAct 兜底处理布局缺失、目标歧义或异常恢复。
- 确定性执行器会校验 action target 必须在 `allowedTargets` 内，且 `page-agent-save-draft`、`page-agent-close-ticket` 等点击目标被门禁阻断，避免 PageAgent 绕过人工复核/结案边界。
- `frontend/scripts/smoke-page-agent.mjs` 增加确定性执行层检查，确保 PageTask executor、危险点击门禁和 ReAct fallback 入口存在。

### 本轮 PageTask 验证记录

- `frontend` 下 `npm.cmd run smoke:page-agent` 通过。
- `frontend` 下 `npm.cmd run build` 通过。

### 2026-07-23 架构审查报告与守护检查

- 新增 `doc/issue/架构治理审查报告_20260723.md`，将本轮治理后的结论固化为可审查/答辩口径：后端只保留 5 个业务 Agent，旧 shim 不进主口径；Agent 间通过 DTO + AgentCard schema 传输；PageAgent/SunPilot 通过 PageTask、SemanticPageAdapter 和 deterministic custom tools 适配 700+ 场景，ReAct 只做兜底。
- 报告中补充按优先级修改清单：P0 守住 5 Agent、人工门禁、PageTask 点击限制和 DTO 校验；P1 再做数据库审计、workflow DTO、schema/DTO 同步和真实 DOM 测试；P2 准备架构图、数据流图和三条验收链路。
- 新增 `ai-engine/evaluation/smoke_module_p_architecture_guardrails.py`，静态守护架构约束：`agent_cards.json` 必须只暴露 5 个业务 Agent，旧 shim/Dispatcher 不得注册；`Orchestrator` 必须按 5 Agent 接线；前端 Header/legacy 入口不得重新出现 SunPilot 外 AI 处理按钮。

### 本轮架构验证记录

- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_p_architecture_guardrails.py` 通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_p_agent_contracts.py` 通过。
- `.venv\Scripts\python.exe -m compileall ai-engine` 通过。
- `frontend` 下 `npm.cmd run smoke:page-agent` 通过。
- `frontend` 下 `npm.cmd run build` 通过。

### 2026-07-23 Workflow 配置契约收口

- 新增 `ai-engine/models/workflow.py`，定义 `WorkflowConfig`、`WorkflowScenario`、`WorkflowField`，并提供 `workflow_scenario()`、`workflow_scenario_names()`、`workflow_default_name()` 统一访问器。
- `orchestrator/workflow_config.py` 的 `load_workflow_config()` 已在读取 JSON 后进行 DTO 校验，再输出兼容现有 AgentCard schema 的 runtime dict；内置默认配置也走同一校验路径。
- `IntakeAgent`、`EscalationAgent`、`ResolutionAgent`、`NotificationAgent` 与 `Orchestrator._run_field_enrichment()` 的高频 workflow 读取点已从散 `.get("scenarios")` 改为统一访问器，减少扩展 700+ 场景时的字段漂移。
- 新增 `smoke_module_p_workflow_contracts.py`，检查 `workflow_config.json` 场景枚举与 `ClassifierAgent` AgentCard output enum 完全一致；检查每个非 UNKNOWN 场景具备 `recommended_tool`，必填字段必须属于配置字段；检查发单侧 `_detect_call_scenario()` 不再输出旧 `CUSTOMER_INFO_UPDATE` / `TRANSACTION_QUERY` 枚举；检查发单侧 `PageTask` 仍产出 `fillForm` 和 `clickSemantic` action。
- 本轮曾发现 `smoke_module_o_tool_calling.py` 会传只包含 `recommended_tool` 的局部 workflow_config，已将 `WorkflowScenario.workflow_name/label` 设为可缺省，保持旧 smoke 和局部配置兼容；正式配置完整性由 `smoke_module_p_workflow_contracts.py` 兜底。

### 本轮 Workflow 验证记录

- `.venv\Scripts\python.exe -m compileall ai-engine` 通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_k_workflow_routing.py` 通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_p_agent_contracts.py` 通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_p_workflow_contracts.py` 通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_p_architecture_guardrails.py` 通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_o_tool_calling.py` 通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_m_call_intake.py` 通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_d.py` 通过。
- `frontend` 下 `npm.cmd run smoke:page-agent` 通过。
- `frontend` 下 `npm.cmd run build` 通过。

### 2026-07-23 架构图与验收链路文档

- 新增 `doc/guides/架构与验收链路_20260723.md`，作为 `PLAN1.md` 文档与答辩口径阶段的 guide。
- 文档补齐多 Agent 编排图、Agent 数据契约图、PageAgent 适配 700+ 场景的能力层图，以及通话发单/回单两条 sequence 数据流。
- 文档明确验收链路：架构守护、低风险回单、发单草稿、前端 SunPilot/PageAgent，并列出对应 smoke/build 命令和检查点。
- 文档继续固化关键边界：PageAgent/SunPilot 不是后端第六个业务 Agent，不编码 700+ 业务规则，不绕过人工保存、提交、结案或转派。

### 当前剩余

- 数据库治理与审计迁移已完成并通过 smoke。
- 前端真实 DOM/Playwright 行为测试仍是可选增强；当前已覆盖静态协议和构建验证。

### 本轮文档验证记录

- `git diff --check` 通过；仅输出 Windows LF/CRLF 提示，无空白错误。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_p_architecture_guardrails.py` 通过。
- `frontend` 下 `npm.cmd run smoke:page-agent` 通过。

### 2026-07-23 EvidenceId 契约补强

- 补强 `ai-engine/evaluation/smoke_module_p_agent_contracts.py`，增加回单侧 PageTask 证据编号来源断言。
- 新断言覆盖 `Orchestrator._build_reply_page_task()`：`businessPayload.evidenceIds` 和 `locateEvidence` action 必须来自结构化 `tool_response.evidenceId/evidence_id` 与 `fieldEnrichment.evidenceIds`，不得从回单正文或工具 message 文本中解析伪证据编号。

### 本轮 EvidenceId 验证记录

- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_p_agent_contracts.py` 通过。
- `.venv\Scripts\python.exe -m compileall ai-engine` 通过。

### 2026-07-23 SunPilot 按钮入口守护补强

- 补强 `frontend/scripts/smoke-page-agent.mjs`，新增企业壳、Header、旧详情页和 `PageAssistantPanel` 兼容 wrapper 的 AI 按钮外溢检查。
- 新规则确保 `启动 AI 处理`、`重新 AI 处理`、`AI处理中`、`生成发单草稿`、`填入发单表单`、`填入回单草稿`、`进入复核区` 等 AI/自动化快捷动作只出现在 SunPilot `AgentPanel.vue`，不回流到主页面或旧助手。
- 新规则同时检查 `EnterpriseTicketShellView.vue` 只能通过 `<AgentPanel @start-ai-process="handleProcess">` 委托 AI 处理，不允许恢复 `@click="handleProcess"` 直连按钮。

### 本轮 SunPilot 入口验证记录

- `frontend` 下 `npm.cmd run smoke:page-agent` 通过。
- `frontend` 下 `npm.cmd run build` 通过。

### 2026-07-23 数据库治理与审计迁移

- 在用户确认 schema 变更后，补齐 `ai-engine/migrations/mysql/001_i1_schema.sql`：
  - 新增 `call_records`、`ticket_drafts`、`page_action_logs`、`agent_execution_log`。
  - 扩展 `trace_steps`：`input_json`、`output_json`、`error_message`、`duration_ms`。
- `models/database.py` 新增幂等 schema upgrade，已有数据库启动时会为 `trace_steps` 补缺失列。
- `models/repositories.py` 新增 `CallRecordRepository`、`TicketDraftRepository`、`PageActionLogRepository`、`AgentExecutionLogRepository`，并扩展 `TraceRepository.insert_trace_steps()` 写入 `output_json/error_message/duration_ms`。
- `Orchestrator._run_agent_step()` 已接入 `agent_execution_log`，成功/失败均记录 Agent input、output/error、状态和耗时；日志写入失败只 warning，不中断主流程。
- `main.py` 将通话样本导入 `call_records` 后再返回/发单；`generate-ticket-draft` 会写 `ticket_drafts`，包含草稿、PageTask、pageTaskHints、缺失字段、关键字段和置信度。
- `main.py` 新增 `POST /api/page-action-logs`、`GET /api/tickets/{ticket_id}/page-action-logs`、`GET /api/tickets/{ticket_id}/agent-executions`。
- 前端 `ticketApi`、Pinia store、`pageTaskExecutor.ts`、`AgentPanel.vue` 已接入 PageAgent 确定性动作审计上报；审计失败会提示但不阻断页面动作。
- `frontend/scripts/smoke-page-agent.mjs` 增加 PageActionLog 上报链路静态守护。
- `smoke_module_i1_database.py` 增加新表、trace 扩展列、call record、ticket draft、page action log、agent execution log 写读验证；`mysql_smoke_utils.py` reset 顺序已包含新表。
- `doc/issue/架构治理审查报告_20260723.md` 与 `doc/guides/架构与验收链路_20260723.md` 已从“数据库待确认”更新为“数据库治理已落地并可验收”。

### 本轮数据库治理验证记录

- `.venv\Scripts\python.exe -m compileall ai-engine` 通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_i1_database.py` 通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_m_call_intake.py` 通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_p_agent_contracts.py` 通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_p_architecture_guardrails.py` 通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_p_workflow_contracts.py` 通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_d.py` 通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_o_tool_calling.py` 通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_k_workflow_routing.py` 通过。
- `frontend` 下 `npm.cmd run smoke:page-agent` 通过。
- `frontend` 下 `npm.cmd run build` 通过。
- `git diff --check` 通过；仅输出 Windows LF/CRLF 提示。
- MySQL `VALUES()` upsert 未来弃用 warning 已清理：`CallRecordRepository` 与 `TicketDraftRepository` 改为重复键更新时绑定同一组参数，`smoke_module_i1_database.py` 复跑通过且不再输出该 warning。

### 2026-07-23 PLAN1 完成审计

- 多 Agent 职责收口已完成：`agent_cards.json` 只暴露 5 个业务 Agent，旧 shim/Dispatcher 不进注册表；`smoke_module_p_architecture_guardrails.py` 复跑通过。
- Agent 数据契约已完成：`TicketContext`、5 个 Agent input DTO、`IntakeResult`、`RiskDecision`、`ToolPlan` 与 AgentCard schema 校验已接入 Orchestrator；`smoke_module_p_agent_contracts.py` 复跑通过。
- Workflow 配置契约已完成：`WorkflowConfig`/`WorkflowScenario`/`WorkflowField` 统一访问器已接入高频读取点；`smoke_module_p_workflow_contracts.py` 复跑通过。
- PageTask / PageAgent 执行层已完成：`PageTaskEnvelope` 覆盖发单与回单；deterministic executor 优先，ReAct 只做失败兜底；危险点击目标门禁与 PageActionLog 上报由 `smoke:page-agent` 守护。
- 前端 AI 入口已收口：`AppHeader`、企业壳主页面、legacy 详情页和 `PageAssistantPanel` 不再提供 SunPilot 外的 AI 快捷按钮；`frontend` build 通过。
- 数据治理已完成：`call_records`、`ticket_drafts`、`page_action_logs`、`agent_execution_log` 与 `trace_steps` 扩展字段已落库并由 Repository/API 接入；`smoke_module_i1_database.py` 复跑通过。
- 业务链路 smoke 已复跑通过：`smoke_module_m_call_intake.py`、`smoke_module_d.py`、`smoke_module_o_tool_calling.py`、`smoke_module_k_workflow_routing.py`。
- 当前剩余只属于下一阶段增强：真实浏览器 DOM/Playwright 行为测试、AgentCard schema 与 Pydantic DTO 的集中生成/同步、workflow policy 进一步细分。

### 2026-07-23 前端分类筛选联动修复

- 修复企业壳最左侧业务菜单/分类按钮只改变筛选条件、不同步右侧当前工单详情的问题。
- `EnterpriseTicketShellView.vue` 新增筛选后选中同步：左侧业务菜单、首页状态桶和状态下拉变化后，会自动选择当前筛选结果第一张工单；筛选为空时清掉当前详情并回到首页队列。
- `ticket.ts` 新增 `clearSelectedTicket()`，用于清理 stale selected ticket 与 AI 上下文。
- `frontend/scripts/smoke-page-agent.mjs` 增加静态守护，防止分类按钮再次退化为只设置本地筛选状态。
- 验证：`npm.cmd run smoke:page-agent` 通过，`npm.cmd run build` 通过。

### 2026-07-23 SunPilot 问答/任务模式与模型菜单修复

- `AgentPanel.vue` 新增输入模式切换，按钮放在聊天框下方工具行，与 Key、模型选择、发送按钮并列。
- 默认进入“问答”模式：用户输入“你好”、询问当前工单、证据或下一步时，只在 SunPilot 消息流中回复，不触发 PageAgent `execute()` 页面动作。
- “任务”模式才允许执行 PageTask deterministic executor 或 ReAct 兜底；快捷功能按钮仍会主动切到任务模式并执行，保持原有操作效率。
- 模型选择最终改为原生 `<select>`，避免自绘菜单受 SunPilot sticky/overflow 布局影响导致溢出或点不到。
- `frontend/scripts/smoke-page-agent.mjs` 增加默认问答模式、模式开关、任务模式切换和原生模型选择守护。
- 验证：`npm.cmd run smoke:page-agent` 通过，`npm.cmd run build` 通过。
