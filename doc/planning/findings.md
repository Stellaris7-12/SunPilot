# TicketAgent 当前发现（2026-07-21）

## 资料来源

- `doc/guides/项目交接说明_20260721.md`
- `doc/requirements/修改意见7.21.txt`
- `doc/planning/page_agent_positioning.md`
- `doc/planning/backup/task_plan.before-new-plan-20260721.md`
- `doc/planning/backup/progress.before-new-plan-20260721.md`
- 当前代码：`ai-engine/config.py`、`ai-engine/models/database.py`、`ai-engine/tools/mock_executor.py`、`ai-engine/models/repositories.py`、`frontend/src/views/EnterpriseTicketShellView.vue`、`frontend/src/components/ai/PageAssistantPanel.vue`

## 核心业务判断

- 新需求要求把故事讲成完整闭环：客服电话/通话记录 -> 发单 -> 多 Agent 处理 -> PageAgent 辅助页面填单/回单 -> 人工复核结案。
- 导师在 2026-07-21 下午将 PageAgent 调整为第一优先级，强调右侧对话框、可见动态点击/执行过程，而不是完全后台自动处理。
- 交接文档同时提醒：MySQL-only 和 Mock Tools 收口应先保证，否则 PageAgent 演示会缺少稳定业务证据。
- 因此计划采用“底座优先修稳 + PageAgent 展示优先并行推进”的路线：先确保 MySQL/MockTools 不拖垮演示，再把 SunPilot 升级为受控 PageAgent。

## MySQL-only 改造现状

- 用户已确认不再考虑旧测评脚本；如需回归前置模块，应另写 MySQL-only 测评脚本。
- 模块 K 执行目标调整为彻底移除 SQLite 运行路径，不保留历史兼容分支。
- `ticket_agent` 用于开发/演示，`ticket_agent_test` 用于 I1/I2/I3 smoke，避免测试污染演示库。
- 本地 MySQL 可使用 `root` 连接，密码来自系统环境变量 `MYSQL_ROOT_PASSWORD`，不写入仓库。

## Mock Tools 现状

- `MockExecutor` 已经通过 `mock_business_repository` 查询客户、卡片、交易、权益、申请、权限和工具历史，设计方向是对的。
- 如果所有工单都升级人工，优先怀疑：后端连到旧 SQLite、MySQL DDL/seed 未执行、演示数据没有业务域表、字段无法命中。
- `_seed_mock_domain_data` 应从 `tickets.json` 和 `call_transcripts.json` 的 `ticketDraft` 派生 Mock 业务域数据。
- 交易 seed 必须优先提取真实 `TXN202607...` 等流水；没有真实流水时才回退到 `TXN{customer_id}`。

## PageAgent / SunPilot 现状

- 旧详情页已有 `frontend/src/components/ai/PageAssistantPanel.vue`，能力是按钮式动作栏：启动 AI、填回单、查看风险/缺失字段、查看工具目录、进入复核。
- 企业壳 `frontend/src/views/EnterpriseTicketShellView.vue` 已有右侧 SunPilot 区域，并支持动作：`process`、`fill_reply`、`locate_evidence`、`locate_missing`、`open_audit`、`prepare_review`、`prepare_confirm`。
- 当前还没有统一的 `PageContext`、`PageAction`、`PageActionRunner`、`PageActionLog`。
- 当前前端依赖只有 Vue/Pinia/Axios 等，没有引入通用 page-agent 或动画库；MVP 可用原生 Vue/CSS 实现动作流、光标和目标高亮。

## 通话发单现状

- `ai-engine/data/call_transcripts.json` 已存在 20 条自生成脱敏中文通话记录样本。
- 建单接口 `POST /api/tickets` 和前端 `createTicket` 已存在。
- 后续更稳的方式是新增发单侧 Call Intake：只把完整 transcript 转成标准 `ticketDraft`，再进入现有多 Agent 工单处理链路。
- 不建议让后续 Classifier/Resolution/Notification 每次直接消费完整 transcript，否则 token 成本、噪声和稳定性都会变差。
- 新定位下，通话发单不应只做成后台接口调用；发单 Agent 负责产出草稿和字段来源，PageAgent 负责以可见鼠标在页面上填单、提交和分发。因此模块 L 应并入模块 M3，作为“发单 Agent 与可见发单 PageAgent”的业务输入、页面契约和发单执行子链路；模块 K 只保留为已完成的数据与 Mock Tools 底座。

## 答辩口径

- TicketAgent 的 PageAgent 不应定位为“更通用的网页自动点击工具”，而应定位为信用卡工单场景下的受控页面执行层。
- 相比通用 Page Agent，差异化在业务上下文、状态机、风险等级、证据编号、工具审计、人工确认、失败接管和可评测。
- 演示上可以有动态鼠标/高亮/步骤流，但底层必须仍是白名单动作，不开放任意 DOM index 点击或任意 JavaScript 执行。

## Mock Tools / UNKNOWN 复查发现

- `当前场景未接入自动化工具，建议转人工处理` 是 `EscalationAgent` 在 `intent_type=UNKNOWN` 时的固定兜底文案，不等同于 Mock Tool 未命中。
- 本轮发现的误判来源主要有两类：一是 Classifier 只读取 `ticket.content`，没有使用标题、场景、类目、子类目；二是 `UNSUPPORTED_SCENE_KEYWORDS` 对“积分兑换/积分争议”过早拦截，导致可按权益/积分查询处理的样本落入 UNKNOWN。
- 稳定做法是先用确定性规则把演示库中已有五类 workflow 场景归一化，再把真正后置的分期、年费、还款协商、征信、投诉、挂失补卡等留给 UNKNOWN/人工。
- 交易类不应直接跳过工具；更贴近演示闭环的做法是先执行只读 Mock 交易查询获取证据，再保持人工复核/不可自动结案边界。
- Mock 交易查询必须容忍 `amount='未提供'` 等抽取值，不应在 Repository 层抛 `float` 转换异常；非数字金额应视为缺失并按客户号/商户等字段回退查询。
