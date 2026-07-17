# 发现与决策：新 Agent 方案与开发取舍

## 当前系统事实

- 当前项目是信用卡工单智能处理 Demo，后端为 FastAPI，前端为 Vue 3 + Vite + TypeScript。
- 当前代码已有 5 个技术型 Agent：`IntentAgent`、`ExtractAgent`、`VerifyAgent`、`ToolCallingAgent`、`ReplyAgent`。
- 当前编排不是 LangGraph，而是手写 Orchestrator。
- 当前已有 Tool Registry 和 MockExecutor，可以模拟部分外部业务系统调用。
- 当前前端已有 Trace 和 AI 结果展示，但偏开发者视角，业务表达还不够强。
- 当前文档和演示需要统一到更专业的业务 Agent 命名。

## 新 Agent 分类为什么更适合当前工单场景

用户提出的 Agent 分类更适合答辩和产品表达，因为它从真实工单业务责任出发，而不是从代码实现细节出发。

| 新 Agent | 业务价值 | 答辩表达优势 |
|----------|----------|--------------|
| Intake Agent | 解决多渠道接入、信息提取、缺失信息追问 | 对应工单前台/接单员，业务容易理解 |
| Classifier Agent | 解决工单类型、优先级、处理路径判断 | 对应分诊台，体现规则 + LLM 的专业性 |
| Dispatcher Agent | 解决派给谁、派给哪个团队或 Agent | 对应调度中心，但实现难度较高，适合作为进阶 |
| Resolution Agent | 解决真正业务动作，包括接口调用、Mock Tool、MCP、PageAgent | 是项目亮点，从“会说”升级到“会做” |
| Notification Agent | 解决状态通知、回单、回访 | 对应行政助理，贴近实际工单闭环 |
| Escalation Agent | 解决异常、超时、工具失败、人工兜底 | 对应安全阀，适合金融合规语境 |

旧方案中的“意图识别、字段抽取、工具调用、话术生成”更像技术模块；新方案更像业务组织结构。对答辩、客户和领导来说，新方案更专业，也更容易讲清“系统如何替业务部门分担工作”。

## 是否需要完全重构 Agent 代码

结论：当前项目规模下，不建议长期维护单独映射层；模块 B 改为受控重构。

之前考虑过“旧 Agent + adapter/metadata/trace label 映射”的路线，但用户指出该映射层在当前 Demo 阶段偏冗余。复盘后确认：项目还没有外部插件生态、大量历史调用方或稳定第三方集成，直接把代码层统一为业务 Agent 命名，反而能降低认知成本，更利于答辩和后续开发。

新的实施路线：

1. 代码层直接采用业务 Agent 命名。
2. 旧文件只作为短期兼容 shim，避免测试和旧导入立刻断裂。
3. Orchestrator、Trace、SSE、前端流程条和 Agent Card 全部使用新业务 ID。
4. 模块 B/C 稳定后，再评估删除旧 shim。

当前重构建议：

| 旧实现 | 新业务 Agent | 兼容策略 |
|----------|---------------|----------|
| `ExtractAgent` | `IntakeAgent` | `extract_agent.py` 短期转发到 `intake_agent.py` |
| `IntentAgent` | `ClassifierAgent` | `intent_agent.py` 短期转发到 `classifier_agent.py` |
| `ToolCallingAgent` + `MockExecutor` | `ResolutionAgent` | `tool_agent.py` 短期转发到 `resolution_agent.py` |
| `ReplyAgent` | `NotificationAgent` | `reply_agent.py` 短期转发到 `notification_agent.py` |
| `VerifyAgent` + 状态机 | `EscalationAgent` | `verify_agent.py` 短期转发到 `escalation_agent.py` |
| 暂无 | Dispatcher Agent | 后续根据人员/团队/Agent 能力派单 |

这样做的好处是：代码、Trace 和文档的语言保持一致，减少“旧技术名”和“新业务名”之间的翻译成本；旧 shim 则保留了必要的安全垫，避免一次性破坏模块 A 已稳定的契约和测试。

模块 A 不需要重做。模块 A 的价值是 API、SSE 终态、状态机、持久化和工具审计契约；模块 B 的 Agent 命名重构只要保持这些边界不变，完成后跑回归验证即可。

## 编排策略判断

### 当前不优先引入 LangGraph

原因：
- 现有流程规模还可由手写 Orchestrator 控制。
- Agent 类型和边界仍在调整，过早迁移框架会放大试错成本。
- 当前更急的是接口契约、工具执行、数据集、测评和前端业务呈现。

可接受的中间方案：
- 引入轻量 `workflow_config`。
- 让不同场景配置必填字段、推荐工具、确认策略、通知模板。
- 当流程分支、checkpoint、replay、状态恢复成为痛点后，再迁移 LangGraph。

### A2A-Lite 当前保留轻量价值

保留：
- Agent Card。
- 能力自描述。
- 输入输出 schema。
- Agent 依赖关系。
- 前端能力展示。

后置：
- 完整 A2A 协议。
- 动态发现和热插拔。
- 跨进程 Agent 通信。
- Agent 间复杂协商。

结论：A2A-Lite 可作为架构亮点展示，但不应占用核心开发时间。

## Resolution Agent 的范围

Resolution Agent 是本项目最重要的亮点之一，需要在计划中明确体现。

当前核心：
- 调用 Mock Tool 或后端接口。
- 记录请求、响应、执行状态和证据编号。
- 将执行结果传给 Notification Agent 生成回单。
- 参数缺失或执行失败时交给 Escalation Agent。

进阶扩展：
- MCP：把业务能力包装为标准工具服务。
- Page Agent：分阶段引入。第一阶段只做当前工单详情页的页面助手；第二阶段配合动态表单做发单/回单自动填充；第三阶段才考虑外部遗留系统自动化。
- 知识库：为咨询类工单提供解决方案建议。

## Page Agent 推荐引入路线

Page Agent 有价值，但不能一开始就做成“自动操作外部系统”的高风险能力。更稳的路线是从本系统内部页面开始，逐步扩大权限边界。

### 第一阶段：前端页面助手

在 `frontend/src/views/TicketDetailView.vue` 增加“页面助手”入口，让 Page Agent 只操作当前工单详情页。

建议能力：
- 把 AI 回单草稿填入回单框。
- 检查当前工单风险和缺失字段。
- 打开工具面板并定位补券工具。
- 滚动到审核区域。

这一阶段的价值是低风险、易演示、能贴近用户操作，不依赖真实外部系统。

### 第二阶段：发单/回单表单自动填充

等动态工单表单更完整后，Page Agent 可以把 Intake Agent 或 ExtractAgent 的抽取结果转成页面填充动作，用于自动填写客户信息、业务字段、处理结果和回单内容。

这一阶段适合证明“Agent 不只分析文本，也能减少页面操作和复制粘贴”。

### 第三阶段：外部遗留系统自动化

如果某些行内系统没有 API，才考虑 Page Agent Ext / MCP 方案，让 Agent 操作浏览器页面。

该阶段属于高风险能力，必须具备：
- 系统和页面白名单。
- 敏感字段脱敏。
- 操作前人工确认。
- 操作过程审计。
- 失败回滚或人工接管。

结论：Page Agent 当前可以作为进阶亮点，但近期只建议做第一阶段“页面助手”，不要把外部系统自动点击作为核心交付。

## 场景数量判断

只做 3 类场景不够。3 类适合最小 Demo，但不足以证明系统能覆盖真实工单复杂性。

建议分层：

| 层级 | 用途 | 场景 |
|------|------|------|
| 核心演示 | 必须跑通，适合现场演示 | 权益/优惠券补发、申请进度查询、资料变更、交易/账单查询、活动资格核验 |
| 评测覆盖 | 用于证明泛化和稳定性 | 分期提前结清、还款协商、挂失补卡、额度咨询、年费调整、积分争议 |
| 进阶/兜底 | 用于体现升级和人工协同 | 盗刷疑似、交易争议、征信异议、商务卡资料变更、投诉、跨部门协办 |

数据集应至少覆盖 10 个以上业务场景，每个核心场景至少 2-3 条样本。

## 当前难点排序

1. 后端和前端契约稳定：字段、状态、SSE、持久化。
2. Agent 业务口径统一：新命名要贯穿文档、Trace、前端、演示。
3. Resolution 执行链：工具/API 调用、证据编号、失败兜底。
4. 数据集构建：通话记录、正确意图、正确工单类型、必填字段、期望工具。
5. Agent 测评：单 Agent 指标和端到端指标。
6. 前端业务呈现：让非技术观众看懂处理过程和效果。
7. Dispatcher、语音、A2A、MCP、PageAgent：作为进阶，不抢主线。

## 产品形态判断

当前最稳产品形态：独立 Web 工作台，模拟可嵌入工单系统的智能处理侧边栏或工作流节点。

汇报口径：
- 当前 Demo：AI 工单处理工作台。
- 近期落地：工单系统内嵌工作流/侧边栏插件。
- 远期演进：接入真实业务接口、MCP、PageAgent、A2A 的跨系统智能处理层。

## 关键取舍

| 问题 | 当前结论 |
|------|----------|
| 是否沿用旧 Agent 代码 | 不长期沿用旧命名；模块 B 受控重构为业务 Agent |
| 是否采用新 Agent 命名 | 采用，产品、文档、Trace、前端和代码层都统一 |
| 风险分级是否作为核心模块 | 否，只作为 Escalation/Classifier/Resolution 的策略细节 |
| Dispatcher 是否现在做 | 暂不做完整实现，作为进阶模块 |
| 是否引入 LangGraph | 暂不引入，先做轻量配置化 |
| 是否做 A2A-Lite | 保留 Agent Card 和展示，不做完整协议 |
| 是否做 Page Agent | 分三阶段推进：先当前工单页助手，再动态表单填充，最后才是外部遗留系统自动化 |
| 是否做真实语音 ASR | 后置，先用通话文本或预置转写 |
| 是否扩展更多工单场景 | 是，数据集和演示都需要超过 3 类 |

## 模块 B 完成后的实现事实

- 代码层已经使用 `ClassifierAgent`、`IntakeAgent`、`EscalationAgent`、`ResolutionAgent`、`NotificationAgent` 五个业务 Agent。
- 旧 Agent 文件短期保留为 shim，只转发到新业务 Agent 类。
- Trace、SSE、Agent Card 和前端流程条均使用新业务 `agentId`。
- `workflow_config.json` 已覆盖优惠券补发、资料修改、交易争议和 UNKNOWN 兜底场景。
- `workflow_config` 加载具备内置 fallback；Classifier 会基于配置回填 `workflow_name` 并归一异常类型。
- Agent 执行异常时，当前 Agent Trace 会落为 `FAILED`，再由 Orchestrator 发出统一失败终态。

## 风险与兜底

| 风险 | 兜底方式 |
|------|----------|
| 大规模改名导致代码不稳 | 受控重构 5 个 Agent，旧文件短期保留兼容 shim，模块 A smoke 回归必须通过 |
| 工具调用不稳定 | 先 Mock Tool/API，真实服务后接 |
| 数据集构建耗时 | 先做 20 条高质量样本，再逐步扩展 |
| 前端过技术化 | 默认展示业务流程，开发 Trace 折叠 |
| 进阶功能分散精力 | Dispatcher、A2A、MCP、PageAgent、语音全部后置 |
| Agent 效果难证明 | 建立标注样本和评测脚本，每轮开发后回归 |


