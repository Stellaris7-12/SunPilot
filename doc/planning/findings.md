# TicketAgent 当前发现

> 仅保留当前开发和答辩需要的结论。历史调查细节见 `doc/planning/backup/`。

## 架构口径

- 系统主线：通话记录 -> 发单 Agent -> 标准工单 -> 五类业务 Agent -> Mock Tools -> SunPilot/PageAgent -> 人工复核结案。
- 五类业务 Agent 保持为 `ClassifierAgent`、`IntakeAgent`、`ResolutionAgent`、`EscalationAgent`、`NotificationAgent`；不要新增第六个后端业务 Agent。
- 发单/回单业务 Agent 是业务大脑，决定“填什么、怎么处理”；SunPilot/PageAgent 是页面执行层，负责“怎么在页面上可见执行”。
- Mock Tools 是外部业务系统替身，证据编号、工具结果、权限门禁和结案规则不应被 LLM 覆盖。

## 配置与 Key

- 业务 Agent 使用 DeepSeek：`DEEPSEEK_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL`。
- SunPilot/PageAgent 使用阿里云百炼：`ALI_API_KEY`、`PAGE_AGENT_LLM_BASE_URL`、`PAGE_AGENT_LLM_MODEL`。
- [ai-engine/config.py](C:/Users/heyunhui/PyProjects/TicketAgent/ai-engine/config.py) 是统一配置入口；真实 Key 只读系统/进程环境变量，不写入仓库。
- Windows 下配置读取已支持当前进程 -> User/Machine 环境变量兜底；修改系统环境变量后仍需重启后端。

## 数据与工具

- 默认数据库为 MySQL/TDSQL，不再保留 SQLite 运行口径。
- `ticket_agent` 是演示库，`ticket_agent_test` 是 smoke 测试库。
- Mock Tools 大面积升级人工时，优先检查数据库连接、DDL/seed、业务字段命中、`workflow_config.json` 和工具候选列表。
- `ResolutionAgent` 已改为原生 tool calling；工具 schema、候选工具过滤、参数归一化和未知工具兜底是稳定性的关键。

## SunPilot / PageAgent

- PageAgent 采用 Ali page-agent fork 的 ReAct 执行层，经后端 `/api/llm/proxy` 调 Qwen，不向浏览器暴露 Key。
- SunPilot 侧边栏必须从 PageAgent DOM 观察和高亮范围中排除，避免误判和浪费 token。
- 当前 UI 口径：浅色侧栏、底部输入框、右下角模型选择、底部 Key 按钮、右侧贴边隐藏箭头、手动唤起/可接管。
- PageAgent 可见执行用于演示发单、回单、证据定位和复核准备；生产级 PolicyLayer、动作审计持久化和更强风险门禁仍是后续项。

## 答辩口径

- TicketAgent 的差异化不是“通用网页自动点击”，而是信用卡工单场景下的业务受控页面执行层。
- 自动化边界要主动说明：不会直接结案；高风险/缺字段/工具失败停在人工作业区；Mock Tools 只是外部系统替身。
- 演示优先讲清三件事：多 Agent 决策、Mock Tools 证据、SunPilot 可见执行与人工接管。
