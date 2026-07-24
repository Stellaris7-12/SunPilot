# TicketAgent 进度日志

> 2026-07-23，分支 `feature/dispatch-reply-refactor`

## 历史基准

PLAN1 全部 6 个阶段已完成。当前分支基于 `feature/sunpilot-agent-architecture` 分叉。

## 2026-07-23 PLAN2 执行

### 2026-07-23 本轮执行记录

| 模块 | 内容 | 状态 |
|------|------|------|
| D1-1 | 新增 `002_dispatch_ext.sql`，同步 `001_i1_schema.sql`、运行时 schema upgrade、Repository/API 字段贯通 | [x] |
| D1-2 | `workflow_config.json` 新增伪冒预防、伪冒调查、客户经营、市场企划、征信 5 个场景及 `specificFields` | [x] |
| D1-3 | 新增 `/dispatch` 动态发单表单，按通用字段 + 场景特有字段 v-for 渲染 | [x] |
| D1-4 | 新增 5 条 FITS 发单样本：`call-fraud-prevent`、`call-fraud-invest`、`call-customer-mgmt`、`call-marketing`、`call-credit` | [x] |
| D1-5 | 发单草稿生成按场景配置补 `extJson`、`orderPrefix`、`deadline`、`receiveUnit`、`needReply` | [x] |
| D1-6 | 静态验收 3 类字段差异：伪冒预防 10 项、市场企划 6 项、征信 4 项 | [x] |
| S2-1 | 新建 `DispatchView.vue`，路由 `/dispatch` 承载通话发单工作台 | [x] |
| S2-2 | `EnterpriseTicketShellView.vue` 移除发单表单，保留回单、AI、证据、SunPilot 处理区 | [x] |
| S2-3 | 发单提交后 `router.push(/tickets/:id)`；首页和顶栏增加发单入口 | [x] |
| S2-4 | `npm.cmd run build` 通过；SunPilot 已按 `/dispatch` 显示发单动作，`/tickets`/`/tickets/:id` 保持回单口径 | [x] |

### 验证结果

- `node` JSON 验证通过：5 个新 workflow 场景均有 `specificFields`，字段数分别为 10/4/3/6/4。
- `node` 样本验证通过：5 条新通话样本均有 `ticketDraft.extJson`。
- `.venv\Scripts\python.exe -m compileall ai-engine` 通过。
- `frontend: npm.cmd run build` 通过。
- 已在用户确认后执行 `init_db()`，真实 MySQL `tickets` 表已具备 `ext_json`、`order_prefix`、`biz_type`、`biz_sub_type`、`deadline`、`receive_unit`、`need_reply`。
- 入库 smoke 已通过：`codex_smoke_ext_192136421883` 读回 `order_prefix=30`、`biz_type=市场企划`、`biz_sub_type=饭票总对总-麦当劳`、`ext_json.remark=订单号0006258`、`ext_json.cardName=白金卡`。

### 并行任务（后端+文档，与前端的用户改动无冲突）

| 时间 | 模块 | 内容 | 状态 |
|------|------|------|------|
| - | PPT | 新增 `答辩PPT逐页讲稿.md`，15 页逐页讲述要点+时间分配 | [x] |
| - | Mock | 新增 `mock_domain_seed.json`（5 客户+6 卡片+3 权益+4 交易+3 申请），独立于工单 | [x] |
| - | Mock | `database.py` 新增 `_seed_from_independent_data()`，优先加载独立种子，工单兜底 | [x] |
| - | PageTask | 已确认：`_build_reply_page_task` → `AiProcessResult.page_task` → bridge `onPageTask` 端到端打通 | [x] |

### 降级项

| 模块 | 状态 | 降级口径 |
|------|------|----------|
| P0-3 Mock 独立化 | 降级 | "架构抽象正确，独立种子是下一步工程工作" |
| P1-1 PageTask 链路 | 降级 | "协议已定义，执行器已完成，当前用自然语言通道" |
| P1-2 Schema 校验 | 降级 | "框架已建，demo 阶段未强制启用" |

## 2026-07-23 Agent 链路收口

| 模块 | 内容 | 状态 |
|------|------|------|
| FITS 分类 | Classifier 以 FITS 七类为主合同，纯规则咨询不再被 LLM 兜底误分类为市场企划 | [x] |
| 发单 PageTask | 发单主目标保持 `dispatch-submit`，同时保留 `draft-submit` 兼容 hint，避免旧 PageAgent 契约断开 | [x] |
| Intake | 静态兜底字段 schema 改为 FITS 七类，标准摘要可走确定性抽取 | [x] |
| Escalation | 调单扣款/客户经营风控门禁改为中文场景判断，人工确认不再错误升级 | [x] |
| Workflow fallback | 内置 `DEFAULT_WORKFLOW_CONFIG` 改为 FITS 七类，配置文件异常时不回落到旧英文 intent | [x] |
| Tool Calling | 烟测改为 FITS 主链路；默认确定性选推荐工具，显式开启时仍验证 LLM native tool calling | [x] |

### 本轮验证

- `.venv\Scripts\python.exe -m compileall ai-engine` 通过。
- `smoke_module_p_workflow_contracts.py` 通过。
- `smoke_module_m_call_intake.py` 通过。
- `smoke_module_k_workflow_routing.py` 通过。
- `smoke_module_p_agent_contracts.py` 通过。
- `smoke_module_o_tool_calling.py` 通过。
- `smoke_module_p_architecture_guardrails.py` 通过。
- `smoke_module_i3_mock_tools.py` 通过。

## 2026-07-24 Agent 链路补丁

| 模块 | 内容 | 状态 |
|------|------|------|
| Agent 上下文 | `TicketContext.to_summary_text()` 补齐客户姓名、工单扩展字段、接单单位、业务细类等结构化字段，避免 Agent 只依赖正文猜测 | [x] |
| Intake 契约 | `_structured_values()` 增加 `客户姓名 -> customerName` 映射，修复 `call-marketing` 明明有客户姓名却进入 `pending_info` 的问题 | [x] |
| Resolution 参数 | 工具参数先合并 fields，再按工具 schema 做 canonical 归一，确保 `customerFeedback -> queryReason` 不丢失 | [x] |
| Mock Tools 补全 | `MockExecutor.enrich_params()` 先做参数 alias 归一，再执行权益/交易等只读补全 | [x] |
| 市场企划 E2E | `call-marketing` 发单 -> 建单 -> AI 处理，已到 `pending_human_review`，调用 `benefit.query`，生成 `BEN...` 证据号 | [x] |

### 2026-07-24 验证

- `.venv\Scripts\python.exe -m compileall ai-engine` 通过。
- `call-marketing` 端到端检查通过：状态 `pending_human_review`；意图 `市场企划`；工具 `benefit.query`；参数含 `customerId/queryReason/benefitCode=DINING_MCD`；无缺失字段；有证据号。
- `smoke_module_m_call_intake.py` 通过。
- `smoke_module_k_workflow_routing.py` 通过。
- `smoke_module_o_tool_calling.py` 通过。
- `smoke_module_p_agent_contracts.py` 通过。
- `smoke_module_i3_mock_tools.py` 通过。
- `smoke_module_p_workflow_contracts.py` 通过。
- `smoke_module_p_architecture_guardrails.py` 通过。

### 剩余风险

- `smoke_module_a/b/c/d.py` 仍是旧英文 intent / 旧工具契约口径，需后续迁移到 FITS 场景，不建议为通过旧 smoke 回退运行时设计。
- MySQL smoke 输出大量 `VALUES()` deprecation warning，当前不阻断功能，但后续应整理 upsert SQL。
