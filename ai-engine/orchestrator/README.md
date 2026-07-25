# orchestrator — 工单流水线编排目录

多 Agent 工单处理流水线的编排核心。以配置为唯一事实来源，由 `Orchestrator.process_ticket()` 串联五个业务 Agent，通过 `PipelineContext` 在步骤间传递共享状态，用 `TicketStateMachine` 约束状态合法流转，用 `TraceCollector` 收集执行轨迹并落库，用 `SSEBridge` 把过程以 SSE 实时推给前端，用 `schema_validator` 对每个 Agent 的输入输出做契约校验。遵循「自动处理但**不自动关单**」的边界：终态最多停在待人工复核 / 升级。

## `process_ticket()` 编排顺序

加载工单 → `IN_PROGRESS` → 高风险短路 → Classifier 分类 → 意图归一化 → Intake 接单抽取 → 字段补全（`mock_executor.enrich_params`）→ Escalation 风险闸门 → 可能停机（`PENDING_INFO` / `PENDING_HUMAN_CONFIRM`）→ Resolution 出工具方案 → `tool_registry.validate_tool_call` 校验 → `mock_executor.execute` 执行并持久化 → 二次 Escalation 复核 → 成功走 `_finish_review`（`PENDING_HUMAN_REVIEW`），失败走 `_escalate`。`public_result()` 剥离 `_` 前缀内部字段。

## 文件说明

| 文件 | 主要功能 |
| --- | --- |
| `orchestrator.py` | 编排核心。实现上述 `process_ticket()` 全流程，每步经 `_run_agent_step` 统一推送 SSE、记录 trace、写执行日志、做 schema 校验，收尾统一走 `_complete_with_notification`（生成回单草稿 + 构建 `PageTaskEnvelope`）。 |
| `state_machine.py` | 工单状态机。定义 9 个状态枚举与合法流转表 `_TRANSITIONS`，`can_transition`/`transition` 校验流转，`requires_human` 标记需人工介入的状态。 |
| `sse_bridge.py` | SSE 流式推送。`format_sse` 组装事件帧，`SSEBridge` 提供 agent_start/thinking/complete/terminal/error 等 emit 方法，`stream()` 把编排调用包装为异步事件生成器。 |
| `workflow_config.py` | 配置加载与校验。`load_workflow_config()`（`@lru_cache`）读取 `workflow_config.json`，经 `WorkflowConfig` 校验并把 camelCase 别名转 snake_case 运行时键，失败回退内置 `DEFAULT_WORKFLOW_CONFIG`。 |
| `pipeline_context.py` | `PipelineContext` dataclass，单次编排运行的共享可变状态容器（ticket、trace、push 回调、各阶段产物），让收尾方法无需长参数列表即可取到中间态。 |
| `schema_validator.py` | 自实现的极简 JSON Schema 校验器（无运行时依赖）。`validate_agent_payload` 按 AgentCard 的 input/output schema 校验载荷，不符即抛 `SchemaValidationError`。 |
| `trace.py` | `TraceCollector` 收集流水线每步轨迹：`start()` 生成 run_id，`add_step`/`update_last` 增改步骤，`persist()` 写入 `trace_steps` 表。 |
