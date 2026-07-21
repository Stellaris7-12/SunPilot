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

## 模块 M：贯穿全流程的 GUI PageAgent（P0 第一优先级）

目标：把 PageAgent 从“右侧辅助按钮”升级为贯穿发单与回单的可见 GUI 执行 Agent。多 Agent 仍是业务大脑，负责识别、判断、工具调用、风险和回单内容；PageAgent 是页面执行员，负责观察页面、移动鼠标、点击按钮、填写表单、展示执行过程，并把发单 Agent 与回单侧多 Agent 的结果转成可审查的页面操作。

核心定位：

```text
发单Agent / 回单侧多Agent = 业务大脑
PageAgent = GUI 执行员 + 演示前台 + 可审查操作轨迹
TicketAgent Policy Layer = 业务策略、风险边界、动作白名单、审计接管
Mock Tools / MySQL = 业务系统与证据底座
坐席/处理人员 = Demo 中可接管的最终责任人
```

### M0：接入路线与源码改造

- [ ] 采用“裁剪源码接入”路线，参考并迁移 `C:\Users\heyunhui\OtherProjects\page-agent-main` 中的核心能力，而不是只仿制按钮面板。
- [ ] 优先复用/裁剪 Ali PageAgent 的 `PageAgentCore` 执行循环、`PageController` DOM 索引/点击/输入能力、`SimulatorMask` 可见鼠标和目标高亮能力。
- [ ] 不直接接入完整 monorepo、Chrome Extension、MCP 和 website；首版只服务 TicketAgent 当前前端页面。
- [ ] 将裁剪代码放入前端独立模块，例如 `frontend/src/page-agent/`，外层包一层 TicketAgent 业务策略，不直接暴露原始通用执行能力。
- [ ] 若引入依赖，优先控制在 `zod`、`ai-motion`、必要的源码内联/本地模块；安装依赖前单独确认。

### M1：PageAgent 在业务流程中的地位

- [ ] 在产品与代码口径中明确：PageAgent 不替代 `ClassifierAgent`、`IntakeAgent`、`ResolutionAgent`、`EscalationAgent`、`NotificationAgent`。
- [ ] PageAgent 贯穿两段流程：发单侧辅助坐席从通话记录生成并提交工单；回单侧辅助处理人员完成方案推荐、证据定位、回复填充和高频结单。
- [ ] PageAgent 的任务来源分两类：用户在右侧对话框输入自然语言；多 Agent/发单 Agent 输出结构化页面任务。
- [ ] PageAgent 每一步都要可见：观察页面、规划动作、移动鼠标、点击/输入、验证结果、记录日志。

### M2：TicketAgent Policy Layer

- [ ] 新增 PageAgent 业务策略层，把自然语言或业务结果先解析成 TicketAgent 允许的页面任务，再交给 PageAgent 执行。
- [ ] 策略层输入包含 `PageBusinessContext`：当前场景、通话摘要、工单草稿、AI 处理结果、工具证据、风险等级、工单状态、可用业务按钮、当前页面锚点。
- [ ] 策略层输出包含 `PageTaskPlan`：目标、步骤、允许使用的 DOM 工具、预期结果、风险等级、是否允许 Demo 自动提交。
- [ ] 禁用 `execute_javascript`；DOM 点击/输入必须经过页面范围、元素语义、业务风险和目标校验。
- [ ] Demo 模式允许低风险高频链路全自动发单/回单/结单；中高风险链路仍演示 PageAgent 填好页面并停在确认/升级节点，除非明确使用演示全自动脚本。

### M3：发单侧 PageAgent

- [ ] 在企业壳增加通话发单工作区：展示通话记录、发单草稿、业务系统字段区和提交按钮。
- [ ] 发单 Agent 负责从 `call_transcripts.json` 或输入 transcript 中识别业务场景、工单类型、客户摘要和关键字段。
- [ ] PageAgent 接管页面操作：移动鼠标到发单入口，打开发单面板，选择通话样本，填入标题、客户号、手机号、卡尾、场景、优先级、摘要等字段。
- [ ] PageAgent 点击“一键提交工单/分发”完成创建，并跳转到新工单详情页。
- [ ] 发单侧日志展示“自动调取业务字段/自动生成摘要/提交工单/分发至处理队列”的步骤，不要求首版真实接 13 个外部系统，可用 Mock 数据和说明承接。

### M4：回单侧 PageAgent

- [ ] 处理人员打开工单后，PageAgent 可点击“生成处理建议”触发原有多 Agent 链路。
- [ ] 多 Agent 完成分类、字段补全、Mock Tools 调用、知识/历史案例匹配、回单建议和结案建议后，PageAgent 读取结果并执行页面动作。
- [ ] PageAgent 可见地定位证据链、打开系统审计、填入客户回单、插入证据编号、填内部处理意见和复核摘要。
- [ ] 高频低风险工单 Demo 中允许 PageAgent 点击保存草稿、提交复核并结案，形成“自动处理重复工单”的惊艳演示。
- [ ] 高风险或异常工单演示 PageAgent 自动预警、定位升级原因、填好处理意见并停在人工确认/升级区。

### M5：右侧对话框、鼠标和动作轨迹

- [ ] 将右侧 SunPilot 升级为 PageAgent 控制台：自然语言输入、当前目标、执行中工具、历史步骤、停止/接管按钮。
- [ ] 接入 Ali PageAgent 的 `activity` / `history` 思路，展示 thinking、executing、executed、retrying、error、done。
- [ ] 接入或复刻 `SimulatorMask`，在页面上显示可见鼠标、移动轨迹、点击波纹、目标高亮和遮罩。
- [ ] 页面操作必须有节奏感：滚动、定位、悬停、点击、输入、等待结果、验证成功，避免瞬间后台完成。
- [ ] 允许用户对 PageAgent 下达指令，例如“根据这通电话帮我发单”“处理当前工单并自动回单”“定位工具证据”“高频低风险直接结单”。

### M6：审计、失败接管与演示脚本

- [ ] 新增 `PageActionLog`：用户指令、业务上下文摘要、DOM 工具、目标元素、输入值摘要、执行结果、耗时、风险等级、停止原因。
- [ ] PageActionLog 与后端 Agent Trace 分开展示：Trace 证明业务大脑，PageActionLog 证明页面执行过程。
- [ ] 失败规则：目标元素找不到、模型选择不确定、状态不匹配、工具失败、超过最大步数、重复失败时停止并提示人工接管。
- [ ] 准备两条必跑 Demo：低风险“通话发单 -> 自动处理 -> 自动回单结单”；高风险“通话发单 -> 多 Agent 识别风险 -> PageAgent 填写并停在人工升级”。

### M 验收

- [ ] PageAgent 能以可见鼠标完成一条发单链路：打开发单区、填表、提交、跳转工单详情。
- [ ] PageAgent 能以可见鼠标完成一条回单链路：触发多 Agent、查看证据、填回单、保存/结案。
- [ ] 右侧控制台可输入任务并展示执行步骤、工具调用、失败/完成状态。
- [ ] 答辩时能讲清：多 Agent 没有被边缘化，它们负责业务决策；PageAgent 负责把业务决策变成可见、可审查、可接管的页面操作。
- [ ] 前端 `npm.cmd run build` 通过；若接入裁剪源码，保留来源说明和 MIT License 口径。

## 模块 L：发单 Agent 与 PageAgent 发单链路（P0，与 M 同步）

目标：把“通话结束后发单”做成可见的端到端链路。发单 Agent 负责理解通话、生成工单草稿和业务字段；PageAgent 负责在页面上移动鼠标、打开内嵌发单区、回填字段并提交/分发工单。模块 L 不替代模块 M，而是模块 M3 发单侧 PageAgent 的业务输入与接口契约。

与 K/M 的关系：

- 模块 K 已完成 MySQL-only 与 Mock Tools 数据底座，不再把 L 合并进 K。
- L 依赖 K 的 `call_transcripts.json`、MySQL 演示库和 Mock 业务域 seed，确保发单后工单能继续命中后续 Mock Tools。
- L 与 M 同步实现：L 产出 `ticketDraft`、字段解释和发单任务；M 用可见 GUI PageAgent 执行填单、提交和跳转。

### L1：发单 Agent / Call Intake 契约

- [ ] 新增 `POST /api/call-records/generate-ticket-draft`，定位为发单 Agent 接口，而不是第六个后端业务 Agent。
- [ ] 输入：`transcript`、可选 `callMeta`、可选 `sampleId`、可选 `operatorId`。
- [ ] 输出：`ticketDraft`、`callSummary`、`detectedScenario`、`detectedTicketType`、`keyFields`、`missingFields`、`confidence`、`sourceCallId`、`pageTaskHints`。
- [ ] `ticketDraft` 保持兼容现有 `POST /api/tickets`：`title`、`customerId`、`customerName`、`phone`、`cardLast4`、`scene`、`category`、`subcategory`、`priority`、`channel`、`riskLabel`、`riskLevel`、`content`。
- [ ] MVP 优先支持样本驱动：若 `sampleId` 命中 `call_transcripts.json`，直接返回样本草稿；自定义 transcript 再走规则抽取 + LLM 兜底。
- [ ] 发单 Agent 只负责发单前摘要和草稿，不参与后续回单侧多 Agent 编排；创建后的标准工单仍进入现有 `ClassifierAgent -> IntakeAgent -> ResolutionAgent -> EscalationAgent -> NotificationAgent`。

### L2：发单页面与 PageAgent 交接

- [ ] 在企业壳中新增“通话发单工作区”，包含通话记录列表、通话全文、自动摘要、草稿字段表单、字段来源/缺失提示和“一键提交工单”按钮。
- [ ] 为发单表单增加稳定页面锚点和语义属性，例如客户号、卡尾、场景、摘要、提交按钮，供 PageAgent DOM 观察和定位。
- [ ] 发单 Agent 返回 `pageTaskHints`，告诉 PageAgent 应填哪些字段、目标区域在哪里、提交后期望跳转到哪里。
- [ ] 坐席可手动编辑草稿；PageAgent 填写前如发现字段已被人工改动，需记录并按策略决定覆盖、追加或停下提示。

### L3：PageAgent 可见发单执行

- [ ] 用户在右侧 PageAgent 控制台输入“根据这通电话帮我发单”后，PageAgent 执行完整可见流程。
- [ ] PageAgent 步骤：选择通话样本/读取当前通话 -> 调用发单 Agent 生成草稿 -> 移动鼠标到发单入口 -> 打开发单区 -> 逐项填写字段 -> 高亮缺失/风险字段 -> 点击提交/分发。
- [ ] 提交成功后调用现有 `POST /api/tickets`，创建工单并跳转 `/tickets/:id`。
- [ ] 跳转后自动把当前 PageAgent 任务切换为回单侧任务，提示可继续“生成处理建议并自动回单”。

### L4：演示中的“13 个业务系统”表达

- [ ] 首版不真实接 13 个外部系统；用 Mock 业务域和页面文案表达“客户资料、卡片、交易、权益、申请、历史工单等业务数据已自动调取”。
- [ ] 发单侧展示字段来源：通话文本、客户资料系统、卡片系统、活动权益系统、交易系统、历史工单系统。
- [ ] 对缺失字段生成追问或人工补充提示，避免 PageAgent 在字段不足时硬提交。

### L 验收

- [ ] 从 `call_transcripts.json` 选择一条低风险通话，PageAgent 能可见地生成草稿、填表、提交并跳转新工单。
- [ ] 新工单继续进入原有多 Agent 回单侧处理链路，后续 Agent 不反复消费完整 transcript。
- [ ] 发单页面展示自动摘要、字段来源、缺失字段和分发结果。
- [ ] 答辩能讲清：发单 Agent 决定“填什么”，PageAgent 展示“怎么填并提交”，多 Agent 继续决定“如何处理和回单”。

## 模块 N：演示与答辩材料（P1）

目标：在开发收口后准备一套能讲清“方案选择、当前效果、边界和后续优化”的 Demo。

- [ ] 准备三条演示链路：低风险优惠券补发、中风险资料/分期人工确认、高风险交易争议或征信异议升级。
- [ ] 准备 PageAgent 对比口径：通用 Page Agent 强在网页泛化，TicketAgent PageAgent 强在信用卡业务上下文、权限门禁、证据审计和人工接管。
- [ ] 准备 Mock Tools 解释：代表外部业务系统能力适配层，不是真实银行系统直连。
- [ ] 准备 MySQL 解释：本地准生产演示沙盘，演示库和测试库分离。
- [ ] 准备待优化项：真实 ASR、外部遗留系统自动化、生产权限体系、更多业务数据、持久化 PageActionLog、监控告警。

## 推荐执行顺序

1. 2026-07-21：完成 K1/K2/K3 的诊断和最小修复，确保 MySQL + Mock Tools 可演示。
2. 2026-07-21 至 2026-07-22：实现 M0/M2/M5 的 PageAgent 基础执行壳、可见鼠标和右侧控制台。
3. 2026-07-22：同步实现 L1/L2/L3，让 PageAgent 完成发单侧可见填单提交。
4. 2026-07-22 至 2026-07-23：实现 M4 回单侧可见处理链路，打通自动处理、填回单和低风险结单。
5. 2026-07-23：跑后端 smoke、前端 build，整理 Demo 脚本和 PPT 要点。

## 非目标

- 不做真实银行生产系统直连。
- 不做真实 ASR 语音识别主线；可作为后续路线或演示素材。
- 不直接集成完整通用 page-agent 工程。
- 不把 PageAgent 放入后端五 Agent 编排中。
- 不允许 PageAgent 任意点击、任意 JS 执行或绕过人工确认/结案接口。
