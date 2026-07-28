# models — 数据契约层与持久化层目录

整个多 Agent 系统的数据契约与持久化基础。包含三类内容：

1. **Pydantic 数据模型**（业务实体、Agent 元数据、AI 结果、API schema、Agent 间 DTO、工具定义），统一以 `ApiModel` 为基类实现「内部 snake_case / 对外 camelCase 别名」双向契约。
2. **MySQL/TDSQL 持久化**：`database.py` 负责建库建表、种子数据、连接封装；`repositories.py` 提供各业务表的仓储层 CRUD。此层不使用 ORM 声明式模型，而用 SQLAlchemy Core（`text()` + 参数绑定）执行原生 SQL。
3. **确定性 FITS 场景识别**（`scenario_detection.py`），供通话录入与 Agent 分类复用。

## 文件说明

| 文件 | 主要功能 |
| --- | --- |
| `__init__.py` | 包导出聚合入口，re-export 各子模块核心类并用 `__all__` 收拢，供 `from models import ...`。 |
| `ticket.py` | 核心工单实体。定义 `RiskLevel`、`TicketStatus`（九态）枚举与主实体 `Ticket`（覆盖客户信息、场景分类、`ext_json`、SLA `deadline`、风险、状态、正文等）。 |
| `agent_card.py` | A2A-lite 的 Agent 自描述元数据。`AgentSkill` 描述单项能力，`AgentCard` 描述 Agent 的 ID、技能、输入/输出 schema、风险上限、超时、重试与依赖。 |
| `agent_trace.py` | Agent 执行轨迹与 SSE 事件模型：`TraceStatus` 枚举、`TraceStep`（单步轨迹）、`SSETraceEvent`（流式推送事件包）。 |
| `tool_schemas.py` | 工具注册表模型：`ToolParameter`、`ToolDefinition`（类别/参数/风险/是否需确认/Mock 配置）、`ToolResult`（执行结果与证据 ID）。 |
| `ai_result.py` | AI 处理结果模型体系，也是全模块 Pydantic 基类所在。`ApiModel` 确立 camelCase 契约；定义意图/字段/校验/补全、通知包 `NotificationBundle`、页面任务信封 `PageTaskEnvelope`，汇聚成顶层 `AiProcessResult`。 |
| `agent_contracts.py` | Agent 间传递的强类型 DTO 契约。`TicketContext` 是贯穿流水线的工单快照（含面向各下游 Agent 的投影方法），并定义各 Agent 输入契约、结果契约与 `coerce_*` 容错归一化函数。 |
| `workflow.py` | 工作流配置校验模型。`WorkflowField`/`WorkflowScenario`/`WorkflowConfig` 解析 `workflow_config.json`，`to_runtime_dict()` 转 snake_case 运行时字典，`scenario()` 按意图取场景并对 UNKNOWN 兜底。 |
| `scenario_detection.py` | 共享的确定性 FITS 场景识别（不依赖 LLM）。用正则从摘要/转写命中场景，`normalize_scene`/`normalize_intent_type` 归一化，`detect_fits_scenario` 产出结构化识别结果。 |
| `api_schemas.py` | FastAPI 请求/响应 schema 集合：工单 CRUD、通话记录转草稿、AI 处理、确认/结单、各类日志响应、评测指标 `EvaluationMetrics`。 |
| `database.py` | MySQL/TDSQL 的初始化、种子数据与底层连接助手。`init_db` 建库建表、幂等补列、灌演示数据；提供 `get_db()` 连接上下文、行归一化、`?` 占位符转命名参数等低层封装（不含业务查询）。**重要**：使用 SQLAlchemy 2.0 async context manager 模式，transaction 在 context 退出时自动 commit/rollback，不应手动调用 `commit()`。 |
| `repositories.py` | 仓储层，封装各业务表 CRUD 与审计写入：`TicketRepository`（含状态流转 + 操作日志）、`AiResultRepository`、`TraceRepository`、`ToolCallRepository`、`CallRecordRepository`、`TicketDraftRepository`、`PageActionLogRepository`、`AgentExecutionLogRepository`、`MockBusinessRepository`，末尾实例化为模块级单例。 |
