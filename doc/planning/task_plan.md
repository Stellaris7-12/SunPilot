# 任务计划：多Agent信用卡智能协同作业系统

## 目标
8天内从零构建信用卡回单（工单处理）多Agent智能协同系统：Python FastAPI 后端 + Vue 3/TypeScript 前端，含5个专业Agent、A2A-lite Agent Card架构、SSE流式Trace、三级风险路由（含Human-in-the-Loop）。

## 当前阶段
✅ 全部 10 个阶段完成 — 系统可运行，需配置 LLM API Key

## 各阶段

### 阶段 0：需求分析与技术选型
- [x] 理解项目需求（5份设计文档）
- [x] PageAgent / A2A / 发回单全流程 三个方向分析
- [x] 技术选型决策（FastAPI + SQLite + 自研编排器 + Vue 3/TS）
- [x] 完整实施计划输出至 `完整实施计划.md`
- [x] 5个工程亮点设计（Agent Card / 状态机 / SSE / Tool Registry / PageAgent）
- **状态：** complete

### 阶段 1：Backend Foundation (Module A)
- [x] 创建 `ai-engine/` 目录结构
- [x] 实现 `models/` 全部 7 个 Pydantic 模型文件
- [x] 实现 `config.py` 配置管理（环境变量支持）
- [x] 实现 `database.py` SQLite 建表 + 种子数据加载
- [x] 创建 `data/tickets.json`（3张工单）
- [x] 创建 `data/agent_cards.json`（5张Agent Card）
- [x] 创建 `data/tools.json`（3个工具定义）
- [x] 创建 `requirements.txt`
- [x] 验证：模型可导入，SQLite 表创建成功，3张工单加载
- **状态：** complete
- **对应任务：** #1

### 阶段 2：LLM Client + Base Agent (Module B)
- [x] 实现 `agents/base.py` BaseAgent 抽象类
- [x] OpenAI 兼容异步客户端封装
- [x] `call_llm()` 方法（JSON mode, temperature=0.1, 重试逻辑）
- [x] 验证：模块导入成功
- **状态：** complete
- **对应任务：** #2

### 阶段 3：IntentAgent + ExtractAgent (Module C1)
- [x] 实现 `agents/intent_agent.py` IntentAgent（零样本分类，3意图+UNKNOWN）
- [x] 实现 `agents/extract_agent.py` ExtractAgent（意图感知字段提取）
- [x] 验证：Agent 注册中心加载成功，执行顺序正确
- **状态：** complete
- **对应任务：** #3

### 阶段 4：ToolAgent + VerifyAgent + ReplyAgent + AgentRegistry (Module C2)
- [x] 实现 `agents/tool_agent.py` ToolCallingAgent（交易争议自动skip）
- [x] 实现 `agents/verify_agent.py` VerifyAgent（规则优先+LLM双路径）
- [x] 实现 `agents/reply_agent.py` ReplyAgent（含证据编号）
- [x] 实现 `agents/agent_registry.py` AgentRegistry（拓扑排序执行顺序）
- [x] 验证：5个Agent全部注册，依赖关系正确
- **状态：** complete
- **对应任务：** #4

### 阶段 5：Tool Registry + Mock Executor (Module D)
- [x] 实现 `tools/definitions.py` 工具定义加载
- [x] 实现 `tools/registry.py` ToolRegistry（注册、发现、参数校验、摘要生成）
- [x] 实现 `tools/mock_executor.py` MockExecutor（可配置延迟+证据ID生成）
- [x] 实现 `tools/tool_router.py` FastAPI 路由
- [x] 验证：3个工具注册，参数校验，Mock执行返回正确证据ID
- **状态：** complete
- **对应任务：** #5

### 阶段 6：Orchestrator + State Machine + Trace + SSE (Module E)
- [x] 实现 `orchestrator/state_machine.py` TicketStateMachine（6状态7转移）
- [x] 实现 `orchestrator/orchestrator.py` 核心管线（~280行，5Agent+HITL）
- [x] 实现 `orchestrator/trace.py` TraceCollector（收集+持久化）
- [x] 实现 `orchestrator/sse_bridge.py` SSEBridge（事件生成）
- [x] 三级风险路由逻辑：LOW全自动 / MEDIUM暂停确认 / HIGH直接升级
- [x] HITL 暂停/恢复机制
- [x] 验证：3张工单管线走通，高风险正确升级，低风险完整5Agent流程
- **状态：** complete
- **对应任务：** #6

### 阶段 7：Backend API Layer (Module F)
- [x] 实现 `main.py` FastAPI 入口 + CORS + lifespan
- [x] 全部 12 个 REST 端点 + 2个工具路由 + OpenAPI文档
- [x] SSE 流式端点 `GET /api/tickets/{id}/ai-process-stream`
- [x] 验证：15条路由注册，curl 测试 REST 端点正常
- **状态：** complete
- **对应任务：** #7

### 阶段 8：Frontend Foundation (Module G)
- [x] 使用 Vite 创建 Vue 3 + TypeScript 项目
- [x] 安装 Pinia / Vue Router / Axios
- [x] 编写 `types/index.ts` TypeScript 接口（镜像全部Pydantic模型）
- [x] 编写 `api/index.ts` API 客户端封装（12个端点）
- [x] 编写 `stores/ticket.ts` Pinia store（含SSE EventSource消费）
- [x] 编写 `router/index.ts` 路由配置（2条路由）
- [x] Vite proxy 配置（/api → localhost:8000）
- [x] 验证：`npm run build` 零错误通过
- **状态：** complete
- **对应任务：** #8

### 阶段 9：Frontend Views + Components (Module H)
- [x] 实现 `TicketListView.vue` 工单队列 + 侧边栏
- [x] 实现 `TicketDetailView.vue` 双栏布局详情页
- [x] 实现 `AgentTraceTimeline.vue` SSE 实时 Trace（RUNNING脉冲动画）
- [x] 实现 `AiProcessPanel.vue` 5模块进度卡片
- [x] 实现 `AiResultCard.vue` 意图/字段/工具结果展示
- [x] 实现 `VerifyChecks.vue` 风险校验状态列表
- [x] 实现 `ReplyDraftEditor.vue` 可编辑回单草稿 + 结单按钮
- [x] 实现 `ConfirmDialog.vue` 中风险确认弹窗
- [x] 实现 `ToolRegistryPanel.vue` 工具列表（从API动态加载）
- [x] 实现 `StatusBadge.vue` 可复用状态标签
- [x] 实现 `AppSidebar.vue` / `AppHeader.vue` / `TicketInfo.vue` / `TicketContent.vue`
- [x] 验证：`npm run build` 134模块零错误，CSS scoped隔离
- **状态：** complete
- **对应任务：** #9

### 阶段 10：Evaluation Module + 文档 (Module I)
- [x] 实现 `evaluation/evaluator.py` 评测计算
- [x] 实现评测 API 端点 `/api/evaluation/metrics`
- [x] 管线冒烟测试通过（3张工单，LLM不可用时优雅降级）
- [x] 撰写 `启动与使用指南.md`
- [ ] Demo 录制 / 汇报PPT准备
- **状态：** complete (Demo录制待用户配置API Key后进行)
- **对应任务：** #10

## 关键问题
1. ~~LLM API Key 是否已就绪？（DeepSeek / Qwen）~~ → 用户需自行配置环境变量
2. ~~前端是否有品牌色/设计规范需要遵循？~~ → 使用项目自有设计系统（绿/蓝/琥珀/红色系）
3. ~~PageAgent CDN 是否需要 Day 7 集成还是可裁剪？~~ → 已裁剪，作为后续加分项

## 已做决策
| 决策 | 理由 |
|------|------|
| 纯 FastAPI 后端（无 Spring Boot） | 8天周期，Python AI 生态更适合 Agent 开发 |
| SQLite + JSON 持久化 | 免运维，Schema 设计与 MySQL 一致，演示迁移路径 |
| 自研编排器（≤500行） | 体现设计能力，不引入 LangGraph 学习曲线 |
| 前端全新 Vite + Vue 3 + TS 工程 | 用户要求完整工程化，不沿用旧 demo |
| A2A-lite Agent Card（非完整协议） | 借鉴核心思想，8天内完整接入风险高 |
| 三级风险路由 + HITL | 金融合规要素，核心亮点 |
| SSE 流式 Trace（非 WebSocket） | 单向推送，浏览器原生 EventSource，更简单 |
| 前端 Vite proxy 代理 /api | 避免 CORS 问题，开发体验好 |

## 遇到的错误
| 错误 | 尝试次数 | 解决方案 |
|------|---------|---------|
| database.py 相对导入失败 | 1 | 改为绝对导入 `from config import ...` |
| get_db() 返回连接而非上下文管理器 | 1 | 用 `@asynccontextmanager` 重写 |
| tools.json 中 example 字段为 float | 1 | 改为字符串 `"398.00"` |
| reply_agent.py 中文引号与Python字符串冲突 | 1 | 改用「」书名号替代 |
| 子 Agent 未实际写文件 | 1 | 改为直接 Write，不做 Agent 委托 |
| LLM API Key 未配置（401错误） | 预期 | 用户需配置环境变量，系统优雅降级 |
| SSE 一次性发出所有事件，Agent Trace 卡住 | 1 | asyncio.Queue 实时推送替代事后遍历 |
| Windows CMD Ctrl+C 无法终止 uvicorn | 1 | 信号处理 + SSE Task cancel + taskkill 兜底 |

## 交付物清单

### 后端 (19 个 Python 文件)
| 目录 | 文件数 | 说明 |
|------|--------|------|
| `models/` | 7 | Ticket, AgentCard, TraceStep, ToolDefinition, AiProcessResult, ApiSchemas, Database |
| `agents/` | 7 | BaseAgent + 5 Agent + AgentRegistry |
| `tools/` | 4 | Registry, Definitions, MockExecutor, ToolRouter |
| `orchestrator/` | 4 | StateMachine, Orchestrator, TraceCollector, SSEBridge |
| `evaluation/` | 1 | Evaluator |
| 根目录 | 3 | main.py (15 routes), config.py, requirements.txt |

### 前端 (13 个 Vue SFC + 7 个 TS 文件)
| 目录 | 文件数 | 说明 |
|------|--------|------|
| `views/` | 2 | TicketListView, TicketDetailView |
| `components/layout/` | 2 | AppSidebar, AppHeader |
| `components/ticket/` | 2 | TicketInfo, TicketContent |
| `components/ai/` | 6 | TraceTimeline, ProcessPanel, ResultCard, VerifyChecks, ReplyEditor, ConfirmDialog |
| `components/tools/` | 1 | ToolRegistryPanel |
| `components/shared/` | 1 | StatusBadge |
| `src/` root | 5 | types, api, router, stores, main.ts, styles.css |

### 文档 (7 个 Markdown 文件)
| 文件 | 说明 |
|------|------|
| `项目要求.md` | 原始需求 |
| `场景沟通.md` | 场景沟通记录 |
| `Mentor汇报实施方案.md` | Mentor 审核方案 |
| `业务逻辑.md` | 业务流程设计 |
| `技术选型与方向分析报告.md` | 方向调研与决策 |
| `完整实施计划.md` | 9模块实施计划 |
| `启动与使用指南.md` | 运维使用手册 |

## 备注
- 系统代码已全部就绪，需配置 `LLM_API_KEY` 环境变量后即可端到端运行
- 前端构建验证通过（134模块，零错误），后端15条路由全部注册
- Demo 录制建议等 API Key 配置后按 `启动与使用指南.md` 第八章脚本执行
