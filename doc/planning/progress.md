# TicketAgent 进度日志

> 当前 active 进度只保留高信号摘要；长篇历史见 `doc/planning/backup/` 与 git 历史。

## 2026-07-21 至 2026-07-22 汇总

### 已完成

- 模块 K：系统默认收口到 MySQL/TDSQL，移除 SQLite 运行口径；I1/I2/I3 smoke 使用 `ticket_agent_test`，演示库与测试库分离。
- Mock Tools：补齐客户、卡、交易、权益、申请等 seed 与查询容错；权益码、交易流水、非数字金额等演示问题已修复。
- 模块 O：`ResolutionAgent` 接入原生 tool calling；工具 schema、候选工具过滤、参数归一化、未知工具兜底和人工边界已收口。
- 模块 M：`frontend/src/page-agent/` 切换为 Ali page-agent fork 的 ReAct 执行层，包含 `PageAgentCore`、`PageController`、DOM 脱水、W3C actions、SimulatorMask、LLM client 与 Vue Panel。
- PageAgent/SunPilot：通过后端 `/api/llm/proxy` 调用阿里云百炼，默认 `ALI_API_KEY + qwen3.7-plus`，Key 不暴露到前端。
- 业务 Agent：继续使用 DeepSeek，默认 `DEEPSEEK_API_KEY + deepseek-chat`。
- 发单链路：通话样本生成标准工单草稿，SunPilot 可见填表、提交并进入工单详情。
- 回单链路：SunPilot 可启动/跟随后端多 Agent，填入回单草稿，定位证据与审计区域，停在人工复核结案节点。
- UI 收口：PageAgent 命名为 SunPilot；侧边栏改浅色；模型选择放入输入框右下角；Key 配置移到底部；右侧隐藏按钮改为贴边小箭头；禁用自动进入页面即执行，改为业务信息到达后等待坐席唤起。
- 识别边界：SunPilot 侧边栏和运行遮罩被排除出 PageAgent DOM 观察与高亮范围；鼠标与识别框改小、改淡。
- 配置收口：`ai-engine/config.py` 增加 `get_env()`，先读当前进程环境变量，Windows 下再读 User/Machine 环境变量；真实 Key 仍不写入代码。
- 文档收口：启动指南改为全项目指南，配置口径改为通过 `config.py` 读取系统环境变量。

### 验证记录

- `.venv\Scripts\python.exe -m compileall ai-engine` 通过。
- `frontend` 下 `npm.cmd run build` 多次通过。
- `smoke_module_i3_mock_tools.py`、`smoke_module_k_workflow_routing.py`、`smoke_module_o_tool_calling.py` 曾通过。
- PageAgent Qwen proxy 直连探针曾返回 200 且包含 tool call。
- 浏览器运行态曾完成：生成发单草稿 -> SunPilot 可见填单提交 -> 新工单详情 -> 多 Agent 处理 -> 回单草稿写入 -> 证据定位。

### 当前边界

- 自动流程不能直接结案，仍需人工复核。
- MVP 暂不实现生产级 PolicyLayer、风险分级拦截、持久化 PageActionLog、真实 ASR、外部遗留系统自动化。
- SunPilot 侧栏里的 Key/模型设置只影响当前后端进程；长期配置仍以系统环境变量为准。

### 下一步

- 模块 N：准备演示脚本和答辩材料。
- 可选增强：PageActionLog 持久化、PolicyLayer、更多高风险门禁、真实 ASR、外部系统自动化样例。
