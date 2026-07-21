# TicketAgent 进度日志

## 会话：2026-07-21（轻量 active planning 重建）

用户要求参照 `doc/guides/项目交接说明_20260721.md` 和 2026-07-21 新需求，规划后续开发，重点包括 PageAgent 开发、MockTools 问题修复、SQLite 全量迁移至 MySQL。

已完成：

- 使用 `planning-with-files-zh` 工作流读取规划规则。
- 读取交接说明，确认旧 active planning 三件套已主动移除，历史备份位于 `doc/planning/backup/`。
- 读取 PageAgent 定位文档和导师 2026-07-21 修改意见。
- 扫描当前 MySQL/SQLite、MockExecutor、PageAssistantPanel、EnterpriseTicketShellView、smoke 测试相关代码。
- 新建轻量 active planning 三件套：
  - `doc/planning/task_plan.md`
  - `doc/planning/findings.md`
  - `doc/planning/progress.md`

关键结论：

- PageAgent 是演示第一优先级，但 MySQL-only 与 MockTools 稳定性是前置底座。
- 计划拆为模块 K/M/L/N：K MySQL-only 与 MockTools 收口，M PageAgent/SunPilot 业务化执行层，L 通话记录发单侧 MVP，N 答辩演示材料。
- PageAgent 不进入后端五 Agent 编排，不做通用网页机器人；当前阶段做前端受控动作层、动态执行展示和动作审计。

待继续：

- 从模块 K 开始实施 MySQL-only 与 MockTools 修复。
- 随后进入模块 M，实现 `PageContext`、`PageAction`、`PageActionRunner`、`PageActionLog` 和右侧动态 PageAgent 展示。

## 会话：2026-07-21（模块 K MySQL-only 执行）

用户确认：不再考虑旧测评脚本；如需再次测试前置模块，后续另写 MySQL-only 测评脚本；不保留历史兼容路径。

已完成：

- 将后端配置默认切到 MySQL/TDSQL；本地 root 密码来自 `MYSQL_ROOT_PASSWORD`，缺少 MySQL URL/密码时给出明确错误。
- 从 `ai-engine/models/database.py` 移除 SQLite 初始化、迁移、连接和 `aiosqlite` 运行路径；启动会按 URL 自动创建缺失的 MySQL 数据库。
- 从 `pyproject.toml`、`ai-engine/requirements.txt`、`uv.lock` 移除 `aiosqlite`，并补齐 MySQL 依赖口径。
- 新增 `ai-engine/evaluation/mysql_smoke_utils.py`，I1/I2/I3 smoke 默认使用 `ticket_agent_test`，自动建库、清表、导入 `tickets.json` 并 seed Mock 业务域。
- 改造 I1/I2/I3 smoke 为 MySQL-only，不再创建 SQLite 临时库，也不再使用 `RUN_MYSQL_SMOKE`。
- `_seed_mock_domain_data` 同时覆盖 `tickets.json` 与 `call_transcripts.json` 的 `ticketDraft`，补齐真实 `TXN...`、`APP...`、amount、merchant、benefit seed。
- `MockBusinessRepository.get_transaction` 兼容 `merchant` / `merchantName` 参数。
- 修复 MySQL 下 `TicketRepository.close_ticket` 更新最新 `ai_results` 的 1093 问题，改为先查 latest id 再更新。
- 更新 `.env.example`、启动指南、数据库配置指南、交接说明和当前 findings。
- `doc/planning/task_plan.md` 模块 K checklist 已全部勾选。

验证：

- `.venv\Scripts\python.exe -m compileall ai-engine` 通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_i1_database.py` 通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_i2_crud.py` 通过；仅有 `fastapi.testclient` 关于 httpx 的 deprecation warning 和应用日志。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_i3_mock_tools.py` 通过。

过程中修复：

- 初次 I1 smoke 发现建库前 URL 仍带 `ticket_agent_test`，导致库不存在时连接失败；已改为显式构造无 database 的 server URL。
- I3 smoke 发现中文上下文中 `\bAPP...` / `\bTXN...` 边界抽取不稳定；已改为前后非英数边界。

待继续：

- 进入模块 M：PageAgent / SunPilot 业务化执行层。

## 会话：2026-07-21（Mock Tools NOT_FOUND 复查）

用户反馈：每个工单 AI 处理结果仍显示 `No matching mock business record was found.`。

排查结果：

- 演示库并非空库：`ticket_agent` 中已有 tickets、mock_customers、mock_cards、mock_applications、mock_transactions 等数据。
- 最新失败集中在 `benefit.query`，请求参数为 `MALL_CASHBACK_2026`、`CONCIERGE_2026` 等权益/活动码。
- 根因是 `_extract_business_code` 之前使用固定白名单，只覆盖 `DINING_`、`AIRPORT_`、`POINT_` 等前缀，未 seed `MALL_CASHBACK_2026`、`CONCIERGE_2026`，导致精确权益查询返回 NOT_FOUND。

已修复：

- 放宽 `ai-engine/models/database.py` 和 `ai-engine/tools/mock_executor.py` 的业务码抽取规则，支持通用 `ABC_DEF_2026` 形式，并排除 `APP...` / `TXN...`。
- I3 smoke 增加 `MALL_CASHBACK_2026` 和 `CONCIERGE_2026` 命中断言。
- 运行非破坏性 `init_db()` 补插演示库缺失权益 seed，不清空工单或日志。

验证：

- 演示库已存在：
  - `BEN-C20029-MALL_CASHBACK_2026`
  - `BEN-C20030-CONCIERGE_2026`
- 直接调用 `benefit.query`：
  - `C20029 + MALL_CASHBACK_2026` 成功并返回 `BEN...` 证据编号。
  - `C20030 + CONCIERGE_2026` 成功并返回 `BEN...` 证据编号。
- `ai-engine/evaluation/smoke_module_i3_mock_tools.py` 通过。
- `.venv\Scripts\python.exe -m compileall ai-engine` 通过。
- 从 `tickets.json` / `call_transcripts.json` 提取 15 个业务码，演示库缺失数为 0。

## 会话：2026-07-21（模块 M PageAgent 定位重写）

用户指出当前模块 M 仍偏“按钮/后台接口辅助”，不符合设想；新的方向应更接近 Ali PageAgent，或裁剪/改造其源码，让 PageAgent 以可见鼠标、点击、输入和右侧对话框贯穿发单与回单全流程。

已完成：

- 明确新定位：发单 Agent / 回单侧多 Agent 是业务大脑，PageAgent 是 GUI 执行员、演示前台和可审查操作轨迹。
- 明确接入路线：优先参考并裁剪 `C:\Users\heyunhui\OtherProjects\page-agent-main` 中的 `PageAgentCore`、`PageController` 和 `SimulatorMask`，外层加 TicketAgent 业务策略层。
- 明确 Demo 自动化边界：低风险高频链路允许全自动发单、回单和结单；中高风险链路默认填好页面并停在人工确认/升级节点。
- 已直接覆盖 `doc/planning/task_plan.md` 中原模块 M 内容，改为“贯穿全流程的 GUI PageAgent（P0 第一优先级）”。

关键结论：

- PageAgent 不替代原有五类业务 Agent；它承接业务 Agent 输出，在页面上可见地执行。
- 新模块 M 覆盖发单侧 PageAgent、回单侧 PageAgent、右侧对话框、可见鼠标/目标高亮、动作审计和失败接管。

## 会话：2026-07-21（模块 L 发单链路重构）

用户补充模块 L 原计划，并询问 PageAgent 重构是否最好和发单 Agent 同步进行；随后要求重构模块 L，必要时可与模块 K 整合。

已完成：

- 将 `doc/planning/task_plan.md` 中模块 L 从“通话记录发单侧 MVP”重构为“发单 Agent 与 PageAgent 发单链路（P0，与 M 同步）”。
- 明确模块 L 不再只是后台 `ticketDraft` 生成接口，而是发单 Agent 生成草稿、字段解释和页面任务提示，PageAgent 在前端可见地填单、提交和跳转。
- 明确模块 K 已完成 MySQL-only 与 Mock Tools 数据底座，L 依赖 K 的 `call_transcripts.json`、MySQL 演示库和 Mock 业务域 seed，但不合并进 K。
- 明确 L 与 M 的协作关系：L 是模块 M3 发单侧 PageAgent 的业务输入与接口契约；M 负责 GUI 执行壳、可见鼠标、动作审计和失败接管。
- 更新推荐执行顺序：先实现 M0/M2/M5 的 PageAgent 基础执行壳，再同步实现 L1/L2/L3 的可见发单链路，随后进入 M4 回单侧可见处理。

关键结论：

- 发单 Agent 决定“填什么”，PageAgent 展示“怎么填并提交”，回单侧多 Agent 继续决定“如何处理和回单”。
- 模块 K 是底座，不适合与 L 合并；L 应与 M 同步开发，避免先做成后台接口后再返工为可见页面执行。

## 会话：2026-07-21（Mock Tools UNKNOWN 复查）

用户反馈除两个已修复权益码外，其他工单仍显示 `当前场景未接入自动化工具，建议转人工处理`。

排查结果：

- 该文案来自 `EscalationAgent` 对 `intent_type=UNKNOWN` 的兜底，不是 Mock Tool 的 `NOT_FOUND`。
- 演示库旧结果中，`demo_points_001` 被 `UNSUPPORTED_SCENE_KEYWORDS` 的 `积分兑换/积分争议` 拦截成 UNKNOWN；`demo_failed_001` 存在 `amount='未提供'` 转 float 异常；`demo_activity_001` 仍有旧的 `MALL_CASHBACK_2026` NOT_FOUND 结果。
- 编排层此前只把 `ticket.content` 传给 Classifier/Intake，标题、场景、类目、子类目等结构化字段没有进入分类上下文。

已完成：

- `ClassifierAgent` 增加确定性分类兜底：优惠券、资料变更、申请进度、权益/活动/积分、交易核查先稳定路由到现有 workflow，再进入 LLM。
- `Orchestrator` 构造完整 ticket context，将标题、场景、类目、子类目、客户号、手机号、卡尾号、风险等级和正文传给 Classifier/Intake。
- `ResolutionAgent` 不再无条件跳过交易类工具；`EscalationAgent` 对字段齐全的交易核查允许先做只读 Mock 交易查询取证，随后仍走人工复核边界。
- `MockBusinessRepository.get_transaction` 对非数字金额做容错，`未提供` 不再触发 float 异常。
- 新增 `ai-engine/evaluation/smoke_module_k_workflow_routing.py`，覆盖积分兑换不再 UNKNOWN、活动资格进入权益查询、分期仍保留 UNKNOWN、交易取证门禁和非数字金额容错。
- 非重置刷新演示库中 `demo_points_001`、`demo_activity_001`、`demo_failed_001`、`demo_vip_001`、`desk_768504` 的最新 AI 结果；未清空工单或日志。

验证：

- `.venv\Scripts\python.exe -m compileall ai-engine` 通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_k_workflow_routing.py` 通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_i3_mock_tools.py` 通过。
- 演示库最新 AI 结果中，`demo_activity_001` 与 `demo_vip_001` 均为 `BENEFIT_QUERY / pending_human_review`，且生成 `BEN...` 证据编号；`demo_points_001` 为 `BENEFIT_QUERY / pending_info`；`demo_failed_001` 为 `TRANSACTION_DISPUTE / pending_info`，不再是 float 异常。

剩余边界：

- 当前最新 `UNKNOWN` 仅剩 `demo_installment_002`（分期手续费），属于当前五类 workflow 之外的后置场景，保留人工处理口径。
