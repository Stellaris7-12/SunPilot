# AGENTS.md - TicketAgent 协作说明

## 项目定位

TicketAgent 是信用卡工单多 Agent 演示系统：

```text
通话记录发单 -> 标准工单 -> 多 Agent 处理 -> Mock Tools 审计 -> PageAgent/SunPilot 辅助填单回单 -> 人工复核结案
```

主要目录：

- `ai-engine/`：FastAPI、业务 Agent、编排、Mock Tools、数据库访问。
- `frontend/`：Vue 3 + Vite + TypeScript 企业工单壳与 SunPilot。
- `doc/`：需求、设计、指南、演示和规划。
- `doc/planning/task_plan.md`：当前唯一 active 计划；历史在 `doc/planning/backup/`。

## 当前优先级

按 `doc/planning/task_plan.md` 执行，不要跳过计划扩散范围：

1. 模块 K：MySQL-only 与 Mock Tools 收口。
2. 模块 M：PageAgent / SunPilot 业务化执行层。
3. 模块 L：通话记录发单侧 MVP。
4. 模块 N：演示与答辩材料。

## Agent 口径

保留五类后端业务 Agent：

- `ClassifierAgent`：分类、场景、workflow、优先级。
- `IntakeAgent`：字段抽取、缺失信息识别；通话发单属于 Intake 前置子流程。
- `ResolutionAgent`：选择并调用 Mock Tool，生成证据。
- `EscalationAgent`：缺字段、高风险、工具失败、人工确认和异常兜底。
- `NotificationAgent`：客户回单、内部通知、复核摘要、结案建议。

旧 `reply_agent.py`、`intent_agent.py` 等只作兼容 shim。不要新增后端第六个业务 Agent；`DispatcherAgent`、真实 ASR、外部网页自动化均后置。

## 核心边界

- 自动流程不能直接结案；结案必须走 `POST /api/tickets/{ticket_id}/close`。
- `NotificationAgent` 只给 `closureSuggestion.canClose` 和最终回单建议。
- LLM 不得覆盖确定性状态、证据编号、失败原因、权限门禁或结案规则。
- PageAgent/SunPilot 是前端受控执行层，只做白名单页面动作：填草稿、定位证据、打开审计、准备人工确认/复核等。
- PageAgent 不允许任意 DOM index 点击、任意 JavaScript 执行、直接保存、结案、转派或覆盖主系统状态。
- Mock Tools 是外部业务系统替身；大面积升级人工时先查 MySQL 连接、DDL、seed、业务字段命中和 `workflow_config.json`。

## 工作规则

- 所有操作默认限制在项目目录内。
- 不修改项目外文件，不修改 `.git/config` 或 Git hooks。
- 不删除源码、文档、配置、数据库或锁文件，除非用户明确确认。
- 修改 `.env`、数据库 schema、初始化数据或安装新依赖前必须确认。
- 不提交、推送或建远程仓库，除非用户明确要求。
- 遵循现有结构和风格，不做无关重构。

## 开发入口

后端：

- 入口：`ai-engine/main.py`
- 编排：`ai-engine/orchestrator/`
- Agent：`ai-engine/agents/`
- 模型与 Repository：`ai-engine/models/`
- Mock Tools：`ai-engine/tools/`、`ai-engine/data/tools.json`
- MySQL DDL：`ai-engine/migrations/mysql/`

前端：

- 企业壳：`frontend/src/views/EnterpriseTicketShellView.vue`
- 旧页面助手：`frontend/src/components/ai/PageAssistantPanel.vue`
- 状态：`frontend/src/stores/ticket.ts`
- API：`frontend/src/api/`
- 业务派生：`frontend/src/utils/business.ts`

## 常用命令

```powershell
uv sync
uv run python -m uvicorn main:app --app-dir ai-engine --reload --port 8000
.venv\Scripts\python.exe -m compileall ai-engine
```

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
npm.cmd run build
```

修改后端至少跑相关 Python 检查或 smoke；修改前端优先跑 `npm.cmd run build`。无法验证时在最终回复说明。

## 输出要求

- 简洁、具体，涉及文件给准确路径。
- 改代码前先说明将改哪些文件。
- 最终回复说明改了什么、验证了什么、还有什么风险。
