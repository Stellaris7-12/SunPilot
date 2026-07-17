# 进度日志

## 会话：2026-07-18（模块C完成：Resolution 执行能力与工具审计）

### 背景

用户要求继续完成模块 C 代码，并使用子 Agent 进行代码审查、测试、debug 和优化，直到满足 `task_plan.md` 中模块 C 的要求清单。

### 执行内容

- 扩展 Mock Tool 到 5 类：补券、资料修改、交易查询、权益查询、进度查询。
- 扩展 `workflow_config`、Classifier、Intake、Escalation、Resolution 和 Agent Card，使 5 类场景都能被识别、抽取、校验和选择工具。
- 统一 `ToolResult` 返回结构：`action`、`business_result`、`evidence_id`、`next_step`、`requires_human`、`failure_reason`。
- 重构 `MockExecutor`，生成业务证据编号，并对权限、冲突、失败等业务异常标记人工复核。
- 重构 Orchestrator 工具执行链：执行前缺参校验，缺参时生成补充提示并暂停；执行后再次调用 Escalation Agent 做失败、冲突、权限和人工复核判断。
- 补齐工具审计：Orchestrator 路径写 `tool_call_log`，直接工具调试接口在传入 `ticketId` 时也写审计。
- 新增 `GET /api/tickets/{ticket_id}/tool-calls` 只读审计接口。
- 前端新增业务执行审计展示：工具名、关键入参、业务结果、证据编号、下一步建议、是否需人工、失败原因。
- 前端新增当前工单页“页面助手”，仅支持本页低风险动作：填入回单、检查风险、定位工具、滚动审核区。
- 修复详情页刷新/路由切换后不恢复 AI 结果、可能操作错工单，以及 `AppSidebar` 未显式导入的问题。
- 新增 `ai-engine/evaluation/smoke_module_c.py`，覆盖 5 类工具、工具审计接口、缺参暂停、失败升级、业务冲突升级和直接工具接口审计。

### 子 Agent 审查与修复

- 后端子 Agent 发现直接工具接口绕过审计、缺参缺少客户可读补充提示、成功但业务冲突时可能跳过升级；已全部修复并加回归断言。
- 前端子 Agent 发现刷新后不恢复 AI 结果、路由切换与 store 状态可能脱节、`AppSidebar` 未导入；已全部修复。
- 子 Agent 未发现 P0 问题。

### 验证结果

- `.venv\Scripts\python.exe -m compileall ai-engine`：通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_a.py`：通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_b.py`：通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_c.py`：通过。
- `cd frontend && npm.cmd run build`：通过。

### 当前阶段

- **状态：** completed
- **阶段名称：** 模块C：Resolution 执行能力与工具审计
- **下一步：** 进入模块D：Notification 与回单闭环；重点把工具结果、证据编号、人工复核原因转成更标准的客户回单、内部通知和结案建议。

## 会话：2026-07-17（模块B完成：业务 Agent 受控重构）

### 背景

用户要求按照计划完成模块 B 代码，并使用子 Agent 进行代码审查、测试、debug 和优化，直到满足 `task_plan.md` 中模块 B 的要求清单。

### 执行内容

- 新增业务 Agent 文件：`classifier_agent.py`、`intake_agent.py`、`escalation_agent.py`、`resolution_agent.py`、`notification_agent.py`。
- 将旧 `intent_agent.py`、`extract_agent.py`、`verify_agent.py`、`tool_agent.py`、`reply_agent.py` 改为短期兼容 shim。
- 更新 Orchestrator：使用新业务 Agent 属性和 `agentId`，Trace/SSE 改为 `classifier_agent`、`intake_agent`、`escalation_agent`、`resolution_agent`、`notification_agent`。
- 新增 `ai-engine/data/workflow_config.json` 和 `orchestrator/workflow_config.py`，描述场景、必填字段、推荐工具、人工确认策略和通知模板。
- 更新 `agent_cards.json` 为新业务 Agent Card 和依赖关系。
- 更新前端流程条、Trace 标题、AI 结果卡片、人工确认提示等业务化文案，并让 SSE `agent_complete.status` 可驱动失败状态。
- 更新 `doc/guides/启动与使用指南.md` 的演示轨迹、目录结构、架构流程和新增场景说明。
- 新增 `ai-engine/evaluation/smoke_module_b.py`，覆盖新 Agent ID、`pausedAt=escalation_agent`、高风险升级、旧 shim、workflow_config fallback、Classifier fallback 和 Agent 异常 Trace 失败状态。
- 通过子 Agent 做后端只读审查，并修复：
  - `workflow_config` 加载失败缺少内置 fallback。
  - Classifier 缺失或异常 `workflow_name/type` 时回填不稳。
  - Agent 抛异常时 Trace/SSE 可能保留 RUNNING 状态。
- API 级验证发现 `/api/agent-cards` 仍返回 snake_case 字段，已将 `AgentCard` 接入统一 camelCase API 模型。

### 验证结果

- `.venv\Scripts\python.exe -m compileall ai-engine`：通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_a.py`：通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_b.py`：通过。
- `cd frontend && npm.cmd run build`：通过。
- 临时数据库 + FastAPI TestClient 验证 `GET /api/tickets`、`GET /api/agent-cards`、`GET /api/tools` 均返回 200，且 Agent Card 对外字段为 `agentId`、`inputSchema`。
- Agent Registry 当前加载顺序为 `classifier_agent -> intake_agent -> escalation_agent -> resolution_agent -> notification_agent`。
- `workflow_config` 可加载三类核心场景和 `UNKNOWN` 兜底，旧 Agent shim 继承关系验证通过。

### 当前阶段

- **状态：** completed
- **阶段名称：** 模块B：Agent 编排与业务化封装
- **下一步：** 进入模块C：Resolution 执行能力与工具审计；重点梳理 Mock Tool、统一工具返回结构、强化工具参数缺失和失败升级链路。

## 会话：2026-07-17（模块B实施策略调整：受控重构新业务 Agent）

### 背景

用户质疑单独增加 Agent 映射层是否冗余，并提出相比维护 `IntentAgent -> ClassifierAgent` 这类翻译关系，是否更适合直接把旧 Agent 重构为新业务 Agent。

### 执行内容

- 读取 `planning-with-files-zh` 技能说明。
- 重新读取 `doc/planning/task_plan.md`、`doc/planning/findings.md`、`doc/planning/progress.md`。
- 更新 `doc/planning/task_plan.md`：将模块 B 从“映射/adapter 方案”调整为“代码层受控重构为新业务 Agent”。
- 更新 `doc/planning/findings.md`：记录映射层在当前 Demo 阶段偏冗余，模块 B 改为受控重构。
- 明确旧 Agent 文件短期保留为兼容 shim，模块 B/C 稳定后再评估删除。
- 明确模块 A 不重新开发；模块 B 完成后只做 API、SSE 终态、状态机、持久化和工具审计契约的回归验证。

### 当前共识

- 模块 B 采用受控重构，不长期维护单独业务映射层。
- 新 Agent 代码命名目标：`ExtractAgent -> IntakeAgent`、`IntentAgent -> ClassifierAgent`、`ToolCallingAgent -> ResolutionAgent`、`ReplyAgent -> NotificationAgent`、`VerifyAgent -> EscalationAgent`。
- 旧文件短期作为兼容 shim，避免测试或旧导入立刻断裂。
- 模块 A 不重做；模块 B 必须保持模块 A 契约不变，并通过模块 A smoke 回归。

### 当前阶段

- **状态：** in_progress
- **阶段名称：** 模块B：Agent 编排与业务化封装
- **当前任务：** 按受控重构方案统一代码层、Trace、前端和文档中的业务 Agent 命名。
- **下一步：** 开始模块 B 代码改造：新增业务 Agent 文件、旧文件改兼容 shim、调整 Orchestrator/Agent Card/前端流程条，并补充模块 B smoke 测试。

## 会话：2026-07-17（Page Agent 进阶路线补充）

### 背景

用户希望在计划中补充 Page Agent 的推荐引入方式：不要直接做外部系统自动化，而是分阶段从低风险页面助手开始。

### 执行内容

- 更新 `doc/planning/task_plan.md` 的进阶模块，加入 Page Agent 三阶段路线。
- 更新 `doc/planning/findings.md`，补充 Page Agent 推荐引入路线和安全边界。
- 保持 `doc/planning/任务顺序.md` 不变。

### 当前共识

- 第一阶段：在 `frontend/src/views/TicketDetailView.vue` 增加“页面助手”入口，只操作当前工单详情页。
- 第二阶段：动态工单表单完善后，将 Intake Agent/ExtractAgent 抽取结果转成发单/回单页面填充动作。
- 第三阶段：只有在行内系统没有 API 时，才考虑 Page Agent Ext / MCP 操作外部浏览器页面。
- 外部遗留系统自动化属于高风险能力，必须有白名单、脱敏、审计和人工确认。
## 会话：2026-07-17（planning 文件按新 Agent 方案重构）

### 背景

用户对原 planning 不满意，主要原因：

- 低/中/高风险分级不应作为核心模块强调，它只是业务策略细节。
- 原 Agent 划分偏技术实现，不如 Intake、Classifier、Dispatcher、Resolution、Notification、Escalation 这套业务命名适合工单场景和答辩表达。
- Resolution Agent 中的接口调用、MCP、PageAgent 体现不够明确。
- 只考虑 3 类业务场景不足，需要更多工单场景支撑数据集和测评。
- 本轮只重构 `doc/planning/任务顺序.md` 以外的 planning 文件。

### 执行内容

- 读取 `planning-with-files-zh` 技能说明。
- 读取当前 `doc/planning/task_plan.md`、`doc/planning/findings.md`、`doc/planning/progress.md`、`doc/planning/任务顺序.md`。
- 读取 `doc/design/` 下现有设计文档，确认旧技术型 Agent 口径仍有残留。
- 保留 `doc/planning/任务顺序.md` 不变。
- 重写 `doc/planning/task_plan.md`：改为核心闭环开发路线，采用新业务 Agent 分类。
- 重写 `doc/planning/findings.md`：记录新旧 Agent 方案对比、是否重构、编排取舍、场景扩展和产品形态判断。
- 重写 `doc/planning/progress.md`：记录本次 planning 重构背景、执行内容、当前共识和下一步。

### 当前共识

- 新业务 Agent 主口径：Intake、Classifier、Resolution、Notification、Escalation。
- Dispatcher Agent 难度较高，先作为进阶模块，不进入当前核心闭环。
- 当前代码不长期维护映射层，模块 B 采用受控重构，旧 Agent 文件短期保留为兼容 shim。
- Resolution Agent 必须明确包含 API/Mock Tool 调用和审计证据；MCP 与 PageAgent 是进阶扩展。
- 风险分级不再作为核心模块，只作为分类、执行和升级策略中的细节。
- 工单场景需要扩展到 10 类以上，用于数据集和测评，而不是只围绕 3 个固定 Demo。
- 当前仍优先手写 Orchestrator + 轻量 `workflow_config`，暂不迁移 LangGraph。

### 当前阶段

- **状态：** in_progress
- **阶段名称：** 新 Agent 方案规划收口
- **当前任务：** 将规划文件对齐到业务型 Agent 编排，为后续代码开发提供稳定导航。
- **下一步：** 开始代码开发前，先检查 AGENTS.md、design 文档和前端 Trace 文案是否也需要同步到新 Agent 口径。

## 历史基线摘要

### 2026-07-16 初版系统建设

- 完成 FastAPI 后端、SQLite 数据库、5 个技术型 Agent、Tool Registry、MockExecutor、手写 Orchestrator、SSE Trace、Vue 前端工作台。
- 完成启动指南、规划文件、AGENTS.md、.gitignore。
- 已重新初始化 Git，并完成初始提交：`64535e6 Initial TicketAgent project snapshot`。

### 2026-07-17 文档目录整理

- `doc/` 已整理为 requirements、design、guides、demo、planning 等子目录。
- 新增 `doc/README.md` 作为文档索引。
- Demo 讲解稿已转向面向产品经理、客户和领导的业务表达。
- `doc/guides/vibe-coding指南.md` 已创建，用于通用 AI coding 工作流。

## 已验证能力

| 能力 | 状态 |
|------|------|
| 后端基础服务 | 已完成初版 |
| SQLite 数据库 | 已完成初版 |
| Agent Registry 加载旧 5-Agent | 已完成初版 |
| Tool Registry 和 MockExecutor | 已完成初版 |
| 手写 Orchestrator | 已完成初版 |
| SSE 实时 Trace | 已完成初版，仍需契约稳定 |
| Vue 前端工作台 | 已完成初版 |
| Git 初始提交 | 已完成 |
| 新业务 Agent 规划 | 本轮重构中 |

## 后续进度更新规则

每完成一个模块后更新本文件：

- 写明日期、阶段、完成内容。
- 记录修改的文件。
- 记录运行过的测试，或无法运行的原因。
- 记录遇到的问题和解决方式。
- 如果阶段状态变化，同步更新 `task_plan.md`。
- 如果 Agent 命名、流程顺序或验收标准变化，必须同步更新 `findings.md`。

## 五问重启检查

| 问题 | 当前答案 |
|------|----------|
| 我在哪里？ | 模块 A 和模块 B 已完成，系统已统一到业务 Agent 命名和轻量 workflow_config |
| 我要去哪里？ | 进入模块 C，强化 Resolution 执行能力、工具审计和失败兜底 |
| 目标是什么？ | 做出可演示、可测评、可解释的信用卡工单智能处理系统 |
| 我学到了什么？ | 受控重构比长期映射层更适合当前项目；workflow_config 需要内置 fallback，Agent 失败 Trace 也要明确落为 FAILED |
| 我做了什么？ | 完成模块 B 代码改造、前端和文档同步、模块 A/B smoke 回归、前端构建和子 Agent 审查修复 |

## 会话：2026-07-17（模块A完成：后端契约与状态稳定化）

### 背景

用户要求根据 planning 继续开发，优先完成模块A，并通过子 Agent 做代码审查和优化，确保系统能跑通。

### 执行内容

- 稳定 API 对外契约：`TicketResponse`、`AiProcessResult`、`ToolDefinition`、`ToolResult`、`ProcessTicketResponse` 对外统一 camelCase。
- 新增 `POST /api/tickets`，补齐工单创建入口。
- 扩展工单状态：新增 `pending_info`、`failed`，并统一 `workflow_complete`、`workflow_paused`、`workflow_escalated`、`workflow_failed` 四类 SSE 终态。
- 补齐 AI 结果结构化持久化字段，记录 workflow、intent、fields、tool request/response、evidence、reply、status、duration、failure reason。
- 工具调用通过 Orchestrator 写入 `tool_call_log`，记录成功/失败、证据编号、耗时和失败原因。
- 人工拒绝确认会写入 trace 和 `ai_results`，不再只改工单状态。
- 中风险人工确认接口增加状态前置校验，避免重复确认导致重复执行工具。
- 前端 Pinia store 同步消费新 SSE 终态；只有 `pauseType=human_confirm` 时才弹人工确认框，信息不足暂停不再误弹确认。
- 新增 `ai-engine/evaluation/smoke_module_a.py`，用临时 SQLite 和伪 Agent 覆盖自动处理、信息不足、人工确认、人工拒绝、工具失败、升级人工和旧状态 CHECK 迁移。
- 使用两个子 Agent 做只读代码审查，修复了 trace alias、SSE 先发终态后落库、确认接口重复执行、人工拒绝未持久化等问题。

### 验证结果

- `.venv\Scripts\python.exe -m compileall ai-engine`：通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_a.py`：通过。
- `cd frontend && npm.cmd run build`：通过。
- 临时数据库启动后端，`GET /api/tickets`、`GET /api/tools`、`GET /docs`：均返回 200。
- 临时数据库调用 `POST /api/tickets/dispute/ai-process`：返回 `status=escalated`、`terminalEvent=workflow_escalated`、trace 使用 `agentId`。
- `GET /api/tickets/dispute/ai-result`：可读取最新持久化 AI 结果。
- 前端 dev server 已验证首页返回 200。

### 当前阶段

- **状态：** completed
- **阶段名称：** 模块A：后端契约与工单状态稳定化
- **下一步：** 进入模块B：Agent 编排与业务化封装。
