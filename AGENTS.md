# AGENTS.md - TicketAgent 项目协作说明

## 项目概览

这是一个信用卡工单多 Agent 处理系统，包含：

- `ai-engine/`：Python FastAPI 后端与多 Agent 编排逻辑
- `frontend/`：Vue + Vite + TypeScript 前端
- `doc/`：项目文档，按需求、设计、指南、演示和规划分组
- `pyproject.toml` / `uv.lock`：Python 项目依赖与锁文件

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

## 常用命令

后端：

```powershell
uv sync
uv run uvicorn ai-engine.main:app --reload
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
