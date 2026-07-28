# TicketAgent — 信用卡工单多 Agent 处理系统

把一通客服电话的转写文本变成一张标准工单，交由**多 Agent 编排器**分类、抽取、决策、审计，再由 **PageAgent / SunPilot** 在前端辅助填单与回复，**最终仅在人工复核后关单**。

后端基于 FastAPI + SQLAlchemy 2（asyncmy）+ MySQL，前端基于 Vue 3 + Vite + TypeScript。

---

## 处理流水线

```text
通话转写 → 标准工单 → 多 Agent 编排 → Mock 工具审计 → PageAgent/SunPilot 辅助填单回单 → 人工复核 → 关单
```

`process_ticket()` 编排顺序：

```text
加载 → IN_PROGRESS → 高风险短路 → 分类(Classifier) → 意图归一化
     → 接单抽取(Intake) → 字段补全 → 升级风险闸门(Escalation)
     → 可能停机(PENDING_INFO / PENDING_HUMAN_CONFIRM)
     → 解决方案(Resolution) → 工具校验 → Mock 执行 → 二次升级复核
     → 待人工复核(PENDING_HUMAN_REVIEW) 或 升级
```

## 五个业务 Agent

| Agent | 职责 |
| --- | --- |
| `ClassifierAgent` | 分类、场景识别、workflow 选择、优先级 |
| `IntakeAgent` | 字段抽取、缺失信息识别（通话发单是其前置子流程） |
| `ResolutionAgent` | 选择并调用 Mock Tool，生成证据 |
| `EscalationAgent` | 缺字段 / 高风险 / 工具失败 / 人工确认的兜底闸门 |
| `NotificationAgent` | 客户回单、内部通知、复核摘要、结案建议 |

## 核心设计原则

- **配置即单一事实来源**：`backend/src/ticket_agent/data/workflow_config.json` 驱动字段映射、场景与门控，代码不硬编码与之竞争的字段映射。
- **确定性快车道 + LLM 慢车道**：先做确定性抽取，仅当所有必填字段抽全时命中快车道；否则 LLM 兜底只补空缺，绝不覆盖确定性值（状态、证据编号、失败原因、门控、结案规则）。
- **两套独立 LLM 配置**：业务 Agent 用 `LLM_*`（DeepSeek 兼容网关）；PageAgent/SunPilot 用 `PAGE_AGENT_LLM_*`（Ali/Qwen，经后端 `/api/llm/proxy/*` 代理）。
- **不自动关单**：自动流程终态最多停在待人工复核 / 升级；关单只经 `POST /api/tickets/{id}/close`。

## 目录结构

```text
TicketAgent/
├── backend/          # FastAPI 后端引擎：业务 Agent、编排、Mock Tools、MySQL 访问
│   ├── src/ticket_agent/
│   │   ├── agents/        # 5 个业务 Agent + 基类、注册表、兼容 shim
│   │   ├── orchestrator/  # 流水线编排、状态机、SSE 推送、配置加载、轨迹
│   │   ├── tools/         # 工具定义、注册表与校验、Mock 执行器、工具路由
│   │   ├── models/        # 数据契约层：Pydantic 模型、API schema、领域模型
│   │   ├── repositories/  # 数据持久化层：MySQL 连接、仓储 CRUD
│   │   ├── api/           # FastAPI 路由层：LLM 代理等 HTTP 端点
│   │   ├── core/          # 核心基础设施：LLM 客户端管理
│   │   ├── domain/        # 业务领域服务层
│   │   ├── data/          # 配置、种子、样本与演示数据（含 workflow_config.json）
│   │   ├── migrations/    # MySQL schema 与增量迁移 SQL
│   │   ├── config.py      # 应用配置（环境变量 / Windows 注册表）
│   │   └── main.py        # FastAPI 应用入口
│   └── tests/         # 异步冒烟测试脚本
├── frontend/         # Vue 3 + Vite + TypeScript 企业工单壳与 SunPilot
│   └── src/
│       ├── app/          # Vue 入口、根组件、路由
│       ├── pages/        # 工作台、发单、回单页面
│       ├── views/        # 企业壳主实现
│       ├── sunpilot/     # SunPilot 面板、PageTask、页面桥、受控工具
│       ├── domain/       # 工单业务映射与规则
│       ├── stores/       # Pinia 状态
│       └── api/          # 后端 API 封装
├── doc/              # 需求、设计、指南、演示与规划文档
├── scripts/          # 辅助脚本
├── AGENTS.md         # 协作约定（详版）
└── CLAUDE.md         # Claude Code 项目指引
```

## 快速开始

### 前置条件

- Python 3.10–3.12，使用 [`uv`](https://github.com/astral-sh/uv) 管理
- Node.js（前端），Windows 下使用 `npm.cmd`
- MySQL（演示库 `ticket_agent`，测试库 `ticket_agent_test`，二者相互隔离）

### 1. 配置环境变量

复制 `.env.example` 为 `.env` 并填入实际值：

```bash
cp .env.example .env
```

关键配置：`LLM_*`（业务 LLM 网关）、`DATABASE_URL`（MySQL 连接）、`HOST` / `PORT` / `CORS_ORIGINS`。

### 2. 启动后端

```bash
cd backend
uv sync                                                        # 安装/同步依赖 + venv
uv run uvicorn ticket_agent.main:app --reload --port 8000     # 启动 API (dev)
uv run python _generate_diverse_tickets.py                     # 生成 50 条多样化演示数据
```

后端默认监听 `http://localhost:8000`，API 前缀为 `/api`。

### 3. 启动前端

```bash
cd frontend
npm.cmd install
npm.cmd run dev      # vite dev server @ 127.0.0.1:5174
```

前端默认使用 `VITE_API_BASE_URL || http://localhost:8000/api`。

## 主要 API 端点

| 端点 | 说明 |
| --- | --- |
| `GET /api/tickets` | 工单列表 |
| `POST /api/tickets` | 新建工单 |
| `GET /api/tickets/{id}` | 工单详情 |
| `POST /api/tickets/{id}/ai-process` | 触发多 Agent 处理 |
| `GET /api/tickets/{id}/ai-process-stream` | SSE 流式处理进度 |
| `POST /api/tickets/{id}/confirm-action` | 人工确认动作 |
| `POST /api/tickets/{id}/close` | **人工关单（唯一关单入口）** |
| `GET /api/tickets/{id}/trace` | 处理轨迹 |
| `POST /api/call-records/generate-ticket-draft` | 通话记录生成工单草稿 |
| `GET /api/workflow-config` | 读取工作流配置 |
| `GET /api/evaluation/metrics` | 评估指标 |
| `/api/llm/proxy/*` | PageAgent/SunPilot 的 LLM 代理 |

## 常用命令

**后端**（`backend/`）：

```bash
uv sync                                                        # 安装/同步依赖
uv run uvicorn ticket_agent.main:app --reload --port 8000     # 启动 API
uv run python -m compileall src/ticket_agent                   # 快速语法/编译检查
uv run python tests/smoke_module_k_workflow_routing.py         # 运行单个冒烟测试
```

**前端**（`frontend/`）：

```bash
npm.cmd run dev              # 开发服务器
npm.cmd run build            # vue-tsc 类型检查 + vite 构建
npm.cmd run smoke:page-agent # PageAgent 冒烟测试
```

> 测试为独立的异步冒烟脚本（无 pytest 套件），跑在测试库 `ticket_agent_test` 上。

## 关键边界

- 自动流程**不能关单**；`NotificationAgent` 只能给出 `closureSuggestion.canClose` 建议。
- PageAgent 限白名单页面动作：无任意 DOM index 点击、无 JavaScript 执行、无直接保存/关单/转派。
- LLM 不得覆盖确定性状态、证据编号、失败原因、权限门禁或结案规则。
- 所有文本文件必须为 **UTF-8 无 BOM**。
- 修改 `.env`、DB schema、种子数据或增删依赖前需与用户确认。

## 技术栈

- **后端**：FastAPI · SQLAlchemy 2（asyncmy）· MySQL · Pydantic 2 · OpenAI SDK · SSE
- **前端**：Vue 3 · Vite · TypeScript · Vue Router · Pinia · Axios · Zod

## 文档导航

- 后端引擎说明：[backend/README.md](backend/README.md)
- 前端工程说明：[frontend/README.md](frontend/README.md)
- 协作约定（详版）：[AGENTS.md](AGENTS.md)
- Claude Code 指引：[CLAUDE.md](CLAUDE.md)
- 需求 / 设计 / 规划：[doc/](doc/)
