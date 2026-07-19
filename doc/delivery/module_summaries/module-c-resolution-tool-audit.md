# 模块 C：Resolution 执行能力与工具审计总结

## 1. 模块定位

模块 C 位于 TicketAgent 核心闭环的“业务执行层”，承接模块 A 稳定下来的 API、状态和持久化契约，也承接模块 B 中形成的 `ResolutionAgent` 业务口径。

它解决的核心问题是：系统不能只停留在“AI 给出处理建议”，而要能在受控边界内调用业务能力，返回明确的处理结果，并留下可以给业务人员、审计人员和后续模块继续使用的证据链。

没有模块 C 时，TicketAgent 只能展示分类、抽取和回单草稿，缺少三类关键能力：
- 无法说明系统到底调用了哪个业务能力。
- 无法展示工具入参、业务结果和证据编号。
- 无法在工具失败、权限不足、业务冲突或参数缺失时形成可追溯的升级路径。

## 2. 做了什么

模块 C 把 Resolution 环节从“选择工具”推进到“执行工具、记录证据、复核异常、前端展示”的完整链路。

最终沉淀的能力包括：
- 扩展 5 类 Mock Tool/API，覆盖优惠券补发、资料修改、交易查询、权益查询和申请进度查询。
- 统一工具执行结果结构，让每次执行都能表达处理动作、业务结果、证据编号、下一步建议、是否需要人工和失败原因。
- 在 Orchestrator 中补齐执行前参数校验，缺参时进入 `pending_info`，并生成客户可读的补充信息提示。
- 在工具执行后再次经过 `EscalationAgent` 复核，确保失败、权限不足、业务冲突和工具要求人工复核的场景不会被误判为自动成功。
- 补齐工具审计日志，Orchestrator 自动执行和直接工具调试接口在绑定 `ticketId` 时都能写入审计记录。
- 前端展示工具名称、关键入参、业务结果、证据编号、下一步建议和是否需人工，让处理过程可解释。
- 落地 Page Agent 第一阶段的页面助手，只操作当前工单详情页中的低风险动作。

## 3. 工作原理

模块 C 的输入来自前序 Agent 的结构化结果：
- `ClassifierAgent` 给出工单意图和 workflow。
- `IntakeAgent` 给出已抽取字段和缺失字段。
- `EscalationAgent` 判断当前是否允许自动执行。
- `ResolutionAgent` 输出要调用的工具名和工具参数。

执行链路采用“先校验，再执行，再复核，再审计”的机制：

1. Orchestrator 根据 workflow 和必填字段检查参数是否完整。
2. 如果缺少关键字段，流程暂停为 `pending_info`，不调用工具。
3. 如果允许自动执行，`ResolutionAgent` 选择 Mock Tool/API 并生成入参。
4. `MockExecutor` 调用工具定义，生成标准化 `ToolResult` 和业务证据编号。
5. Orchestrator 将工具请求、响应、证据编号、耗时和失败原因写入 `tool_call_log`。
6. 工具返回后再次交给 `EscalationAgent` 复核。
7. 如果工具失败、权限不足、业务冲突或 `requiresHuman=true`，流程升级为人工处理；否则进入待复核或后续通知链路。

这里的工具层仍是 Mock Tool/API，但接口边界按真实业务系统来组织：上层 Agent 只关心工具名、参数、业务结果和证据编号，不直接依赖 Mock 的内部实现。后续替换为真实 API、MCP Server 或外部系统接入时，可以尽量保持上层业务链路稳定。

## 4. 核心内容

核心 Agent：
- `ResolutionAgent`：选择业务工具并生成工具入参。
- `EscalationAgent`：在执行前和执行后判断是否需要补充信息、人工确认或升级人工。

核心工具：
- `coupon.reissue`：优惠券补发。
- `customer.update-address`：客户资料修改。
- `transaction.query`：交易流水查询。
- `benefit.query`：权益资格查询。
- `application.progress-query`：申请进度查询。

核心数据结构：
- `ToolResult`：包含 `success`、`tool_name`、`evidence_id`、`action`、`business_result`、`next_step`、`requires_human`、`failure_reason`、`data`、`message`、`duration_ms`。
- `tool_call_log`：记录工具名、请求 JSON、响应 JSON、证据编号、成功状态、耗时和失败原因。

核心接口：
- `GET /api/tickets/{ticket_id}/tool-calls`：查看指定工单的工具调用审计记录。
- `POST /api/tools/{tool_name}/execute`：直接调试工具；传入 `ticketId` 时写入审计日志。

核心前端展示：
- `AiResultCard`：展示工具审计摘要，包括工具、关键入参、业务结果和证据编号。
- `ToolRegistryPanel`：展示当前可用工具。
- `PageAssistantPanel`：当前工单页助手，支持填入回单、检查风险/缺失字段、定位工具面板和滚动审核区域。

核心验证：
- `ai-engine/evaluation/smoke_module_c.py`：覆盖 5 类工具注册、工具审计接口、缺参暂停、工具失败升级、业务冲突升级和直接工具接口审计。

## 5. 结果表现

模块 C 完成后，系统具备了可观察、可追溯的工具执行能力：
- 低风险且字段完整的场景可以自动调用工具，并生成业务证据编号。
- 字段缺失时不会强行执行工具，而是进入 `pending_info` 并提示客户补充信息。
- 工具失败、权限不足、业务冲突或工具要求人工复核时，会升级为人工处理。
- 每次工具执行都有审计记录，可以通过接口查询请求、响应、证据编号、耗时和失败原因。
- 前端能向业务人员解释“调用了什么工具、为什么调用、结果是什么、下一步怎么处理”。

已通过的验证命令：

```powershell
.venv\Scripts\python.exe -m compileall ai-engine
.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_a.py
.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_b.py
.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_c.py
cd frontend
npm run build
```

## 6. 代表性例子

### 例子：优惠券补发自动执行

输入：客户反馈参加活动后达标，但未收到 `DINING_100_20` 优惠券，并提供客户号、券类型和补发原因。
处理：`ResolutionAgent` 选择 `coupon.reissue`，`MockExecutor` 执行补券工具并生成 `CP` 前缀的证据编号。
结果：系统记录工具请求和响应，前端展示业务结果、证据编号和下一步建议，工单进入待人工复核或后续通知链路。

### 例子：权益查询缺少权益编码

输入：客户咨询是否有机场贵宾厅权益，但没有提供具体权益编码。
处理：执行前参数校验发现 `benefitCode` 缺失，Orchestrator 不调用 `benefit.query`。
结果：流程进入 `pending_info`，系统生成“请补充权益编码”等客户可读提示，避免错误调用工具。

### 例子：申请进度查询工具失败

输入：客户提供申请单号，系统准备查询信用卡申请进度。
处理：工具返回权限不足或执行失败，`ToolResult` 写入 `failure_reason`，执行后由 `EscalationAgent` 复核。
结果：工单进入 `escalated`，审计日志保留失败响应和原因，业务人员可以继续人工处理。

### 例子：交易查询返回业务冲突

输入：客户反馈某笔交易异常，系统调用 `transaction.query` 查询交易流水。
处理：工具返回成功但业务结果包含冲突、权限或需人工复核信号。
结果：系统不把技术成功等同于业务成功，而是升级人工，并在工具审计中保留证据和冲突原因。

## 7. 边界与后续

模块 C 的当前能力边界很明确：工具层仍是 Mock Tool/API，用于演示业务执行链路、审计证据和异常兜底，不等同于已经接入真实银行核心系统。

当前边界：
- Mock Tool 返回的是模拟业务结果，真实 API 接入后需要重新评估权限、幂等、失败码、超时、重试和审计字段。
- 资料修改、交易争议、高风险或敏感操作不能仅凭 LLM 自动完成，必须保留人工确认或人工升级。
- Page Agent 当前只做工单详情页内的低风险助手动作，不操作外部遗留系统。
- 工具审计记录服务于可追溯和演示说明，不替代生产级审计、风控和合规系统。

后续模块 D 已在模块 C 的工具结果和证据编号基础上生成标准回单、内部通知、复核摘要和结案建议；模块 F 则用评测样本验证工具选择、参数正确性和闭环状态匹配。
