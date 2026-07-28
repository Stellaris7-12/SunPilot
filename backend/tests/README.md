# tests — 评测与冒烟测试目录

一组**独立运行的 async 冒烟脚本**（非 pytest 套件）。每个脚本自带 `main()` 并以 `asyncio.run(main())` 运行。脚本分两风格：纯内存 / SQLite + Fake Agent（A/B/C/O/P），以及依赖 MySQL 测试库 `ticket_agent_test`（D/I*/K/M）。

运行单个脚本示例：

```bash
cd backend
uv run python tests/smoke_module_k_workflow_routing.py
```

## 公共工具

| 文件 | 主要功能 |
| --- | --- |
| `evaluator.py` | Module F 指标引擎（单例 `evaluator`）。从 `evaluation_samples.json` 加载标注样本，对 Agent 输出打分（意图准确率、工作流一致性、字段完整度、工具正确性、回复覆盖、人工介入准确率、状态闭环率等）；无 records 时用参考指标兜底。 |
| `mysql_smoke_utils.py` | MySQL 测试库共享工具。`configure_mysql_test_database()` 指向 `ticket_agent_test`，`reset_mysql_test_data()` 清表并重灌种子数据。 |
| `run_module_f.py` | Module F 评测**运行器**（非冒烟，需真实 `LLM_API_KEY`）。跑完整业务 Agent 链后用 `evaluator.compute_records` 出指标，支持 `--limit/--ids/--records/--output`。 |

## 冒烟脚本

| 文件 | 测试目标 |
| --- | --- |
| `smoke_module_a.py` | Orchestrator 端到端主流程（SQLite + 确定性 Fake Agents，不需 LLM）。 |
| `smoke_module_b.py` | 业务 Agent 命名与 workflow config 注入、缺信息分支。 |
| `smoke_module_c.py` | Resolution 执行与工具审计（多意图工具选择、tool_call 落库）。 |
| `smoke_module_d.py` | Notification 与回复闭环（依赖 MySQL），通知五段式结构与结案建议。 |
| `smoke_module_e.py` | 标注评测样本静态校验（样本数、必备键齐全）。 |
| `smoke_module_f.py` | Agent 评测指标计算（喂样本给 `evaluator`）。 |
| `smoke_module_i1_database.py` | MySQL schema / seed / repositories 读写。 |
| `smoke_module_i2_crud.py` | MySQL 工单 CRUD / 状态机 / 操作日志（经 TestClient）。 |
| `smoke_module_i3_mock_tools.py` | MySQL 下 Mock 工具执行与 `enrich_params` 只读补全、证据 ID、幂等重放、身份门禁。 |
| `smoke_module_k_workflow_routing.py` | MySQL 下确定性工作流路由与风险门（Classifier/Escalation + `load_workflow_config`）。 |
| `smoke_module_m_call_intake.py` | 通话记录 → 工单草稿生成接口。 |
| `smoke_module_o_tool_calling.py` | 原生 function calling 与注册表守卫（工具数、schema、参数归一、名称纠偏、缺参拒绝，不需 MySQL）。 |
| `smoke_module_p_architecture_guardrails.py` | 架构护栏（防回退到额外业务 Agent、legacy 名泄漏、越出 SunPilot 白名单）。 |
| `smoke_module_p_agent_contracts.py` | AgentCard 运行时输入/输出契约校验。 |
| `smoke_module_p_workflow_contracts.py` | workflow 配置契约（classifier 输出 enum 与场景一致、页面任务 hints）。 |
