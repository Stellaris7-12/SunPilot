# TicketAgent 开发计划（2026-07-21）

## 目标

在 2026-07-23 前把当前系统收口为可演示闭环：

```text
通话 -> 通话记录 -> 发单Agent -> 生成标准工单 -> 回单Agent（多 Agent 处理+工具调用（Mock Tools 执行/审计+PageAgent辅助填单与回单 -> 人工复核结案
```

当前计划只保留剩余主线，历史完整过程见 `doc/planning/backup/`。

## 当前判断

- PageAgent 是答辩展示第一优先级，但它依赖一个稳定的业务底座：MySQL 演示库、Mock Tools 数据命中和 AI 结果/证据链必须先可靠。
- 旧 SQLite 运行口径会干扰演示，应推进到 MySQL-only：默认 MySQL、smoke 使用 `ticket_agent_test`、文档去掉 SQLite 路径。
- Mock Tools 大面积升级人工时，优先排查数据库连接、演示数据重置、业务域 seed 和 `workflow_config.json`，不要先假设 ResolutionAgent 坏了。
- 通话记录数据集已准备好，发单侧应做成“发单 Agent 生成草稿 + PageAgent 可见填单提交”的同步链路，不再只是后台接口生成 `ticketDraft`。
- 2026-07-22 复查后，决定采用 **fork 源码** 路线替代从零实现：直接复制 Ali page-agent 的 PageAgentCore + PageController + SimulatorMask，不加安全层（MVP 放弃 PolicyLayer 和审计），用 SSE bridge（pushObservation）让 PageAgent 接收后端 Agent 输出。PageAgent 专用 LLM 代理已切换为 `ALI_API_KEY` + `qwen3.7-plus`。详细方案见 `doc/issue/PageAgent_ReAct改造方案_7.22.md`。
- 完整业务背景位于 `doc/requirements/项目详细背景.md`

## 模块 K：MySQL-only 与 Mock Tools 收口（P0）

目标：让系统默认进入 MySQL 演示沙盘，并保证 Mock Tools 在干净 MySQL 数据下可稳定命中。

### K1：MySQL-only 运行口径

- [x] 将后端默认运行从旧 SQLite 口径改为 MySQL/TDSQL 方向。
- [x] 启动时如果缺少 MySQL `DATABASE_URL`，给出明确错误或引导，不再静默落到 SQLite。
- [x] 梳理 `ai-engine/models/database.py`，移除 SQLite 初始化/fallback，不保留历史兼容运行路径。
- [x] 梳理 `pyproject.toml`、`ai-engine/requirements.txt` 中 `aiosqlite` 依赖，并从当前依赖中删除。
- [x] 更新 `.env.example` 或配置说明，明确 `ticket_agent` 为演示库、`ticket_agent_test` 为测试库。

### K2：MySQL 测试库与 smoke

- [x] 新增或改造 MySQL smoke 配置，使 I1/I2/I3 不再默认创建 SQLite 临时库。
- [x] smoke 使用 `ticket_agent_test`，避免污染演示库 `ticket_agent`。
- [x] 为 MySQL smoke 加入最小重置流程：建表、清空测试数据、导入 tickets、seed Mock 业务域。
- [x] 运行并记录：`compileall`、I1 database smoke、I2 CRUD smoke、I3 Mock Tools smoke。

### K3：Mock Tools 命中修复

- [x] 检查 `reset_demo_data.py` 在 MySQL 下的删除顺序、外键约束和幂等性。
- [x] 检查 `_seed_mock_domain_data` 的客户、卡片、交易、权益、申请、权限 seed 是否覆盖 `tickets.json` 和 `call_transcripts.json` 中的关键字段。
- [x] 补齐交易流水 seed：从工单内容提取 `TXN...`，避免工具按 `transactionId` 查询时只命中生成的 `TXN{customer_id}`。
- [x] 补齐 merchant/amount/application/benefit 的抽取与回退策略，确保交易查询、权益查询、申请进度查询可稳定返回业务证据。
- [x] 增加 Mock Tools 诊断输出或 smoke 断言：客户命中、权益命中、申请命中、交易命中、补券幂等、人工确认门禁。

### K 验收

- [x] 默认启动不再连接旧 SQLite。
- [x] 干净 MySQL 演示库中，核心低风险样本能完成工具调用并生成证据编号。
- [x] 高风险/敏感样本进入人工确认或升级，不被自动结案。
- [x] 文档中的旧 SQLite 口径已清理；旧测评如需回归另写 MySQL-only 脚本。

## 模块 M：贯穿全流程的 GUI PageAgent（P0 第一优先级，已验收）

目标：fork Ali page-agent 源码，复制 PageAgentCore + PageController + SimulatorMask，用 SSE bridge（pushObservation）连接后端 Agent 输出，让 PageAgent 贯穿发单和回单全流程。MVP 放弃安全层，给予 PageAgent 最大自主性。

验收状态：2026-07-22 已完成运行态验收。PageAgent 专用 LLM proxy 使用系统级 `ALI_API_KEY` 调用 DashScope OpenAI-compatible 接口，模型强制为 `qwen3.7-plus`；浏览器在 `127.0.0.1:5173` + 后端 `127.0.0.1:8000` 下完成发单、AI 处理、回单草稿写入和证据定位。

核心定位：

```text
发单Agent / 回单侧多Agent = 业务大脑（管 what）
PageAgent = 页面执行员（管 how）+ 可视化演示前台
SSE Bridge = 两个大脑之间的通信通道（observation 机制）
Mock Tools / MySQL = 业务系统与证据底座
```

### M0：fork 源码（替代从零重写的 PageActionRunner）

- [x] 确定 fork 路线：直接复制上游 PageAgentCore、PageController、SimulatorMask、LLM 客户端、DOM 脱水引擎和 W3C 动作实现。不再从零重写。
- [x] 从 `C:\Users\heyunhui\OtherProjects\page-agent-main\packages` 复制核心源文件到 `frontend/src/page-agent/`，整理导入路径。
- [x] 不引入上游的 React Panel、Chrome Extension、MCP、website。
- [x] 保留原 `tools/index.ts` 全部内置工具（包括 execute_javascript 作为兜底逃生舱，默认禁用）。
- [x] 保留上游 MIT License 声明。

### M1：工厂函数与集成

- [x] PageAgent 不替代五个业务 Agent。
- [x] PageAgent 的任务来源分两类：用户在 Panel 输入自然语言指令；SSE bridge 通过 pushObservation 注入后端 Agent 输出。
- [x] 实现极简 `createTicketPageAgent()` 工厂函数（~30 行）：实例化 PageController（enableMask=true）+ PageAgentCore（baseURL 指向 `/api/llm/proxy`、language=zh-CN、maxSteps=15、stepDelay=0.8、model=`qwen3.7-plus`）。
- [x] 原 `page-agent/src/PageAgent.ts`（聚合 Core + Controller + React Panel）不引入，聚合逻辑在工厂函数中完成。

### M2：MVP 不实现 PolicyLayer

- [x] 明确 MVP 放弃：白名单校验、风险分级、确认门控、PageActionLog 持久化。
- [x] PageAgent 拥有最大自主性——LLM 输出的任何 action（click/input/scroll/execute_javascript）都直接执行，不经过额外拦截。
- [x] execute_javascript 默认关闭（experimentalScriptExecutionTool: false），demo 调试时如标准工具反复失败可临时开启作为兜底。
- [x] 安全层和审计能力作为答辩时主动说明的”已知待优化项”。

### M3：SSE Bridge（PageAgent 接收后端 Agent 输出的关键）

- [x] SSE bridge 是连接后台业务 Agent 和前端 PageAgent 的唯一通道。
- [x] 实现 `bridge.ts`：`watch(store.aiResult)` + `watch(store.traceSteps)` + `watch(store.isProcessing)` + `watch(store.ticketDraftResult)` → `pushObservation()`。
- [x] bridge 的核心工作：将 `AiProcessResult` 结构字段转为 LLM 友好的自然语言描述文本（而非 JSON），注入 PageAgent 的 observation 流。
- [x] 发单侧：watch `store.ticketDraftResult` → observation 含草稿各字段值，提示”请打开发单表单并填入以上字段”。
- [x] 回单侧：watch `store.aiResult` → observation 含场景、风险、回单草稿、证据编号、可结案状态，提示”请填入回单编辑器并定位证据”。
- [x] 后端 Agent 执行进度：watch `store.traceSteps` → observation 含每一步的 agent 名称和 summary，Panel 实时展示。

### M4：Vue Panel（替代 React Panel）

- [x] Panel 挂载在工单详情页右侧栏，嵌入页面布局。
- [x] 实现 `panel/AgentPanel.vue`：输入框 + 发送按钮 + 停止按钮 + 步骤流展示。
- [x] 监听 PageAgentCore 事件驱动更新：`activity: thinking` → 思考态、`activity: executing` → 动作描述、`activity: executed` → 结果+耗时、`activity: error` → 红色错误卡、`statuschange: completed/stopped` → 最终状态。
- [x] CSS 复用上游 Teal(#0f766e)+Amber(#f59e0b) 色系，和 SimulatorMask 保持视觉一致。
- [x] 和 SimulatorMask 的同步感：Panel 展示执行中/已执行步骤，PageController/SimulatorMask 负责鼠标移动和点击动画。

### M5：后端 LLM 代理

- [x] 新增 `POST /api/llm/proxy/chat/completions` 与兼容 `POST /api/llm/proxy`：前端 PageAgentCore 的 OpenAIClient 通过此端点调 LLM，不暴露 API Key。PageAgent proxy 使用 `ALI_API_KEY` + `qwen3.7-plus`。
- [x] 运行态验收：`POST /api/llm/proxy/chat/completions` 由后端强制使用 `qwen3.7-plus`，请求 `tool_choice=required`、`enable_thinking=false` 返回 200，且包含 `done` tool call。

### M6：发单与回单 Demo 链路

- [x] 已实现：发单 Agent（`POST /api/call-records/generate-ticket-draft`）、企业壳通话发单工作区、发单表单语义标记。
- [x] Demo 链路 1（低风险全自动）已接入：坐席说”根据这通电话帮我发单” → PageAgent/bridge 接收发单草稿 → 表单字段可填可提交 → 工单创建 → 跳转详情页 → 坐席点”AI处理” → Panel 实时展示多Agent进度 → 处理完成 → bridge 注入 observation → PageAgent 可继续填回单与定位证据。
- [x] Demo 链路 2（高风险）已接入：多Agent 识别高风险/人工确认后，bridge 注入风险原因 observation，PageAgent 任务停在人工确认/风险定位口径，不直接结案。
- [x] 运行态验收：点击“生成发单草稿”后，bridge observation 自动注入 Panel；PageAgent 真实调用 Qwen ReAct 循环，Panel 记录多步 `input_text`，填入标题、客户号、客户姓名、手机号、卡尾号等字段。
- [x] 运行态验收：发单侧提交成功，工单列表新增 `T20260722445615 / C20001 / 张明 / 餐饮券 / 待处理`，并进入详情区。
- [x] 运行态验收：回单侧 PageAgent 在详情页点击 `启动 AI 处理`，bridge 实时注入 Classifier、Intake、Escalation、Resolution、Notification 等后端 Agent 进度。
- [x] 运行态验收：后端多 Agent 完成后，bridge 注入低风险可结案 observation 与回单草稿；PageAgent 点击“填入 SunPilot 建议”、定位证据编号，并写入 `page-agent-reply-draft`。最终回单内容包含 `处理依据/证据编号：BEN20260722C8C4B9EE`。

### M 验收

- [x] PageAgent 能以可见鼠标完成发单：打开发单表单、填表、提交。
- [x] PageAgent 能以可见鼠标完成回单：填入回单、定位证据、滚动到复核区。
- [x] 右侧 Panel 可输入任务并展示实时步骤流。
- [x] 后端 Agent 结果通过 bridge 自动注入 PageAgent，无需人工复制粘贴。
- [x] 答辩时能讲清：多 Agent 是业务大脑，PageAgent 是页面执行员，SSE bridge 是两者之间的语言通道。

验收证据：

- `frontend` 下 `npm.cmd run build` 通过。
- `.venv\Scripts\python.exe -m compileall ai-engine` 通过。
- Qwen proxy 直连探针通过：`qwen3.7-plus` + `tool_choice=required` + `enable_thinking=false` 返回 tool call。
- 浏览器动态验收通过：PageAgent 可见发单、提交新增工单、启动多 Agent、填入客户回单、定位证据编号。

保留边界：

- MVP 仍不实现 PolicyLayer、风险分级拦截和 PageActionLog 持久化。
- 自动流程不直接结案；仍停在人工复核/结案节点。

## 模块 L：已并入模块 M3（不再单独排期）

模块 L 原“通话记录发单侧 MVP”已整合进模块 M3：发单 Agent 与可见发单 PageAgent。后续不再单独维护 L1/L2/L3/L4，避免与 M3 重复。

保留模块 L 作为索引说明：

- K 仍是已完成的数据与 Mock Tools 底座，不与 L 合并。
- L 的接口契约、发单页面、PageAgent 可见填单、13 个业务系统演示表达和验收标准均落在 M3。
- 后续实施时直接按 M0/M2/M5 建 PageAgent 执行壳，再做 M3 发单链路，最后做 M4 回单链路。

## 模块 O：Tool Calling 与 PageAgent 内置 LLM 收口（P0 新增）

目标：优先处理 `doc/issue/架构与数据流问题分析报告_20260722.md` 的 3.1、3.2 和 4，修复“没有合适 Tools 可供调用”的根因。PageAgent 规划口径已被模块 M fork ReAct 方案替代，不再维护“后端 Planner + Policy Guard”路线。

### O1：LLM 原生 Tool Calling 主链路

- [x] 在 `ai-engine/agents/base.py` 扩展 `call_llm()`，保留现有 JSON 模式，并新增 `tools`、`tool_choice` 支持。
- [x] 当传入 tools 时，使用 OpenAI/DeepSeek 兼容的 `chat.completions` tool calling；返回值统一解析为 `tool_calls[]`，文本 JSON 仅作为兼容 fallback。
- [x] `ResolutionAgent` 不再把 22 个工具 Markdown 全量塞入 prompt；改为把当前 intent 相关工具转换为 tools schema。
- [x] `ResolutionAgent` 输入补充 `ticket_content` 和结构化 `ticket`，避免只依赖 Intake 抽取字段。
- [x] `Orchestrator` 调用 ResolutionAgent 时传入完整 ticket context、结构化 ticket、当前 intent 相关工具名列表和 workflow 配置。
- [x] 保留现有人工门禁：中高风险、工具要求人工、字段缺失、工具失败均不能因为 tool calling 改造而自动结案。

### O2：工具注册表与数据格式统一

- [x] 在 `ToolRegistry` 增加 OpenAI tools schema 生成能力，解决 `coupon.reissue`、`customer.update-address` 这类工具名与 function name 的映射问题。
- [x] 增加 `list_for_intent(intent_type, workflow_config)`，只向 LLM 暴露当前场景相关候选工具。
- [x] 增加工具参数归一化：工具边界继续使用 camelCase canonical 参数，同时兼容 snake_case、类型字符串和常见 LLM 包装文本。
- [x] 将 `definitions.py` 中 17 个 I3 硬编码工具迁移到 `ai-engine/data/tools.json`，统一维护 22 个工具定义。
- [x] 为所有 I3 工具参数补齐中文业务描述和 example，禁止 `description` 仅重复参数名。
- [x] `LLM_MAX_TOKENS` 默认从 2000 提升到 4096；不修改 `.env`。

### O3：ResolutionAgent 兜底、校验和 Mock Tools 根因修复

- [x] `_INTENT_TOOL_MAP` 从单工具扩展为场景候选工具列表，覆盖 I3 工具。
- [x] LLM 未返回 tool call、返回未知工具名或工具名轻微漂移时，只允许在当前候选工具集合内校正；无法校正则走 workflow `recommended_tool` 或进入 `pending_info`/人工。
- [x] MockExecutor 执行前统一做工具存在性、必填参数、参数类型和风险等级校验；未知工具不能进入 `mock_executor.execute()`。
- [x] 修复发单 Agent 场景枚举不一致：资料变更输出 `CUSTOMER_ADDRESS_UPDATE`，交易争议/交易核查输出 `TRANSACTION_DISPUTE`，与 `workflow_config.json` 对齐。
- [x] 保留 `transaction.query` 的只读取证口径：交易类可先查流水生成证据，但后续仍走人工复核边界。
- [x] 更新 `agent_cards.json` 中 ResolutionAgent 的 input schema：`available_tool_names` 为主，`available_tools` 仅保留兼容旧评测。

### O4：已废弃（被 M0 fork 方案替代）

原来的 “PageAgent 内置 LLM Planner + 后端规划接口” 方案已废弃。fork Ali page-agent 源码后，LLM 决策由 PageAgentCore 的 ReAct 循环原生提供，不需要额外的后端 Planner。PageAgent 通过 `POST /api/llm/proxy` 直接调用 LLM（和 OpenAIClient 已有的机制一致）。

### O 验收

- [x] `ResolutionAgent` 在 mock `tool_calls` 响应下能输出真实工具名和 canonical 参数。
- [x] 工具名幻觉、无 tool call、snake_case 参数、缺必填参数均有确定性兜底或人工/待补充分支。
- [x] Registry 加载 22 个工具，且 I3 参数描述与 example 可读。
- [x] 发单场景检测返回的 ticket type 能被回单侧 workflow 正确路由。
- [x] PageAgent 输入“根据这通电话帮我发单”“处理当前工单并自动回单”“定位证据”时走 PageAgentCore ReAct 循环，不再输出白名单 `PageTaskPlan`。
- [x] MVP 不启用 Policy Guard；非法动作/高风险直接结案拦截作为后续安全层和审计优化项。
- [x] 验证命令：`.venv\Scripts\python.exe -m compileall ai-engine`、`smoke_module_i3_mock_tools.py`、`smoke_module_k_workflow_routing.py`、新增 tool-calling smoke、前端 `npm.cmd run build`。

## 模块 N：演示与答辩材料（P1）

目标：在开发收口后准备一套能讲清“方案选择、当前效果、边界和后续优化”的 Demo。

- [ ] 准备三条演示链路：低风险优惠券补发、中风险资料/分期人工确认、高风险交易争议或征信异议升级。
- [ ] 准备 PageAgent 对比口径：通用 Page Agent 强在网页泛化，TicketAgent PageAgent 强在信用卡业务上下文、权限门禁、证据审计和人工接管。
- [ ] 准备 Mock Tools 解释：代表外部业务系统能力适配层，不是真实银行系统直连。
- [ ] 准备 MySQL 解释：本地准生产演示沙盘，演示库和测试库分离。
- [ ] 准备待优化项：真实 ASR、外部遗留系统自动化、生产权限体系、更多业务数据、持久化 PageActionLog、监控告警。

## 推荐执行顺序

1. 已完成：K1/K2/K3，确保 MySQL + Mock Tools 可演示。
2. 已完成：O1/O2/O3，ResolutionAgent 原生 Tool Calling、工具 schema、参数归一化和 Mock Tools 根因修复。
3. 立即执行（7.22-7.23）：**M0**（复制源码 + 整理导入）→ **M5**（LLM proxy）→ **M1**（工厂函数）→ **M3**（SSE bridge）→ **M4**（Vue Panel）→ **M6**（发单回单 Demo 链路调试）。
4. M 完成后：跑后端 smoke、前端 build，再进入 N，整理 Demo 脚本和 PPT 要点。

## 非目标

- 不做真实银行生产系统直连。
- 不做真实 ASR 语音识别主线；可作为后续路线或演示素材。
- MVP 不做 PolicyLayer（安全白名单、风险分级、确认门控、PageActionLog 持久化）；答辩时作为"已知待优化项"主动说明。
- 不把 PageAgent 放入后端五 Agent 编排中。
- MVP 允许浏览器通过 `/api/llm/proxy` 间接调用 LLM（PageAgentCore 的 OpenAIClient 机制需要）。
