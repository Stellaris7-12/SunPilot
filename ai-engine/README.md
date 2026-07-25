# ai-engine — 信用卡工单多 Agent 后端引擎

TicketAgent 的后端引擎。把一通电话录音转写成的标准工单，交由**多 Agent 编排器**处理，经 Mock 工具审计、PageAgent/SunPilot 辅助填单与回复，最终**仅在人工复核后关单**。基于 FastAPI + SQLAlchemy 2（asyncmy）+ MySQL 构建。

## 处理流水线

```
通话转写 → 标准工单 → 多 Agent 编排 → Mock 工具审计 → 人工复核 → 关单
```

`process_ticket()` 编排顺序：加载 → IN_PROGRESS → 高风险短路 → 分类(Classifier) → 意图归一化 → 接单抽取(Intake) → 字段补全 → 升级风险闸门(Escalation) → 可能停机(PENDING_INFO / PENDING_HUMAN_CONFIRM) → 解决方案(Resolution) → 工具校验 → Mock 执行 → 二次升级复核 → 待人工复核(PENDING_HUMAN_REVIEW) 或升级。

## 核心设计原则

- **配置即单一事实来源**：`data/workflow_config.json` 驱动字段映射、场景与门控，代码不硬编码与之竞争的字段映射。
- **确定性快车道 + LLM 慢车道**：先做确定性抽取，仅当所有必填字段抽全时命中快车道；否则 LLM 兜底只补空缺，绝不覆盖确定性值。
- **两套独立 LLM 配置**：业务 Agent 用 `LLM_*`（DeepSeek 兼容网关）；PageAgent/SunPilot 用 `PAGE_AGENT_LLM_*`（Ali/Qwen，经后端代理）。
- **不自动关单**：自动流程终态最多停在待人工复核 / 升级；关单只经 `POST /api/tickets/{id}/close`。

## 顶层文件

| 文件 | 主要功能 |
| --- | --- |
| `main.py` | FastAPI 应用入口（~1300 行）。暴露工单 CRUD、`/api/tickets/{id}/ai-process[-stream]`（SSE）、通话记录→草稿生成、LLM 代理与配置/指标端点。 |
| `config.py` | 应用配置，从环境变量（含 Windows 注册表）读取：业务 `LLM_*`、`PAGE_AGENT_LLM_*`、数据库、服务器、Agent 默认值等。 |
| `__init__.py` | 包标识。 |

## 目录导航

| 目录 | 说明 |
| --- | --- |
| [agents/](agents/README.md) | 5 个业务 Agent（分类/接单/解决/升级/通知）+ 基类、注册表、兼容 shim。 |
| [orchestrator/](orchestrator/README.md) | 工单流水线编排：编排器、状态机、SSE 推送、配置加载、上下文、轨迹、契约校验。 |
| [models/](models/README.md) | 数据契约层与持久化层：Pydantic 模型、API schema、Agent DTO、MySQL 连接与仓储。 |
| [tools/](tools/README.md) | 工具子系统：工具定义、注册表与校验、Mock 执行器、工具路由。 |
| [evaluation/](evaluation/README.md) | 独立 async 冒烟脚本与评测指标引擎。 |
| [data/](data/README.md) | 配置、种子、样本与演示数据（含核心 `workflow_config.json`）。 |
| [migrations/](migrations/README.md) | MySQL schema 与增量迁移 SQL。 |
| [scripts/](scripts/README.md) | 运维与演示脚本（重置演示数据、Intake 模式对比）。 |
| [static/](static/README.md) | 老式系统/页面样例，演示 PageAgent 的无侵入能力。 |

## 常用命令

```bash
uv sync                                                                    # 安装/同步依赖 + venv
uv run python -m uvicorn main:app --app-dir ai-engine --reload --port 8000 # 启动 API(dev)
uv run python -m compileall ai-engine                                      # 快速语法/编译检查
uv run python ai-engine/evaluation/smoke_module_k_workflow_routing.py      # 运行单个冒烟脚本
```

## 关键边界

- 自动流程**不能关单**；NotificationAgent 只能给 `closureSuggestion.canClose` 建议。
- PageAgent 限白名单页面动作，无任意 DOM 点击、无 JS 执行、无直接保存/关单/转派。
- 所有文本文件为 **UTF-8 无 BOM**。
- 修改 `.env`、DB schema、种子数据或增删依赖前需与用户确认。

> 演示库 `ticket_agent` 与测试库 `ticket_agent_test` 相互隔离。更完整的协作约定见根目录 `CLAUDE.md` 与 `AGENTS.md`。
