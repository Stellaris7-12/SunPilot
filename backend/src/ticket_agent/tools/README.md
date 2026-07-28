# tools — 工具子系统目录

模拟外部业务系统调用的工具子系统，四层结构：工具定义加载 → 中央注册表与校验 → Mock 执行器 → 对外 FastAPI 路由。核心分工是「**注册表负责名称解析 / 参数归一化 / 校验，执行器负责按类别派发并生成带证据 ID 的业务结果**」。工具元数据来自 `data/tools.json`。

## 文件说明

| 文件 | 主要功能 |
| --- | --- |
| `definitions.py` | 单一函数 `load_tool_definitions()`：从 `data/tools.json` 读取并解析为 `list[ToolDefinition]`，是所有工具元数据的唯一入口。 |
| `registry.py` | `ToolRegistry`（单例 `tool_registry`）。工具发现、OpenAI function schema 生成、名称纠偏（`closest_tool_name`）、参数归一化（`normalize_params`：拆包裹层、别名映射、snake→camel、类型强转）。**校验入口 `validate_tool_call`**：校验注册存在性、白名单归属、风险门槛并归一化参数，供 Orchestrator 调用。 |
| `mock_executor.py` | `MockExecutor`（单例 `mock_executor`）。模拟外部业务系统：`execute` 校验 → 派发 → 生成统一响应（含 `evidenceId`/`requiresHuman`/`failureReason` 等）；`enrich_params` 只读补全缺失参数（永不覆盖确定值）；含幂等重放、身份核验门禁、受控写操作审计等。 |
| `tool_router.py` | FastAPI `APIRouter`（前缀 `/api/tools`）。`GET /api/tools` 列出全部工具定义；`POST /api/tools/{tool_name}/execute` 供 Demo/调试直接执行工具，带 ticketId 时写 `tool_call_log` 审计。 |
