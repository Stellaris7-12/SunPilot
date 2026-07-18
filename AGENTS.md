# AGENTS.md - TicketAgent 项目协作说明

## 项目概览

这是一个信用卡工单多 Agent 处理系统，包含：

- `ai-engine/`：Python FastAPI 后端与多 Agent 编排逻辑
- `frontend/`：Vue + Vite + TypeScript 前端
- `doc/`：项目文档，按需求、设计、指南、演示和规划分组
- `pyproject.toml` / `uv.lock`：Python 项目依赖与锁文件

## 当前业务 Agent 口径

项目已经统一采用业务 Agent 命名，文档、Trace、SSE、前端展示和代码实现应尽量保持一致：

- `IntakeAgent`：接单与信息提取，负责抽取工单关键字段和生成缺失信息追问。
- `ClassifierAgent`：分类与优先级判定，负责识别工单类型、业务场景、优先级和工作流配置。
- `ResolutionAgent`：解决方案与执行，负责选择业务工具、调用 Mock Tool/API，并留下审计证据。
- `NotificationAgent`：通知与回单，负责生成客户回单、内部通知、复核摘要、结案建议和回访预留。
- `EscalationAgent`：升级与兜底，负责字段缺失、工具失败、高风险、人工确认和异常场景。

旧 Agent 文件（如 `reply_agent.py`、`intent_agent.py` 等）短期只作为兼容 shim；新增主逻辑优先放到新的业务 Agent 文件中。`DispatcherAgent` 当前作为 P2 进阶能力，不进入核心闭环。

## 当前模块状态

- 模块 A：后端契约与工单状态稳定化，已完成。
- 模块 B：Agent 编排与业务化封装，已完成。
- 模块 C：Resolution 执行能力与工具审计，已完成。
- 模块 D：Notification 与回单闭环，已完成。
- 下一阶段优先看 `doc/planning/task_plan.md` 中的模块 E/F/G，不要跳过 planning 直接扩散开发范围。

模块 D 的关键契约：

- `AiProcessResult` 保留 `replyDraft`/`reply_draft` 兼容字段，同时新增结构化 `notification`。
- `notification` 应包含 `standardReply`、`internalNotice`、`reviewSummary`、`closureSuggestion`、`followUp`。
- 自动流程只能输出 `closureSuggestion.canClose` 和最终回单建议，不应直接把工单置为 `closed`。
- 实际结案必须通过 `/api/tickets/{ticket_id}/close`，并回写 `final_reply` 和 `closed_at`。
- 不允许 LLM 生成内容覆盖确定性的状态、证据编号、失败原因或可结案规则。

## 工作边界

- 所有操作默认限制在当前项目目录内。
- 不要修改项目外部文件。
- 不要删除源码、文档、配置、数据库或锁文件，除非用户明确确认。
- 不要修改 `.git/config`、Git hooks 或用户级配置文件。
- 不要提交、推送或创建远程仓库，除非用户明确要求。

## 目录约定

- 后端代码放在 `ai-engine/`。
- 前端代码放在 `frontend/`。
- 需求与背景资料放在 `doc/requirements/`。
- 业务设计文档放在 `doc/design/`。
- 启动、使用、演示指南放在 `doc/guides/` 或 `doc/demo/`。
- 过程计划、发现和进度记录放在 `doc/planning/`。
- 本地运行产生的数据、缓存、日志不应提交到 Git。

## 后端约定

- 后端使用 Python 3.10+。
- 依赖以 `pyproject.toml` 和 `uv.lock` 为准。
- FastAPI 入口优先检查 `ai-engine/main.py`。
- 修改 Agent 编排逻辑前，先阅读：
  - `ai-engine/orchestrator/`
  - `ai-engine/agents/`
  - `ai-engine/models/`
- 修改通知、结案、回单链路前，先阅读：
  - `ai-engine/agents/notification_agent.py`
  - `ai-engine/models/ai_result.py`
  - `ai-engine/evaluation/smoke_module_d.py`
- 不要随意改动数据库 schema 或初始化数据，除非用户确认。

## 前端约定

- 前端位于 `frontend/`。
- 使用 Vue 3 + Vite + TypeScript。
- 依赖以 `frontend/package.json` 和 `frontend/package-lock.json` 为准。
- 修改 UI 时遵循现有组件结构：
  - `frontend/src/components/`
  - `frontend/src/views/`
  - `frontend/src/stores/`
  - `frontend/src/api/`
- 当前 AI 工单详情页重点组件：
  - `frontend/src/components/ai/NotificationBundlePanel.vue`
  - `frontend/src/components/ai/ReplyDraftEditor.vue`
  - `frontend/src/components/ai/PageAssistantPanel.vue`

## 常用命令

后端：

```powershell
uv sync
uv run uvicorn ai-engine.main:app --reload
```

后端检查与 smoke：

```powershell
.venv\Scripts\python.exe -m compileall ai-engine
.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_a.py
.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_b.py
.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_c.py
.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_d.py
```

前端：

```powershell
cd frontend
npm install
npm run dev
npm run build
```

## 测试与验证

- 修改后端逻辑后，至少运行相关 Python 检查或启动服务验证。
- 修改前端后，优先运行：

```powershell
cd frontend
npm run build
```

- 如果无法运行测试或构建，需要在最终回复中说明原因。

## Git 与忽略规则

- Commit 信息建议采用 Conventional Commits，例如 `feat(module-d): complete notification closure loop`、`docs(agents): update project guidance`。
- `.gitignore` 应忽略：
  - `.venv/`
  - `__pycache__/`
  - `*.pyc`
  - `frontend/node_modules/`
  - `frontend/dist/`
  - `.env`
  - `*.db`
  - 日志和临时文件
- 不要提交本地数据库、虚拟环境、前端依赖目录或构建产物。

## 配置与敏感信息

- 不要提交 `.env` 或真实 API Key。
- 新增配置示例时使用 `.env.example`。
- 修改 `.env`、数据库文件、配置文件前，需要用户确认。

## 输出风格

- 回答尽量简洁、具体。
- 涉及文件时给出准确路径。
- 修改代码前先说明将要改哪些文件。
- 不做无关重构。
