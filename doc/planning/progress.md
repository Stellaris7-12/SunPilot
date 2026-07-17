# 进度日志

## 会话：2026-07-17（Page Agent 进阶路线补充）

### 背景

用户希望在计划中补充 Page Agent 的推荐引入方式：不要直接做外部系统自动化，而是分阶段从低风险页面助手开始。

### 执行内容

- 更新 `doc/planning/task_plan.md` 的进阶模块，加入 Page Agent 三阶段路线。
- 更新 `doc/planning/findings.md`，补充 Page Agent 推荐引入路线和安全边界。
- 保持 `doc/planning/任务顺序.md` 不变。

### 当前共识

- 第一阶段：在 `frontend/src/views/TicketDetailView.vue` 增加“页面助手”入口，只操作当前工单详情页。
- 第二阶段：动态工单表单完善后，将 Intake Agent/ExtractAgent 抽取结果转成发单/回单页面填充动作。
- 第三阶段：只有在行内系统没有 API 时，才考虑 Page Agent Ext / MCP 操作外部浏览器页面。
- 外部遗留系统自动化属于高风险能力，必须有白名单、脱敏、审计和人工确认。
## 会话：2026-07-17（planning 文件按新 Agent 方案重构）

### 背景

用户对原 planning 不满意，主要原因：

- 低/中/高风险分级不应作为核心模块强调，它只是业务策略细节。
- 原 Agent 划分偏技术实现，不如 Intake、Classifier、Dispatcher、Resolution、Notification、Escalation 这套业务命名适合工单场景和答辩表达。
- Resolution Agent 中的接口调用、MCP、PageAgent 体现不够明确。
- 只考虑 3 类业务场景不足，需要更多工单场景支撑数据集和测评。
- 本轮只重构 `doc/planning/任务顺序.md` 以外的 planning 文件。

### 执行内容

- 读取 `planning-with-files-zh` 技能说明。
- 读取当前 `doc/planning/task_plan.md`、`doc/planning/findings.md`、`doc/planning/progress.md`、`doc/planning/任务顺序.md`。
- 读取 `doc/design/` 下现有设计文档，确认旧技术型 Agent 口径仍有残留。
- 保留 `doc/planning/任务顺序.md` 不变。
- 重写 `doc/planning/task_plan.md`：改为核心闭环开发路线，采用新业务 Agent 分类。
- 重写 `doc/planning/findings.md`：记录新旧 Agent 方案对比、是否重构、编排取舍、场景扩展和产品形态判断。
- 重写 `doc/planning/progress.md`：记录本次 planning 重构背景、执行内容、当前共识和下一步。

### 当前共识

- 新业务 Agent 主口径：Intake、Classifier、Resolution、Notification、Escalation。
- Dispatcher Agent 难度较高，先作为进阶模块，不进入当前核心闭环。
- 当前代码不需要完全推倒重构，先用映射/adapter/trace label 对齐新业务命名。
- Resolution Agent 必须明确包含 API/Mock Tool 调用和审计证据；MCP 与 PageAgent 是进阶扩展。
- 风险分级不再作为核心模块，只作为分类、执行和升级策略中的细节。
- 工单场景需要扩展到 10 类以上，用于数据集和测评，而不是只围绕 3 个固定 Demo。
- 当前仍优先手写 Orchestrator + 轻量 `workflow_config`，暂不迁移 LangGraph。

### 当前阶段

- **状态：** in_progress
- **阶段名称：** 新 Agent 方案规划收口
- **当前任务：** 将规划文件对齐到业务型 Agent 编排，为后续代码开发提供稳定导航。
- **下一步：** 开始代码开发前，先检查 AGENTS.md、design 文档和前端 Trace 文案是否也需要同步到新 Agent 口径。

## 历史基线摘要

### 2026-07-16 初版系统建设

- 完成 FastAPI 后端、SQLite 数据库、5 个技术型 Agent、Tool Registry、MockExecutor、手写 Orchestrator、SSE Trace、Vue 前端工作台。
- 完成启动指南、规划文件、AGENTS.md、.gitignore。
- 已重新初始化 Git，并完成初始提交：`64535e6 Initial TicketAgent project snapshot`。

### 2026-07-17 文档目录整理

- `doc/` 已整理为 requirements、design、guides、demo、planning 等子目录。
- 新增 `doc/README.md` 作为文档索引。
- Demo 讲解稿已转向面向产品经理、客户和领导的业务表达。
- `doc/guides/vibe-coding指南.md` 已创建，用于通用 AI coding 工作流。

## 已验证能力

| 能力 | 状态 |
|------|------|
| 后端基础服务 | 已完成初版 |
| SQLite 数据库 | 已完成初版 |
| Agent Registry 加载旧 5-Agent | 已完成初版 |
| Tool Registry 和 MockExecutor | 已完成初版 |
| 手写 Orchestrator | 已完成初版 |
| SSE 实时 Trace | 已完成初版，仍需契约稳定 |
| Vue 前端工作台 | 已完成初版 |
| Git 初始提交 | 已完成 |
| 新业务 Agent 规划 | 本轮重构中 |

## 后续进度更新规则

每完成一个模块后更新本文件：

- 写明日期、阶段、完成内容。
- 记录修改的文件。
- 记录运行过的测试，或无法运行的原因。
- 记录遇到的问题和解决方式。
- 如果阶段状态变化，同步更新 `task_plan.md`。
- 如果 Agent 命名、流程顺序或验收标准变化，必须同步更新 `findings.md`。

## 五问重启检查

| 问题 | 当前答案 |
|------|----------|
| 我在哪里？ | 初版系统已完成，正在把 planning 对齐到新的业务型 Agent 方案 |
| 我要去哪里？ | 先跑通接单、分类、执行、通知、升级的核心工单闭环，再做数据集、测评和前端呈现 |
| 目标是什么？ | 做出可演示、可测评、可解释的信用卡工单智能处理系统 |
| 我学到了什么？ | 新 Agent 分类更适合业务表达；旧代码不必推倒，可先映射；Resolution 执行链和测评是核心亮点 |
| 我做了什么？ | 重构 planning 三文件，保留 `任务顺序.md` 不动，将规划从旧技术 Agent 和风险分级主轴迁移到业务型 Agent 编排 |

