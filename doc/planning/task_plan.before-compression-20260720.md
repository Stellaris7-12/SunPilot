# 任务计划：TicketAgent 核心闭环开发路线

## 目标

把当前 TicketAgent 从“可运行 Demo”推进到“可演示、可测评、可解释的信用卡工单智能处理闭环”。

本阶段不追求一次性做完整企业级工单系统，也不把 A2A、PageAgent、真实语音识别做成主线。主线是先让系统稳定完成：接收工单/通话文本、识别诉求、补齐信息、分类定级、调用业务能力、生成回单、通知/回访、必要时升级人工，并能用数据集和指标证明效果。

## 核心原则

1. 先跑通业务闭环，再增加进阶能力。
2. 先稳定后端契约和 Agent 输出，再优化前端呈现。
3. 先用 Mock Tool/API 打通执行链路，再接 MCP、PageAgent 或真实系统。
4. 先做中等规模、高质量标注数据和评测脚本；样本优先服务场景覆盖、回归验证和指标展示，不把数量本身作为目标。
5. 先沿用当前手写 Orchestrator，等分支和状态管理复杂后再评估 LangGraph。
6. 风险分级不作为独立核心模块，只作为分类、执行、升级策略中的业务规则。

## 当前代码与新 Agent 重构口径

| 新业务 Agent | 职责 | 代码重构目标 | 当前策略 |
|-------------|------|--------------|----------|
| Intake Agent / 接单与信息提取 | 接收工单、通话文本、表单输入，抽取标题、描述、用户、关键字段；信息不足时生成追问 | `ExtractAgent` 重构为 `IntakeAgent` | P0 直接采用业务命名，旧文件短期做兼容 shim |
| Classifier Agent / 分类与优先级判定 | 判断工单类型、业务场景、处理优先级；规则先行，LLM 处理复杂表达 | `IntentAgent` 重构为 `ClassifierAgent` | P0 核心 |
| Dispatcher Agent / 智能派单 | 根据类型、紧急程度、技能、负载，把工单派给人、团队或 Agent | 当前暂无完整实现 | P2 进阶，不抢主线 |
| Resolution Agent / 解决方案与执行 | 查询知识库，调用接口/API/Mock Tool，未来接 MCP 或 PageAgent 执行业务动作 | `ToolCallingAgent` 重构为 `ResolutionAgent`，继续使用 `MockExecutor` + `ToolRegistry` | P0 核心，必须有审计证据 |
| Notification Agent / 通知与回访 | 生成处理说明、客户回单、状态通知、满意度回访 | `ReplyAgent` 重构为 `NotificationAgent` | P0/P1，先做回单和状态通知 |
| Escalation Agent / 升级与兜底 | 处理字段缺失、工具失败、SLA 即将超时、合规或异常场景，转人工或升级 | `VerifyAgent` 重构为 `EscalationAgent`，继续结合状态机和人工确认逻辑 | P0 先做兜底策略，不单独炫技 |

## 推荐主流程

```text
多渠道输入/通话文本
  -> Intake Agent：接单、字段抽取、缺失信息提示
  -> Classifier Agent：工单类型、业务场景、优先级判定
  -> Resolution Agent：选择处理方案，调用 API/Mock Tool，记录证据
  -> Notification Agent：生成回单、状态通知、回访提示
  -> Escalation Agent：贯穿全流程，处理异常、超时、失败、人工升级
  -> 工单结案/人工复核/转派
```

Dispatcher Agent 不放入当前核心闭环。需要体现“派单中心”时，先用规则或占位说明表达，等核心闭环稳定后再实现工程师/团队/Agent 的动态匹配。

## 模块 A：后端契约与工单状态稳定化（P0）已完成

目标：让 API、SSE、状态流转、数据库持久化成为稳定底座。

- [x] 梳理工单创建、AI 处理、人工确认、回单、结单、升级的 API 契约。
- [x] 统一后端对外字段命名和前端类型，避免 AI 结果字段漂移。
- [x] 统一 SSE 终态事件：完成、暂停待补充、升级人工、失败。
- [x] 补齐处理结果持久化：分类结果、抽取字段、工具调用结果、回单内容、处理状态、处理耗时。
- [x] 为数据库变更采用兼容迁移，不做破坏性重建。
- [x] 建立脚本化冒烟测试，覆盖自动处理、信息不足、工具失败、升级人工四类路径。

验收标准：
- 后端服务可启动，Swagger 可访问。
- 工单从输入到处理结果可重复跑通。
- 前端能稳定消费同一套 AI 结果结构。
- 失败、暂停、升级都有明确状态和可解释原因。

## 模块 B：Agent 编排与业务化封装（P0）已完成

目标：用新的业务 Agent 命名组织系统，采用受控重构统一代码、Trace、前端和文档口径。

- [x] 在文档、Trace、前端展示中采用 Intake、Classifier、Resolution、Notification、Escalation 的业务命名。
- [x] 代码层直接重构为 `IntakeAgent`、`ClassifierAgent`、`ResolutionAgent`、`NotificationAgent`、`EscalationAgent`，避免长期维护冗余映射层。
- [x] 旧 Agent 文件短期保留为兼容 shim，只转发到新业务 Agent 类；模块 B/C 稳定后再评估删除。
- [ ] 清理旧模块相关内容：移除旧 Agent shim 文件，更新兼容测试、Orchestrator 旧别名和文档口径，确认不再依赖 `IntentAgent`、`ExtractAgent`、`VerifyAgent`、`ToolCallingAgent`、`ReplyAgent`。
- [x] 在 Orchestrator 中明确每个业务 Agent 的输入、输出和失败处理。
- [x] 将规则策略和 LLM 判断分层：规则覆盖高频明确场景，LLM 处理口语化和复杂表达。
- [x] 设计轻量 `workflow_config`，描述场景、必填字段、推荐工具、是否需人工确认、默认通知模板。
- [x] 保持模块 A 的 API、SSE 终态、状态机、持久化和工具审计契约不变；模块 B 完成后只做回归验证，不重做模块 A。
- [x] 暂不迁移 LangGraph；等出现复杂分支、checkpoint、replay、跨会话恢复需求后再评估。

验收标准：
- 汇报时能用业务 Agent 名称讲清流程。
- 新增一个工单场景时，优先改配置、样本和工具，不大改 Orchestrator 主体。
- 模块 A 冒烟测试继续通过，证明命名重构没有破坏既有契约。
- 旧导入在兼容期内仍能运行，不因命名调整造成外部调用或测试断裂。

## 模块 C：Resolution 执行能力与工具审计（P0）已完成

目标：把“AI 给建议”升级为“AI 调用业务能力并留下证据”。

- [x] 梳理现有 Mock Tool：补券、查询交易、修改资料、查询权益、进度查询等。
- [x] 为每次工具调用记录审计日志：ticket_id、tool_name、request_json、response_json、evidence_id、success、duration_ms、failure_reason。
- [x] 统一工具返回结构：处理动作、业务结果、证据编号、下一步建议、是否需要人工。
- [x] 工具参数缺失时回到 Intake Agent 生成追问或补充提示。
- [x] 工具失败、结果冲突、权限不足时交给 Escalation Agent 升级人工。
- [x] MCP 作为进阶接入方式预留接口边界，不在核心闭环中强依赖。
- [x] Page Agent 采用三阶段引入，不直接进入高风险外部系统自动化：
  - 第一阶段：前端页面助手。在 `frontend/src/views/TicketDetailView.vue` 增加“页面助手”入口，只操作当前工单详情页，支持把 AI 回单草稿填入回单框、检查当前工单风险和缺失字段、打开工具面板并定位补券工具、滚动到审核区域等低风险动作。
  - 第二阶段：发单/回单表单自动填充。等动态工单表单更完整后，将 Intake Agent/ExtractAgent 的抽取结果转成页面填充动作，用于减少人工复制粘贴。
  - 第三阶段：外部遗留系统自动化。仅当行内系统没有 API 时，才考虑 Page Agent Ext / MCP 方案操作浏览器页面；该能力属于高风险扩展，必须有白名单、脱敏、审计、人工确认。

验收标准：
- 每次自动执行都有可展示的证据编号。
- 前端能说明系统调用了什么能力、传入了什么关键参数、得到什么结果。
- Mock Tool 可替换为真实 API 或 MCP Server，而不改变上层业务流程。

## 模块 D：Notification 与回单闭环（P0）

目标：让系统不止会处理，还会把处理结果清楚反馈给客户和业务人员。

- [x] 生成标准化回单：处理结果、证据编号、客户可理解说明、后续建议。
- [x] 根据工单状态生成内部通知：已处理、待补充、待人工复核、已升级、已结案。
- [x] 对可自动闭环的标准场景，支持自动生成最终回单和结案建议。
- [x] 对需人工判断的场景，生成复核摘要和建议操作，不直接提交敏感动作。
- [x] 回访能力先做模板和状态预留，后续再做满意度收集。

验收标准：
- 回单内容可以直接用于演示，不是开发调试文本。
- 业务人员能看到“系统做了什么、为什么这么做、下一步谁处理”。
- 人工复核时有摘要，不需要重新阅读完整 Trace。

## 模块 E：数据集构建与场景扩展（P1）已完成

目标：从少量演示样本升级为可评测、可扩展的小型业务数据集。模块 E 的样本主要用于 Agent 效果评测、场景覆盖证明和后续回归测试，不作为模型训练数据；当前 MVP 优先构建 40 条左右的高质量标注样本，而不是追求大而粗的数据量。

- [x] 完成外部数据源预检：CFPB 投诉库适合扩展金融投诉/信用卡争议工单来源，BANKING77 适合扩展短文本意图分类和工具路由评测。
- [x] 修改 `.gitignore`，忽略 `ai-engine/data/external/` 和 `ai-engine/data/generated/`，避免大文件数据集进入 Git。
- [x] 将可用数据目录迁移到项目内：`ai-engine/data/external/` 存放外部原始数据，`ai-engine/data/generated/` 存放转换/生成数据；下载目录根部旧版小配置不覆盖当前项目配置。
- [x] 构建 40 条左右的 MVP 标注样本；数量下限按 40 条验收，后续再按评测需要扩展到 50+ 或 100+。
- [x] 每条样本包含：通话记录/工单原文、正确意图、正确工单类型、必填字段、期望工具、期望处理结果、回单要点、是否需要人工介入。
- [x] Demo 种子数据和评测数据分开存放，避免演示数据污染评测。
- [x] 所有客户号、手机号、卡号、证件号使用模拟值。
- [x] 先覆盖标准高频场景，再扩展投诉、争议、跨部门协作等复杂场景。

当前数据源使用判断：
- CFPB Consumer Complaint Database 体量较大，语言为英文，适合抽样生成金融投诉、交易争议、账单费用、征信异议等工单原文；不能直接作为中文通话记录或最终标注样本使用，后续需要抽样、脱敏确认、翻译/改写和补齐期望输出。
- BANKING77 共 13,083 条英文银行客服短文本意图样本，适合 Classifier Agent 的意图扩展、混淆测试和工具路由回归；它不是完整工单，不能单独满足模块 E 的样本结构要求。
- `ai-engine/data/tickets.json` 继续作为小规模 Demo 种子数据；模块 E 评测样本应另建独立文件，避免污染演示初始化数据。
- 样本量不是越大越好；当前更看重场景覆盖、字段标注一致性、期望工具和期望处理结果是否清楚。100+ 样本适合作为模块 F 后续严肃指标、混淆矩阵和稳定性回归扩展，不作为当前模块 E 的 MVP 必达范围。
- `ai-engine/data/evaluation_samples.json` 已作为独立评测样本集落地，当前包含 40 条中文模拟标注样本；`ai-engine/evaluation/smoke_module_e.py` 负责校验样本结构、脱敏、场景覆盖、Demo/评测分离和评测入口读取。

优先场景池：
- 权益/优惠券补发。
- 申请进度查询。
- 地址、手机号、联系人等资料变更。
- 账单/交易查询。
- 活动资格或权益资格核验。
- 分期提前结清咨询。
- 还款协商或延期咨询。
- 卡片挂失、补卡、停卡。
- 额度咨询、临时额度或固定额度调整。
- 年费减免或年费调整。
- 积分到账、积分兑换、积分争议。
- 交易争议、调单、拒付、盗刷疑似场景。
- 征信异议、申请资料补充。
- 商务卡公司资料变更。
- 投诉、催办、跨部门协办。

验收标准：
- 至少 40 条样本能被评测脚本读取。
- 每条样本都有明确标签和期望输出。
- 场景数量足以说明系统不是只为 3 个固定案例硬编码，并能覆盖自动处理、待补充、人工确认、升级人工等关键路径。

## 模块 F：Agent 测评与效果指标（P1）测评框架已完成

目标：让答辩和汇报从“看起来能跑”升级为“有指标证明”。

- [x] 评测 Intake Agent：字段抽取完整率、缺失字段识别正确率。
- [x] 评测 Classifier Agent：意图准确率、工单类型准确率、优先级判断一致率。
- [x] 评测 Resolution Agent：工具选择正确率、参数正确率、执行成功率。
- [x] 评测 Notification Agent：回单要点覆盖率、模板合规性、可读性人工评分。
- [x] 评测 Escalation Agent：异常识别正确率、人工介入判断合理性。
- [x] 汇总端到端指标：闭环成功率、平均处理耗时、人工节省步骤、预计节省时间。

当前实现：
- `ai-engine/evaluation/evaluator.py` 已从演示分数改为可对真实 Agent 输出 records 计分，并在未执行完整 LLM 评测时返回基于标注样本的参考摘要。
- `ai-engine/evaluation/run_module_f.py` 可在配置 LLM Key 后逐条运行 40 条样本的五类 Agent 链路，不写主数据库。
- `GET /api/evaluation/metrics` 保留旧顶层字段，并新增 `agents`、`closedLoopSuccessRate`、`avgProcessingMs`、`evaluatedSamples`、`avgManualStepsSaved`、`source`。
- `ai-engine/evaluation/smoke_module_f.py` 覆盖自动处理、待补充和升级人工三类评测计分路径。

真实 LLM 阶段性执行记录：
- [x] 确认当前终端可读取 `DEEPSEEK_API_KEY`，且不在日志中输出真实 Key。
- [x] 先执行 5 条预检样本：
  ```powershell
  .venv\Scripts\python.exe ai-engine\evaluation\run_module_f.py --limit 5 --records
  ```
- [x] 检查 5 条预检结果，重点关注 `source=agent_run`、是否全部跑完、是否存在 LLM 超时或 JSON 解析失败。
- [x] 对预检低分项做归因，不直接把所有低分解释为 Agent 能力问题：
  - `workflowConsistency` 偏低：优先检查 LLM 是否返回 `workflow_name`，以及计分字段是否需要兼容 snake_case/camelCase。
  - `replyPointCoverage` 偏低：优先检查中文回单要点匹配是否过严，必要时记录为评分口径问题。
  - `humanInterventionAccuracy` 偏低：优先检查 `pending_human_review`、`pending_info` 和真正人工介入之间的口径差异。
- [x] 完成至少 3 轮真实 LLM 小样本迭代：第 1 轮定位 workflow/reply/human 低分，第 2 轮修正 Resolution/参数/人工口径，第 3 轮将回单要点改为业务槽位覆盖。
- [x] 执行 12 条真实 LLM 扩展回归，覆盖优惠券补发、申请进度、资料变更等核心场景。
- [x] 预检链路稳定后执行完整 40 条真实 LLM 测评：
  ```powershell
  .venv\Scripts\python.exe ai-engine\evaluation\run_module_f.py --records
  ```
- [x] 汇总真实测评阶段性结果：12 条真实回归中 `intentAccuracy=1.0`、`fieldCompleteness=1.0`、`workflowConsistency=1.0`、`replyPointCoverage=0.9655`、`humanInterventionAccuracy=1.0`、`toolCorrectness=0.8571`、`closedLoopSuccessRate=0.8333`。
- [x] 完整 40 条真实 LLM 测评已在模块 F+ 中收口，最终结果保存到 `ai-engine/evaluation/module_f_full_final3_20260719.json`，`source=agent_run`、`evaluatedSamples=40`。

验收标准：
- 后端或脚本能基于标注样本输出一组真实指标。
- 指标能支撑业务表达：更快、更准、更规范、更可追溯。
- 每次修改 Agent 后能跑回归样本，避免只凭感觉调 Prompt。

## 模块 F+：真实 LLM 全量测评与指标收口（P1）已完成

目标：在模块 F 测评框架和三轮真实 LLM 小样本迭代已经稳定的基础上，完成一轮可复述、可追溯、可用于答辩的全量真实 LLM 测评报告。该阶段不再盲目调分，而是把“真实链路表现、评分口径、残留风险、是否进入模块 G”说清楚。

执行原则：
- 真实 LLM 测评使用系统环境变量中的 DeepSeek API Key，不打印、不写入、不提交真实 Key。
- 全量测评优先读取 `ai-engine/data/evaluation_samples.json` 的 40 条样本，不污染 Demo 种子数据和主业务数据库。
- 每轮真实测评都要保留可追溯输出：样本数、运行来源、核心指标、低分样本、异常类型和修复决策。
- 若 LLM 超时、限流或 JSON 解析失败，不重复盲跑同一命令；先记录失败样本，再判断是重试、降并发、缩小批次还是修代码。
- 区分 Agent 能力问题与评分口径问题：只有确认是业务链路缺陷时才改 Agent；评分误伤优先修 `Evaluator` 并补 smoke 回归。

新的测评计划：
- [x] 执行全量前置检查：确认 `DEEPSEEK_API_KEY` 可用但不输出 Key；确认 `evaluation_samples.json` 为 40 条；确认当前未依赖真实数据库写入。
- [x] 执行一轮完整 40 条真实 LLM 测评：
  ```powershell
  .venv\Scripts\python.exe ai-engine\evaluation\run_module_f.py --records
  ```
- [x] 汇总全量真实测评指标，至少记录：`source`、`evaluatedSamples`、`intentAccuracy`、`fieldCompleteness`、`toolCorrectness`、`workflowConsistency`、`replyPointCoverage`、`humanInterventionAccuracy`、`closedLoopSuccessRate`、`avgProcessingMs`。
- [x] 对低于阶段性 12 条回归的指标做样本级归因，按以下优先级分类：
  - Agent 输出问题：字段抽取、workflow 选择、工具参数、人工介入判断、回单内容确实不符合预期。
  - 评分口径问题：中文表达等价但未被识别、待补充/人工确认口径混淆、咨询类/无工具类样本被工具指标误伤。
  - 样本标注问题：期望状态、期望工具、回单要点或人工介入标签与当前业务规则冲突。
  - 外部服务问题：超时、限流、LLM 非 JSON 输出或临时网络错误。
- [x] 至少完成一轮针对低分项的修复或标注/评分口径修正，并运行相关 smoke：
  ```powershell
  .venv\Scripts\python.exe ai-engine\evaluation\smoke_module_f.py
  ```
- [x] 如修复影响核心链路，补跑模块 A-F 的后端 smoke；如影响前端类型或展示，补跑前端构建。
- [x] 生成最终测评结论，写入 `doc/planning/progress.md` 和必要的 `doc/planning/findings.md`：说明全量结果、修复内容、残留风险、是否允许进入模块 G。

最终真实 LLM 全量结果：
- 初始 40 条全量测评已完成，结果保存到 `ai-engine/evaluation/module_f_full_20260719.json`，指标为 `intentAccuracy=0.725`、`fieldCompleteness=0.8911`、`toolCorrectness=0.7778`、`replyPointCoverage=0.8539`、`humanInterventionAccuracy=0.7`、`closedLoopSuccessRate=0.6`。
- 子 Agent 只读审查确认低分主因是 UNKNOWN 扩展场景误分类、`pending_human_confirm` 未显式建模、状态/人工介入口径混淆和敏感资料变更先执行工具的链路风险。
- 经过多轮真实问题子集回归和链路修复后，最终 40 条真实 LLM 回归保存到 `ai-engine/evaluation/module_f_full_final3_20260719.json`，`source=agent_run`、`evaluatedSamples=40`。
- 最终指标：`intentAccuracy=1.0`、`fieldCompleteness=1.0`、`toolCorrectness=1.0`、`workflowConsistency=1.0`、`replyPointCoverage=0.9888`、`humanInterventionAccuracy=1.0`、`closedLoopSuccessRate=1.0`、`avgProcessingMs=6529.6`。
- `closedLoopSuccessRate` 当前工程含义是“期望状态匹配率”，不是实际客户闭环结案率；模块 G 展示时应优先解释为状态/预期结果匹配。

F+ 验收标准：
- 完整 40 条真实 LLM 测评成功完成，或清楚记录未完成原因、已完成样本数和下一步处理策略。
- 指标不是只给平均分；必须能追溯到低分样本和问题类型。
- 至少有一轮“全量测评 -> 问题归因 -> 修复/口径调整 -> 回归验证”的闭环。
- 模块 F 的 smoke 回归通过；如触及核心链路，模块 A-F smoke 回归通过。
- 文档中明确区分“12 条阶段性真实回归结果”和“40 条全量真实测评结果”。

## 模块 G：坐席业务工作台重构（P1）

目标：把前端从“AI Demo 展示页”重构为面向一线坐席/业务员的信用卡工单处理工作台。前端第一优先级不是展示 Agent，而是帮助坐席更快完成接单、分诊、核验、处理、复核、回单和升级。Agent 信息默认以业务动作摘要呈现，技术链路只放在审计抽屉中服务调试和答辩追问。

设计口径：
- 当前产品形态是独立 Web 坐席工作台，远期可内嵌为工单系统侧边栏、插件或工作流节点。
- 主角色是一线坐席/业务员，不是纯技术演示者；主管视角和评测视角作为辅助页面或辅助区。
- 页面语言使用坐席能直接操作的业务词：待补充、待确认、待复核、已升级、证据编号、下一负责人、建议动作、客户回单。
- AI/Agent 露出方式采用业务化摘要：接单提取、业务分诊、资料核验、执行处理、回单生成、人工复核；`IntakeAgent`、`ClassifierAgent` 等技术名仅保留在“技术审计/执行明细”折叠区。

重构任务：
- [x] 重构首页为坐席工作池，而不是空白选择页或普通 Demo 列表；按“待处理、待补充、待人工确认、待复核、已升级、可结案建议”组织队列。
- [x] 工单列表卡片展示坐席扫单必需信息：工单号、客户、场景族、风险、当前状态、等待原因、下一步动作和是否已有 AI 结果。
- [x] 增加场景族与状态筛选：权益/优惠券、申请进度、资料变更、交易/争议、投诉升级、人工协办类，以及 `pending_info`、`pending_human_confirm`、`pending_human_review`、`escalated` 等关键状态。
- [x] 重构工单详情为案件处理台：首屏展示工单场景、当前状态、处理结论、下一负责人、证据编号、建议动作，不再把 Agent Trace 放在主视觉位置。
- [x] 中间主区域展示客户诉求、关键字段、缺失字段、核验结果、工具执行结果、业务证据和处理结论，按坐席阅读顺序组织。
- [x] 右侧固定操作栏提供坐席动作：启动 AI 处理、填入回单、请求补充、人工确认、查看证据、定位工具、复核结案；按钮可用状态必须跟当前工单状态一致。
- [x] 对自动工具型场景（补券、权益查询、申请进度）突出“字段完整性 -> 工具调用 -> 业务结果 -> 证据编号 -> 回单建议”。
- [x] 对敏感确认型场景（资料变更、交易核查、境外交易）突出身份核验、风险原因、人工确认入口和不可直接自动执行的原因。
- [x] 对高风险升级型场景（盗刷、征信异议、投诉、跨部门协办）突出升级原因、接管建议、禁止自动结论和后续人工归属。
- [x] 对信息缺失型场景突出缺失字段、客户追问话术和补齐后继续处理的路径。
- [x] 保留开发者 Trace、原始 Agent 步骤、工具入参/出参 JSON 等信息，但统一收纳到“技术审计/执行明细”折叠区，默认不干扰坐席主流程。
- [x] 增加评测摘要辅助区或独立视图，消费 `/api/evaluation/metrics`，展示 40 条真实 LLM 测评结果、状态/预期结果匹配率、工具命中率、回单覆盖率、平均耗时和人工节省步骤。
- [x] 修复当前前端中文文案乱码问题，所有用户可见文案统一 UTF-8，并用业务文案替换开发调试式描述。
- [x] 建立前端设计系统：专业、克制、可扫描的银行运营台风格；风险色只用于状态和告警；证据编号、工具名、流水号使用等宽字体；避免大面积渐变和泛 AI 风格装饰。
- [x] 响应式重构：桌面优先三栏工作台，窄屏降级为队列/详情/操作区可切换布局，保证文本、按钮和证据编号不重叠。

验收标准：
- 一线坐席 30 秒内能判断：当前是什么案子、处于什么状态、AI 做了什么、下一步谁处理、自己该点哪个操作。
- 主界面不依赖解释底层 Agent 字段即可完成演示；技术 Trace 只在需要追问时展开。
- 前端能稳定展示证据链、客户回单、人工介入原因、缺失字段、工具结果、升级理由和评测摘要。
- 自动处理、待补充、待人工确认、待人工复核、升级人工、失败和结案建议都有一等 UI 状态。
- 补券、申请进度、资料变更、权益查询、交易争议、投诉升级等核心场景在页面上有不同处理重点，而不是套同一张通用结果卡。
- `closedLoopSuccessRate` 在前端明确解释为“状态/预期结果匹配率”，不误称为真实客户结案率。
- 修改后运行 `cd frontend && npm run build` 通过；如无法运行，需要记录原因。

## 模块 G+：企业工单系统壳与 Agent Copilot 解耦接入（P1）已完成

目标：在已完成的坐席业务工作台基础上，快速开发一个更接近真实企业工单系统的前端壳。这个壳不是一次性演示页面，而是后续补齐真实工单系统时可以继续扩展的前端框架雏形；Agent 助手以低耦合侧边栏、悬浮窗或插件组件方式接入，不直接吞掉原系统主流程。

设计口径：
- 当前阶段优先让观众第一眼看到“企业/银行客服工单详情系统中接入了 Agent 助手”，而不是“一个独立 AI Demo 页”。
- 企业工单系统壳负责承载主业务流程：菜单、标签页、工单详情、客户/卡片信息、发单内容、处理日志、回单内容、状态流转和坐席操作。
- Agent Copilot 负责辅助坐席：读取当前工单上下文，给出分诊、字段提取、风险提示、证据链、回单草稿和技术审计入口。
- Agent 默认不直接保存、结案、转派或覆盖主系统状态；涉及写入的动作必须通过主系统按钮或坐席确认完成。
- 5 天收口内不做完整 Java 工单系统、不强行迁移真实数据库、不接真实生产系统；重点是把前端框架、边界和演示口径打稳。

页面风格：
- 整体视觉贴近银行/客服后台系统，参考原型图的传统企业系统气质：左侧树形菜单、顶部多标签页、浅蓝灰分区标题、高密度表格、细边框、紧凑表单、明确滚动区域。
- 主题色以 `#CD2C42` 和白色为主：`#CD2C42` 用于品牌标识、当前标签、主按钮、关键状态强调和少量焦点线；白色用于主内容背景；浅蓝灰用于分区栏和表头。
- 推荐基础色板：品牌红 `#CD2C42`、页面白 `#FFFFFF`、分区浅蓝 `#EAF6FB`、边框灰 `#D8E0E7`、表头灰 `#F3F5F8`、正文深灰 `#1F2933`。
- 避免大面积渐变、毛玻璃、营销式 hero、圆角大卡片、泛 AI 紫蓝光效和过强动效；页面应该更像坐席每天使用的业务系统，而不是展示型官网。
- 信息密度优先于视觉留白：字号、行高、间距、表格列宽和按钮尺寸都应服务于快速扫单、核验、处理和回单。

页面参考与最终选型：
- G+ 静态页面 demo 放在项目外的 Codex visualization 目录，不属于项目源码：`C:\Users\heyunhui\.codex\visualizations\2026\07\20\019f7da3-b38f-7c30-bdc0-8c1c59ba862a\ticketagent-gplus-demos\`。
- 正式实现优先参考 `demo-1-core-system.html` 的最新版本：传统银行/企业核心系统详情页、左侧细颗粒业务菜单、顶部多标签、主工单详情表单、处理日志、回单区域和技术审计折叠区。
- 左侧菜单不能只做粗粒度“工单处理/信用卡业务/运营管理”，应按真实信用卡二线处理视角细分：受理队列、权益与活动、客户资料、交易与风险、申请与账务、人工协办，并在每组下展示二级队列和数量，例如优惠券补发、餐饮券/满减券、机场贵宾厅权益、地址变更、非本人交易、调单/拒付、申请进度、额度咨询、投诉升级、征信异议、跨部门协办等。
- Agent Copilot 采用最新 demo 的“推入式插件栏”，而不是遮挡表单的悬浮层：展开时主表单整体让出右侧空间，隐藏时主表单恢复全宽，并保留清晰的“Agent Copilot 展开/隐藏”入口。
- Copilot 的交互口径是低耦合插件：读取当前工单上下文，辅助填入回单、定位证据、定位缺失字段、打开技术审计；不得直接保存、结案、转派或覆盖主系统状态。
- 若实现时需要在“推入式右侧插件栏”和“底部中间插件面板”之间取舍，默认采用推入式右侧插件栏；底部中间面板只作为窄屏或空间不足时的降级方案。

开发任务：
- [x] 快速搭建企业工单系统壳：左侧细颗粒菜单树、顶部多标签页、主内容区、推入式 Copilot 插件栏和底部/抽屉式审计区，布局风格参考传统银行客服后台的高密度表单与处理页面。
- [x] 建立 G+ 页面视觉令牌：以 `#CD2C42`、白色、浅蓝灰分区栏、细边框和紧凑表格为基础，统一菜单、标签页、表格、表单、按钮、状态标签和 Copilot 面板的颜色与间距。
- [x] 将工单详情页拆成可演进业务分区：基本信息、客户信息、卡片列表、发单内容、处理日志、回单内容、附件/备注占位、状态与操作区；后续接真实工单系统时优先替换数据源而不是重写页面。
- [x] 把 Agent 助手封装为低耦合 Copilot 组件：优先支持右侧推入式插件栏和隐藏/展开状态，通过 `ticket context -> Agent service -> suggestions/evidence/draft` 的边界与主页面交互；不得遮挡原表单、原系统按钮或回单区域。
- [x] 强化处理日志和操作记录：基于已有 Trace、工具审计和状态流转生成坐席可读日志，展示时间、操作人、动作类型、处理内容、证据编号和下一步责任人。
- [x] 明确生产约束与 HITL：高风险不自动处理、敏感资料变更必须人工确认、工具失败不能包装为成功、缺字段必须追问、回单必须复核、结案必须单独点击。
- [x] 为真实工单系统预留最小接口边界：整理 `TicketContext`、`CopilotSuggestion`、`OperationLog`、`ReplyDraft`、`EvidenceItem` 等前端层概念，避免组件直接依赖 Mock 数据结构。
- [x] 在文档和演示口径中说明低耦合接入路径：真实企业环境可将 Agent 作为侧边栏、iframe、微前端或内嵌组件接入 Java/Spring 或遗留工单系统，通过 REST/SSE 调用 Python Agent 服务。
- [x] 保留当前独立工作台能力作为演示入口或 fallback；企业工单系统壳开发过程中不能破坏已有模块 G 的核心演示链路。

验收标准：
- 首屏观感接近真实银行/客服企业工单详情系统：有细颗粒菜单树、多标签、详情表单、卡片列表、发单内容、处理日志和回单区域，而不是卡片式 AI 展示页。
- 页面主色符合 `#CD2C42` + 白色 + 浅蓝灰分区的银行系统风格，红色克制用于品牌、选中态和关键动作，不形成大面积红色压迫感。
- 坐席能在主页面完成业务动作，Agent 助手只是辅助入口；即使 Copilot 不可用，工单详情和人工处理流程仍可展示。
- Agent Copilot 能读取当前工单上下文并展示建议、证据、风险、缺失字段和回单草稿；展开时主表单应平滑让出空间，隐藏时恢复全宽，不允许遮挡主系统表单、操作按钮或回单区域；写入主页面时必须有明确确认动作。
- 后续接真实工单系统时，优先替换 API/数据适配层即可继续复用页面框架和 Copilot 组件。
- 页面能讲清“体验深度融入、架构低耦合可插拔”：前端像原系统的一部分，Agent 服务边界独立可替换。
- 修改后运行 `cd frontend && npm run build` 通过；若只更新计划文档，则至少检查 Markdown 标题层级和模块顺序正确。

## 模块 H：Page Agent 业务化改造（P1 优先）

目标：把当前已落地的前端页面助手升级为“金融工单场景下的受控页面执行层”。模块 H 的第一优先级不再是语音入口或 Dispatcher Agent，而是围绕 Page Agent 做业务化闭环：让它消费工单业务上下文、执行白名单页面动作、留下动作审计，并且严格服从现有状态机、人工确认和结案接口。

核心判断：
- 当前 Page Agent 已部分实现，主要形态是 `frontend/src/components/ai/PageAssistantPanel.vue`，并已挂载在 `frontend/src/views/TicketDetailView.vue`。
- 它目前没有纳入后端 Orchestrator 主编排；后端主链路仍是 `ClassifierAgent -> IntakeAgent -> EscalationAgent -> ResolutionAgent -> NotificationAgent`。
- Page Agent 不应被做成第六个后端业务 Agent，也不应在当前阶段变成通用网页机器人。
- 阿里 `page-agent` 能力强，但 TicketAgent 当前不直接二开/嵌入完整工程；采用 A+B 路线：先手搓轻量 Page Assistant，再借鉴其 `PageContext`、动作 DSL、白名单工具、观察-计划-执行-验证循环和动作日志思路。
- TicketAgent 的差异化不在“更会点网页”，而在信用卡工单闭环、状态机、工具审计、证据编号、人工确认、回单通知和可评测指标。

### H1：Page Agent 业务化 MVP（当前第一优先级）

目标：把 Page Agent 从“按钮式页面助手”升级为“受控页面动作编排层”。它只操作当前工单详情页内的低风险页面动作，不直接改变权威业务状态，不绕过 `/confirm-action` 和 `/close`。

开发方案：
- [ ] 梳理 `TicketDetailView.vue` 的页面区域、锚点和当前可执行动作：AI 处理、回单编辑、风险/缺失字段、工具证据、人工确认、结案复核、处理日志。
- [ ] 定义 `PageContext`：`ticket`、`aiResult`、`notification`、`traceSteps`、`toolCalls`、`missingFields`、`riskFlags`、`closureSuggestion`、`currentDraft`、`uiAnchors`、`allowedActions`、`disabledReasons`。
- [ ] 定义受控 `PageAction` DSL：`fill_reply`、`scroll_to`、`focus_panel`、`locate_evidence`、`locate_missing_fields`、`open_tool_audit`、`prepare_human_confirm`、`prepare_close_review`、`start_ai_process`。
- [ ] 新增或抽象 `PageActionRunner`，把每个 `PageAction` 映射为明确的前端函数、现有 API 或页面滚动/聚焦动作；不开放任意 DOM index 点击，不启用任意 JavaScript 执行。
- [ ] 将 `PageAssistantPanel.vue` 从静态按钮面板升级为动作入口：根据 `PageContext.allowedActions` 展示可执行动作，根据 `disabledReasons` 展示不可执行原因。
- [ ] 增加 `PageActionLog`：记录 `action`、`input`、`result`、`duration`、`operatorConfirmRequired`、`relatedEvidenceId`、`createdAt`，并与后端 Agent Trace 区分展示。
- [ ] 对敏感动作做权限门禁：人工确认必须走 `/api/tickets/{ticket_id}/confirm-action`，实际结案必须走 `/api/tickets/{ticket_id}/close`，Page Agent 只能准备页面和填充草稿。
- [ ] 页面状态只来自受控业务上下文，不把完整 DOM、客户敏感信息或任意页面快照直接发送给 LLM。
- [ ] 前端补充验证场景：自动成功待复核、待补充、待人工确认、高风险升级、工具失败、UNKNOWN 升级。

验收标准：
- 坐席能在工单详情页一键填入 AI 回单、定位证据、定位缺失字段、进入人工确认或结案复核区域。
- Page Agent 的动作由 `PageContext` 和 `allowedActions` 控制，不直接改业务状态。
- 页面助手动作日志与后端 Agent Trace 边界清晰，能展示“坐席页面辅助”但不污染工具审计证据链。
- 模块 H 汇报时能讲清：Page Agent 是业务受控执行层，不是通用网页自动化工具。
- 修改前端后运行 `cd frontend && npm run build` 通过；若只改文档，则检查 Markdown 标题层级和模块顺序正确。

### H2：Page Agent 动态表单与半自动填充（H1 稳定后）

目标：在 H1 的受控动作框架上，扩展到更有业务价值的半自动页面填写。所有写入动作采用“预览 -> 人工确认 -> 写入页面”，不直接提交业务结果。

开发方案：
- [ ] 定义可填充字段清单：回单草稿、客户追问话术、人工确认摘要、内部通知摘要、资料变更复核字段、争议交易说明字段。
- [ ] 为每类字段定义来源优先级：确定性后端结果优先，LLM 文案只作为草稿，不覆盖证据编号、失败原因、状态和结案规则。
- [ ] 增加填充预览面板，展示字段来源、置信度、缺失原因和人工确认入口。
- [ ] 支持一键写入页面但不自动提交；提交、确认、结案继续走现有业务按钮和 API。
- [ ] 引入轻量 observe-plan-execute-verify 循环：观察 `PageContext`，生成动作计划，执行白名单动作，验证页面结果并写入 `PageActionLog`。
- [ ] 支持自然语言页面指令的窄域解析，例如“帮我填回单”“定位证据”“看一下为什么不能结案”；解析失败时退回明确按钮。

验收标准：
- 至少覆盖回单、人工确认摘要、缺失信息追问三类半自动填充。
- 每次填充前坐席能预览来源和影响范围。
- 动态填充不绕过状态机、不替代后端 Agent 结论。
- 错误或不可执行场景能给出明确 `disabledReason`，并可降级为人工操作。

### H3：外部遗留系统页面自动化预研（后置 P2）

目标：仅当真实业务系统没有 API、必须通过浏览器页面处理时，才评估阿里 `page-agent` Ext/MCP 或二开方案。该阶段不是模块 H 当前实现主线。

预研方案：
- [ ] 梳理外部系统页面清单、登录方式、权限边界、数据敏感级别、可替代 API 和失败接管方式。
- [ ] 评估阿里 `page-agent` 的二开成本：TypeScript monorepo、LLM 配置、Chrome Extension/MCP、本地 hub、DOM 脱敏、动作白名单、供应链和演示稳定性。
- [ ] 设计 TicketAgent Policy Layer：页面白名单、字段脱敏、动作审批、审计记录、人工接管、失败回滚提示。
- [ ] 仅允许 Page Agent 调用受控工具，不允许任意点击、任意 JS 执行或跨系统提交高风险业务动作。
- [ ] 若进入 PoC，先选一个低风险只读页面做查询/定位，不从资金、资料变更或客户通知类操作开始。

验收标准：
- 能明确回答是否值得引入阿里 `page-agent` 作为底层执行引擎。
- PoC 不接触真实敏感客户数据，不修改生产状态。
- 外部页面动作必须有白名单、脱敏、审计、人工确认和失败接管。

### H4：后置能力队列（降优先级）

这些方向保留，但不抢模块 H 的第一主线。

- [ ] 语音入口 Mock-first：后续作为新的输入渠道验证。MVP 仍建议只做通话文本/预置转写文本导入，文本进入 `tickets.content`，沿用现有 AI 处理、SSE Trace、状态流和回单闭环；真实 ASR、音频上传、API Key 和隐私合规后置。
- [ ] Dispatcher Agent：后续作为派单/队列/SLA 能力验证。当前没有 Dispatcher 仍运行良好，是因为系统是 Orchestrator 控制的确定性业务流水线，`workflow_config` 已承担轻量路由，`EscalationAgent` 已承担安全兜底；Dispatcher 未来只负责“派给谁/哪个队列”，不重新分类、不选择业务工具、不覆盖风险结论。
- [ ] A2A-Lite：保留 Agent Card、能力自描述、依赖关系和展示，不做完整协议。
- [ ] MCP：先定义工具接口边界，后续接 MCP Server。
- [ ] LangGraph：当流程分支、状态恢复、回放调试成为主要痛点时再迁移。

模块 H 总体验收标准：
- Page Agent 业务化成为模块 H 的明确第一优先级。
- 语音入口和 Dispatcher Agent 被明确降为后续能力，不再作为 H1/H2 主线。
- Page Agent 能融入当前坐席工作台和现有业务闭环，但不纳入后端 Orchestrator 主编排。
- 系统能讲清相对阿里 `page-agent` 的产品优势：不是通用页面自动化，而是金融工单场景下的可审计、可确认、可评测的受控页面执行层。

## 阶段节奏

| 阶段 | 主目标 | 产出 |
|------|--------|------|
| 阶段 1 | 稳定后端契约和现有闭环 | API/SSE/状态一致，基本流程可重复跑通 |
| 阶段 2 | 业务化 Agent 编排 | 新 Agent 口径、Trace 标签、workflow_config 雏形 |
| 阶段 3 | 打通 Resolution 执行链 | Mock Tool/API 调用、审计日志、证据编号 |
| 阶段 4 | 完成回单与通知闭环 | 标准回单、内部状态通知、人工复核摘要 |
| 阶段 5 | 构建数据集和评测 | 40 条左右标注样本、Agent 指标、端到端指标 |
| 阶段 6 | 重构坐席业务工作台 | 工作池、案件处理台、证据链审计、坐席操作栏、评测摘要 |
| 阶段 7 | 收口与 Code Review | 回归测试、接口测试、文档更新、稳定快照 |

## 当前验收清单

- [x] 后端服务可启动，核心 API 可访问。
- [x] 前端可构建，可展示工单处理过程。
- [x] Intake/Classifier/Resolution/Notification/Escalation 五类核心 Agent 口径清晰。
- [x] Dispatcher 被明确标记为进阶模块。
- [x] 至少 5 类以上工单场景可演示或可评测。
- [x] Resolution Agent 能调用 Mock Tool/API 并生成证据编号。
- [x] 工具失败、字段缺失、复杂争议能升级人工。
- [x] 至少 40 条标注样本可跑评测。
- [x] Agent 测评能输出准确率、完整率、工具命中率、闭环成功率、耗时节省等指标。
- [ ] Demo 讲解、README、AGENTS.md 与当前 Agent 口径一致。

## 不做或后置

- 暂不把风险分级包装成核心模块。
- 暂不为了改名做无边界重构；模块 B 允许对 5 个旧 Agent 做受控重命名，并保留短期兼容 shim。
- 暂不强依赖真实 ASR。
- 暂不做完整 A2A 协议。
- 暂不做外部遗留系统级 Page Agent 自动操作；只允许先做当前工单详情页内的低风险页面助手。
- 暂不迁移 LangGraph，除非手写编排已明显不可维护。

