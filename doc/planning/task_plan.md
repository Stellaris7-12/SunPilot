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

完成摘要：已稳定 API、SSE 终态、工单状态机、AI 结果持久化和工具审计底座；数据库变更采用兼容迁移，不做破坏性重建。

关键产物：`AiProcessResult` 契约、`pending_info`/`failed` 等状态、`workflow_complete`/`workflow_paused`/`workflow_escalated`/`workflow_failed` 四类 SSE 终态、`ai-engine/evaluation/smoke_module_a.py`。

验收状态：后端启动、Swagger、核心工单流程、前端消费 AI 结果、失败/暂停/升级解释均已通过 smoke 与联调验证。

## 模块 B：Agent 编排与业务化封装（P0）已完成

完成摘要：系统已统一为 `IntakeAgent`、`ClassifierAgent`、`ResolutionAgent`、`NotificationAgent`、`EscalationAgent` 五类业务 Agent；Trace、SSE、前端展示和文档口径保持一致。

关键产物：业务 Agent 文件、兼容 shim、Orchestrator 业务链路、`workflow_config` 轻量场景配置。规则覆盖高频明确场景，LLM 处理口语化和复杂表达；暂不迁移 LangGraph。

遗留事项：
- [ ] 清理旧模块相关内容：移除旧 Agent shim 文件，更新兼容测试、Orchestrator 旧别名和文档口径，确认不再依赖 `IntentAgent`、`ExtractAgent`、`VerifyAgent`、`ToolCallingAgent`、`ReplyAgent`。

## 模块 C：Resolution 执行能力与工具审计（P0）已完成

完成摘要：Resolution 已从“生成建议”升级为“选择工具、执行 Mock Tool/API、记录证据、失败兜底”的业务执行层。

关键产物：5 类 Mock Tool（补券、资料变更、交易查询、权益查询、申请进度）、统一 `ToolResult`、`tool_call_log`、只读工具审计接口、前端证据链展示。

边界：参数缺失回到 Intake 追问；工具失败、结果冲突或权限不足交给 Escalation；MCP 和外部 Page Agent 自动化只预留接口，不进入当前核心闭环。

## 模块 D：Notification 与回单闭环（P0）已完成

完成摘要：系统已生成结构化通知包和客户可读回单，覆盖标准回单、内部通知、复核摘要、结案建议和回访预留。

关键契约：`AiProcessResult` 保留 `replyDraft` 兼容字段并新增 `notification`；LLM 生成内容不能覆盖确定性的状态、证据编号、失败原因或结案规则。

结案边界：自动流程只输出 `closureSuggestion.canClose` 和最终回单建议；实际结案必须由 `/api/tickets/{ticket_id}/close` 完成，并回写 `final_reply` 和 `closed_at`。

## 模块 E：数据集构建与场景扩展（P1）已完成

完成摘要：已从少量 Demo 样本扩展为可评测的小型业务数据集；样本用于效果评测、场景覆盖证明和回归测试，不作为训练数据。

关键产物：`ai-engine/data/evaluation_samples.json` 含 40 条中文模拟标注样本；`ai-engine/data/tickets.json` 继续作为 Demo 种子数据；`ai-engine/evaluation/smoke_module_e.py` 校验样本结构、脱敏、场景覆盖和 Demo/评测分离。

数据边界：CFPB 和 BANKING77 仅作为后续扩展参考；外部/生成数据目录已纳入 `.gitignore`，避免大文件和原始数据进入 Git。当前优先看场景覆盖和标注一致性，不追求粗放扩量。

场景覆盖：优惠券/权益、申请进度、资料变更、交易/账单、活动资格、分期/还款、挂失补卡、额度/年费/积分、交易争议、征信异议、投诉和跨部门协作等。

## 模块 F：Agent 测评与效果指标（P1）测评框架已完成

完成摘要：已建立 Agent 分项指标和端到端指标，让系统能用标注样本和真实 Agent 输出证明效果，而不是只靠演示观感。

关键产物：`ai-engine/evaluation/evaluator.py`、`ai-engine/evaluation/run_module_f.py`、`ai-engine/evaluation/smoke_module_f.py`、`GET /api/evaluation/metrics`。

指标覆盖：Intake 字段抽取/缺失识别，Classifier 意图/类型/优先级，Resolution 工具/参数/执行，Notification 回单要点/合规/可读性，Escalation 异常识别/人工介入，端到端状态匹配、耗时和人工节省。

真实 LLM 过程：已完成 5 条预检、3 轮小样本迭代、12 条扩展回归和 40 条全量评测；最终收口见模块 F+。

## 模块 F+：真实 LLM 全量测评与指标收口（P1）已完成

完成摘要：已完成一轮可追溯的 40 条真实 DeepSeek LLM 全量测评，并通过“全量测评 -> 问题归因 -> 链路修复/评分口径调整 -> 回归验证”闭环收口。

关键产物：初始结果 `ai-engine/evaluation/module_f_full_20260719.json`；最终结果 `ai-engine/evaluation/module_f_full_final3_20260719.json`。

重要修复：UNKNOWN 扩展场景兜底、`pending_human_confirm` 显式建模、状态/人工介入口径区分、敏感资料变更先确认后执行、Resolution 参数规范化、Notification 回单要点改为业务槽位覆盖。

最终指标：`source=agent_run`、`evaluatedSamples=40`、`intentAccuracy=1.0`、`fieldCompleteness=1.0`、`toolCorrectness=1.0`、`workflowConsistency=1.0`、`replyPointCoverage=0.9888`、`humanInterventionAccuracy=1.0`、`closedLoopSuccessRate=1.0`、`avgProcessingMs=6529.6`。

口径提醒：`closedLoopSuccessRate` 当前工程含义是“期望状态匹配率/expected outcome match”，不是实际客户真实结案率；前端和答辩中不得误称为生产闭环率。

## 模块 G：坐席业务工作台重构（P1）已完成

完成摘要：前端已从“AI Demo 展示页”重构为面向一线坐席的信用卡工单处理工作台，首要目标是扫单、分诊、核验、处理、复核、回单和升级，而不是暴露底层 Agent。

关键产物：坐席工作池、案件处理台、场景族/状态筛选、右侧操作栏、业务证据链、缺失字段/人工介入原因、回单草稿、评测摘要、技术审计折叠区。

展示口径：Agent 信息默认以业务动作摘要呈现；`IntakeAgent`、`ClassifierAgent` 等技术名只保留在“技术审计/执行明细”。`closedLoopSuccessRate` 在前端解释为“状态/预期结果匹配率”。

验收状态：自动处理、待补充、待人工确认、待人工复核、升级人工、失败和结案建议均有一等 UI 状态；前端构建已通过。

## 模块 G+：企业工单系统壳与 Agent Copilot 解耦接入（P1）已完成

完成摘要：默认 `/tickets` 和 `/tickets/:id` 已切换为更接近真实银行/客服企业工单系统的前端壳；旧坐席工作台保留在 `/legacy/tickets` 和 `/legacy/tickets/:id`。

关键产物：`frontend/src/views/EnterpriseTicketShellView.vue`、企业壳 wrapper、细颗粒信用卡二级菜单、多标签、详情表单、处理日志、证据链、回单区、底部技术审计折叠区、右侧推入式 Agent Copilot。

视觉口径：银行后台高密度表单风格；主色为品牌红 `#CD2C42`、白色、浅蓝灰分区栏和细边框；避免大面积渐变、泛 AI 紫蓝光效和营销式布局。

接入边界：Copilot 是低耦合插件，只读取当前工单上下文并辅助启动处理、填回单草稿、定位证据/缺失字段、打开技术审计、进入复核或人工确认区域；不得直接保存、结案、转派或覆盖主系统状态。人工确认仍走 `/api/tickets/{ticket_id}/confirm-action`，结案仍走 `/api/tickets/{ticket_id}/close`。

验收状态：工单编号直达、二级菜单过滤、Copilot 展开/隐藏、技术审计、旧版 fallback、SSE 重新生成、回单草稿展示和结案门禁均已联调；`cd frontend && npm.cmd run build`、后端 compileall、模块 D/F smoke 均通过。

注意事项：当前 dev 数据库已被多轮演示/联调改动，部分种子工单处于已结案、已升级或待复核状态；后续录制演示建议补一个受控 Demo 数据重置脚本。

后续待删 fallback：
- [ ] 企业壳稳定后清理旧独立工作台 fallback：评估删除 `/legacy/tickets`、`/legacy/tickets/:id` 及相关旧页面/路由/说明，确认不破坏当前演示入口后再执行。

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

