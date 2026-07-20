# Page Agent 产品定位与差异化改造方案

## 背景

阿里 `page-agent` 已经具备比较强的通用网页 GUI Agent 能力：它可以理解页面 DOM，基于 LLM 选择点击、输入、选择、滚动等动作，并通过 Chrome Extension/MCP 扩展到多页面或外部浏览器控制。

因此，如果只比较“通用网页自动操作能力”，TicketAgent 当前的 Page Agent 不占优势。TicketAgent 当前已经落地的是第一阶段页面助手：`frontend/src/components/ai/PageAssistantPanel.vue`，主要服务当前工单详情页内的低风险坐席动作。

TicketAgent 不应和通用 page-agent 在“谁更会点网页”上硬拼。真正的产品优势应来自垂直金融工单场景：业务闭环、状态机、工具审计、人工确认、证据编号、回单通知和评测指标。

## 当前 Page Agent 状态

当前 Page Agent 没有纳入后端 Agent 编排流程。后端主流程仍是：

```text
ClassifierAgent
  -> IntakeAgent
  -> EscalationAgent
  -> ResolutionAgent
  -> NotificationAgent
```

当前 Page Agent 更准确地说是“前端页面助手”或“坐席动作栏”，主要能力包括：

- 启动 AI 辅助处理或重新生成建议。
- 将 AI 生成的标准回单填入回单编辑器。
- 定位风险、缺失字段、处理结果和工具目录。
- 滚动到回单复核区域。
- 展示建议动作、下一负责人、缺失字段和证据编号。

它不具备以下能力：

- 不做通用 DOM 自动理解。
- 不做 LLM 驱动的页面观察、规划和执行循环。
- 不自动点击外部系统。
- 不绕过人工确认或结案接口。
- 不生成业务证据编号。
- 不替代后端状态机和业务 Agent。

## 与阿里 page-agent 的关系

阿里 page-agent 可以作为通用页面执行引擎参考，但不适合作为 TicketAgent 当前阶段的直接核心依赖。

主要原因：

- TicketAgent 是 FastAPI + Vue 坐席工作台，阿里 page-agent 是 TypeScript monorepo，并包含独立 core、page-controller、ui、extension、mcp 等包。
- 完整引入会带来较大的依赖体量、Node/npm 版本要求、LLM Key 管理、Chrome 权限、MCP/本地 hub、供应链和演示稳定性成本。
- 金融工单涉及客户号、手机号、卡号、交易、资料变更等敏感信息，不能默认把完整 DOM 发送给 LLM。
- TicketAgent 已有状态机、工具审计、证据编号、人工确认和结案接口，不能让通用页面 Agent 成为第二套事实来源。

更适合的关系是：

```text
阿里 page-agent = 通用网页 GUI Agent / 页面操作引擎参考
TicketAgent Page Agent = 金融工单场景下的受控页面执行层
```

## TicketAgent 的产品优势

### 1. 业务闭环优势

TicketAgent 不只是操作页面，而是覆盖信用卡工单处理闭环：

```text
接单
  -> 分类
  -> 字段抽取
  -> 风险与缺失判断
  -> 工具执行
  -> 证据编号
  -> 回单生成
  -> 人工确认/升级
  -> 结案建议
  -> 评测指标
```

阿里 page-agent 可以帮助执行页面动作，但它不天然提供信用卡工单的场景分类、字段标准、业务工具、证据链和回单闭环。

### 2. 金融合规与审计优势

TicketAgent 已经具备更贴近金融工单的安全边界：

- 工单状态机。
- 工具调用审计。
- 证据编号。
- 失败原因。
- 人工确认。
- 高风险升级。
- 结构化通知与回单。
- 结案必须走 `/api/tickets/{ticket_id}/close`。

这些能力决定了系统不是“AI 自动点页面”，而是“AI 在可审计、可解释、可接管的业务流程中辅助坐席处理工单”。

### 3. 垂直领域 Agent 优势

TicketAgent 的核心 Agent 是围绕信用卡工单设计的：

- `IntakeAgent`：抽取客户号、券码、申请编号、交易流水、身份核验状态等字段。
- `ClassifierAgent`：识别权益/优惠券、资料变更、交易争议、申请进度等业务场景。
- `ResolutionAgent`：选择并调用补券、查询交易、查询进度、查询权益等业务工具。
- `EscalationAgent`：处理高风险、缺字段、工具失败、人工确认和 UNKNOWN 场景。
- `NotificationAgent`：生成客户回单、内部通知、复核摘要和结案建议。

通用 page-agent 不会天然理解这些业务规则。

### 4. 可评测优势

TicketAgent 已经有评测样本和指标体系，可以证明 Agent 链路效果：

- 意图准确率。
- 字段完整率。
- 工具命中率。
- 回单要点覆盖率。
- 人工介入判断合理性。
- 状态/预期结果匹配率。
- 平均处理耗时。

这使系统能从“看起来能跑”升级为“有指标支撑的业务系统”。

## 改造方向

### 方向 A：把 Page Agent 做成受控页面执行层

不要追求通用网页自动点击，而应定义金融工单专用动作：

```text
fill_reply
locate_evidence
open_tool_audit
prepare_human_confirm
fill_ticket_form
scroll_to_review
locate_missing_fields
```

这些动作由业务状态和权限控制，而不是由 LLM 任意选择 DOM index。

### 方向 B：让 Page Agent 消费业务上下文

Page Agent 的输入不应是完整 DOM，而应是受控的业务上下文：

```text
ticket
aiResult
missingFields
toolEvidence
notification
allowedActions
disabledReasons
currentStatus
currentDraft
```

这样既减少敏感信息暴露，也能让 Page Agent 更贴合工单处理逻辑。

### 方向 C：接入状态机和权限

Page Agent 的动作必须受状态机约束：

- `pending_human_confirm` 才允许展示人工确认动作。
- `closureSuggestion.canClose=true` 才允许进入结案复核。
- 高风险工单只能定位升级原因，不能填自动结论。
- 工具失败只能定位审计记录和升级建议。
- 信息缺失时优先定位缺失字段和客户追问话术。

Page Agent 只能辅助坐席，不直接改变权威业务状态。

### 方向 D：增加 Page Action 审计

每个页面助手动作都应记录为 `PageActionLog`：

```text
action
input
result
duration
operatorConfirmRequired
relatedEvidenceId
createdAt
```

这样可以展示“AI 不只是点了页面，而是可审计地辅助坐席完成操作”。

### 方向 E：把阿里 page-agent 放到第三阶段

当前不直接集成阿里 page-agent。未来如果要操作外部遗留系统，可以把它作为底层页面执行引擎，但外层必须包一层 TicketAgent 的金融安全策略：

```text
TicketAgent Policy Layer
  -> 页面白名单
  -> 数据脱敏
  -> 动作审批
  -> 审计记录
  -> 失败接管
  -> page-agent 执行
```

## 推荐路线

### A 档：当前阶段

手搓轻量 Page Assistant。

目标：

- 增强当前 `PageAssistantPanel.vue`。
- 定义受控 `PageAction`。
- 增加动作日志。
- 继续只操作当前工单详情页。

适合当前 H3 MVP。

### B 档：下一阶段

借鉴阿里 page-agent 的主要思路，重做局部能力。

目标：

- 增加 `PageContext`。
- 增加 `PageActionRunner`。
- 引入“观察 -> 计划 -> 执行 -> 验证”的轻量循环。
- 支持自然语言页面助手和动态表单填充。
- 保持动作白名单、脱敏和人工确认。

适合 A 稳定后推进。

### C 档：远期阶段

评估直接二开或嵌入阿里 page-agent / PageAgent Ext / MCP。

目标：

- 仅用于无 API 的外部遗留系统页面自动化。
- 必须先解决白名单、脱敏、审计、人工确认、失败接管、Chrome 权限和 LLM Key 管理。

不适合作为当前核心 Demo 依赖。

## 一句话定位

阿里 page-agent 是通用页面操作引擎；TicketAgent 是信用卡工单智能处理系统。TicketAgent 的 Page Agent 不应追求成为更通用的网页机器人，而应成为金融工单场景下的受控页面执行层，把业务 Agent 的结果安全、可审计地转化为坐席页面动作。




---

## 为什么选择Page Agent


**Page-Agent 是最适合的选择。**

结合你的项目计划（模块C中Page Agent三阶段引入策略），以下是四个方案的详细对比和推荐理由。

---

## 四方案核心对比

| 维度 | **Page-Agent（推荐）** | **browser-use** | **Playwright** | **Selenium** |
|------|----------------------|-----------------|----------------|---------------|
| **运行位置** | 浏览器页面内（纯前端）| Python后端服务 | Python后端服务 | Python后端服务 |
| **部署方式** | 一行CDN或NPM安装 | 需部署Python服务 + Playwright | 需部署Python/Node服务 | 需部署Python/Java服务 + WebDriver |
| **是否需要截图/多模态** | ❌ 不需要，基于DOM文本 | 基于截图+DOM | ❌ 不需要（纯自动化框架）| ❌ 不需要 |
| **AI规划能力** | ✅ 内置，自然语言驱动 | ✅ 内置LLM决策 | ❌ 无，需手动编写选择器 | ❌ 无，需手动编写选择器 |
| **与后端Agent集成** | 前端直接调用，无需后端改动 | 需后端Resolution Agent调用 | 需后端封装调用 | 需后端封装调用 |
| **跨标签页能力** | 可选Chrome扩展 | ✅ 支持 | ✅ 支持 | ✅ 支持 |
| **高风险操作安全** | ⚠️ 提示词级约束，非硬性隔离 | 同左 | 代码级精确控制 | 代码级精确控制 |
| **维护成本** | 低（纯前端，与后端解耦）| 中（依赖LLM质量） | 高（选择器需随UI变更维护） | 高（选择器维护+驱动版本兼容） |
| **执行速度** | 快（本地DOM操作）| 较慢（需调用LLM决策） | 快（~290ms/动作） | 较慢（~536ms/动作） |

---

## 为什么 Page-Agent 最合适

### 1. 完美契合你的三阶段策略

你在模块C中明确规划了Page Agent三阶段引入：

> **第一阶段**：前端页面助手，只操作当前工单详情页【模块C】
> **第二阶段**：动态表单自动填充【模块C】
> **第三阶段**：外部遗留系统自动化【模块C】

Page-Agent 正是为此而生——它是一个**纯前端JavaScript库**，直接运行在页面内。你可以在 `TicketDetailView.vue` 中直接引入：

```javascript
import { PageAgent } from 'page-agent'
const agent = new PageAgent({
  model: 'qwen3.5-plus',  // 或你后端的LLM
  baseURL: 'YOUR_API_ENDPOINT',
  apiKey: 'YOUR_API_KEY',
})
await agent.execute('把回单草稿填入回单框')
```

完全不需要改动后端，与现有Resolution Agent解耦。

### 2. 技术原理与你的工单场景天然匹配

Page-Agent 的核心是 **“DOM脱水”** ——将实时DOM结构压缩为轻量化的纯文本映射。这意味着：

- **无需截图，无需多模态LLM**，直接用文本模型即可理解页面
- **天然继承用户的Cookie和会话信息**，免去繁琐的身份验证
- **支持任意兼容OpenAI接口的LLM**，你可以复用现有的Qwen模型

这对于工单详情页的操作（填入回单、检查字段、滚动定位）来说，是最轻量高效的方案。

### 3. browser-use 的局限：太重，不适合前端嵌入

browser-use 虽然功能强大，但它是 **Python后端服务**，需要部署Playwright环境。它的核心机制是：解析DOM→给可交互元素编号→LLM决策操作哪个编号。

这意味着：
- 你的Resolution Agent需要通过网络调用browser-use服务
- 每次操作都需要后端往返，增加延迟
- 对于“当前工单详情页内的页面助手”这个场景，属于**过度设计**

### 4. Playwright/Selenium 的问题：没有AI规划能力

Playwright和Selenium是**纯自动化框架**，不是AI Agent。它们需要你**精确写出CSS选择器和每一步操作**，页面一改版就要改代码。

你的目标是让AI**自然语言驱动**页面操作，而不是手工维护脆弱的自动化脚本。

---

## 集成建议

结合你的项目计划，推荐这样落地：

```text
前端 TicketDetailView.vue
    ↓ 引入 page-agent
    ↓ 用户点击"页面助手"
PageAgent.execute("把AI回单草稿填入回单框，检查缺失字段")
    ↓ 调用后端已有LLM（复用Qwen）
    ↓ 操作当前页面DOM
完成填充 + 高亮提示
```

**关键设计**：Page-Agent 执行的操作指令，可以由后端的 Resolution Agent 生成并下发给前端【模块C】。这样：
- 后端Agent负责**决策**（“应该填什么”）
- 前端Page-Agent负责**执行**（“怎么填到页面上”）

职责清晰，符合你现有的多Agent架构。

---

## 注意事项

1. **高风险操作需服务端校验**：Page Agent官方也强调，涉及资金或数据修改的操作，需在服务端保留严格的校验机制。这与你的Escalation Agent设计理念一致。
2. **当前聚焦单页面**：Page Agent目前聚焦单页面交互，正好匹配你第一阶段“只操作当前工单详情页”的需求。跨标签页可通过可选Chrome扩展实现。

---

**结论**：Page-Agent 是“纯前端、轻量、自然语言驱动”的最佳选择，与你已有的多Agent后端架构天然互补，且完美匹配你规划的三阶段引入策略。