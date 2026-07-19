# 模块 A：后端契约与工单状态稳定化总结

生成日期：2026-07-19

## 1. 模块定位

模块 A 位于 TicketAgent 核心闭环的后端基础层，负责把工单创建、AI 处理、人工确认、升级、失败和结案这些关键动作统一成稳定契约。

它服务于整条工单处理主链路：前端通过固定 API 发起工单和 AI 处理，后端 Orchestrator 负责推进状态，Agent 和 Mock Tool 的运行结果被结构化保存，SSE 负责把过程和终态实时推给前端。

没有模块 A 时，系统虽然可以跑 Demo，但会缺少稳定底座：前端字段可能漂移，SSE 终态不清楚，AI 处理结果无法可靠复查，人工确认和工具失败也难以用同一套状态解释。

## 2. 做了什么

模块 A 最终稳定了 TicketAgent 的后端契约和状态流转能力。

核心能力包括：

- 统一工单、AI 处理结果、工具定义、工具结果和处理响应的 API 字段命名，对外保持 camelCase。
- 补齐 `POST /api/tickets` 工单创建入口，使前端和后端能通过标准接口创建新工单。
- 扩展并稳定工单状态，覆盖处理中、待补充、待人工确认、待人工复核、升级、失败和结案。
- 统一 SSE 终态事件，让前端可以明确识别完成、暂停、升级和失败。
- 将 AI 处理结果、工具请求/响应、证据编号、处理耗时、失败原因等信息持久化。
- 增加模块 A 冒烟测试，覆盖自动处理、信息不足、人工确认、人工拒绝、工具失败、升级人工和旧状态兼容迁移。

## 3. 工作原理

模块 A 的输入主要来自前端或 API 调用：创建工单、发起 AI 处理、确认或拒绝敏感操作、查询 AI 结果、关闭工单。

工单创建后，后端保存基础工单信息。当前端发起 AI 处理时，Orchestrator 会按业务链路调用 Agent 和工具，并在过程中持续产出 Trace/SSE 事件。每次关键阶段完成后，系统会把结构化结果写入数据库，而不是只把结果留在内存或前端页面里。

状态流转采用确定性规则收口：

- 自动处理成功后进入 `pending_human_review`，等待人工终审或结案。
- 信息不足时进入 `pending_info`，并通过 `workflow_paused` 通知前端。
- 需要人工确认的动作进入 `pending_human_confirm`，确认通过后才继续执行。
- 高风险、异常或无法自动处理的场景进入 `escalated`。
- 工具或 Agent 链路失败时进入 `failed`，并保留失败原因。

SSE 终态与工单状态一一对应到四类事件：`workflow_complete`、`workflow_paused`、`workflow_escalated`、`workflow_failed`。前端不再需要猜测流程是否结束，而是根据终态事件和结构化结果更新页面。

数据库迁移采用兼容方式：对已有表补字段和扩展状态约束，不做破坏性重建，避免本地 Demo 数据和旧状态因为模块 A 改造而失效。

## 4. 核心内容

核心接口：

- `POST /api/tickets`：创建工单。
- `POST /api/tickets/{ticket_id}/ai-process`：发起 AI 处理。
- `POST /api/tickets/{ticket_id}/confirm-action`：人工确认或拒绝敏感操作。
- `GET /api/tickets/{ticket_id}/ai-result`：读取最新 AI 处理结果。
- `POST /api/tickets/{ticket_id}/close`：人工结案入口。

核心数据结构：

- `TicketResponse`：工单对外响应结构。
- `AiProcessResult`：AI 处理结果结构，包含分类、抽取字段、工具调用、证据、回单、状态和失败原因。
- `ToolDefinition`：工具定义结构。
- `ToolResult`：工具执行结果结构。
- `ProcessTicketResponse`：AI 处理接口统一响应结构。

核心状态：

- `open`
- `in_progress`
- `pending_info`
- `pending_human_confirm`
- `pending_human_review`
- `escalated`
- `failed`
- `closed`

核心事件：

- `workflow_complete`
- `workflow_paused`
- `workflow_escalated`
- `workflow_failed`

核心脚本：

- `ai-engine/evaluation/smoke_module_a.py`：模块 A 冒烟测试，验证状态流转、SSE 终态、持久化、人工确认和兼容迁移。

## 5. 结果表现

模块 A 完成后，TicketAgent 的后端主链路具备了可重复、可解释、可回归的运行基础。

可观察结果包括：

- 后端服务可启动，Swagger、工单列表和工具接口可访问。
- 工单从创建到 AI 处理结果持久化可以重复跑通。
- 前端可以稳定消费统一的 camelCase API 字段。
- 自动完成、信息不足、人工确认、升级人工和失败都有明确状态。
- SSE 不再只有过程事件，也能给出稳定终态。
- 工具调用结果和证据编号可以落库，为后续模块 C 的工具审计打底。
- 人工拒绝确认不再只修改工单状态，也会写入 trace 和 AI 结果。

已通过的验证命令和结果：

```powershell
.venv\Scripts\python.exe -m compileall ai-engine
.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_a.py
cd frontend
npm run build
```

接口级验证结果：

- `GET /api/tickets` 返回 200。
- `GET /api/tools` 返回 200。
- `GET /docs` 返回 200。
- `POST /api/tickets/dispute/ai-process` 可返回 `status=escalated` 和 `terminalEvent=workflow_escalated`。
- `GET /api/tickets/dispute/ai-result` 可读取最新持久化 AI 结果。

## 6. 代表性例子

### 例子：标准工单自动处理完成

输入：前端对一个信息完整、可自动处理的工单发起 AI 处理。
处理：后端调用 Agent 链路和 Mock Tool，生成处理结果、工具响应、证据编号和回单草稿。
结果：工单状态进入 `pending_human_review`，SSE 发出 `workflow_complete`，AI 结果被持久化。

### 例子：客户信息不足暂停

输入：客户描述中缺少券类型、申请编号或其他必填字段。
处理：后端识别缺失字段，不继续强行调用工具，并生成补充信息提示。
结果：工单状态进入 `pending_info`，SSE 发出 `workflow_paused`，前端展示待客户补充而不是弹出人工确认。

### 例子：敏感操作等待人工确认

输入：工单涉及资料变更等需要人工确认的操作。
处理：系统先进入确认等待状态，人工通过 `confirm-action` 接口批准后才继续执行工具。
结果：未确认前状态为 `pending_human_confirm`；确认通过后继续处理，拒绝则记录 trace 和 AI 结果。

### 例子：工具失败或高风险升级

输入：工具执行失败、返回业务异常，或工单本身属于无法自动闭环的高风险场景。
处理：Orchestrator 记录失败原因或升级原因，并停止自动执行链路。
结果：工单进入 `failed` 或 `escalated`，SSE 发出对应终态，前端可以展示清楚的失败/升级原因。

## 7. 边界与后续

模块 A 解决的是后端契约、状态机、SSE 终态和持久化稳定性，不负责把所有业务 Agent 能力一次性做完整。

当前边界：

- 工具仍是 Mock Tool/API，真实业务系统接入属于后续模块扩展。
- 模块 A 只保证状态和结果能稳定保存，不承诺分类、字段抽取或回单质量达到最终效果。
- 自动处理成功后默认进入人工复核或结案建议链路，不直接绕过人工完成真实业务闭环。
- 高风险、敏感操作和异常场景必须通过状态机进入人工确认、人工复核、升级或失败，不包装成全自动能力。

后续模块 B 在此基础上统一业务 Agent 命名和编排边界；模块 C 强化工具执行与审计；模块 D 把处理结果转成客户回单、内部通知和结案建议。
