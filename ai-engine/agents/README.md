# agents — 多 Agent 业务智能体目录

信用卡工单处理的多 Agent 核心。**真正的业务 Agent 只有 5 个**（Classifier / Intake / Resolution / Escalation / Notification），全部继承自 `base.py` 的 `BaseAgent`，共享一个模块级 `AsyncOpenAI` 客户端（业务 `LLM_*` 配置），并由 `agent_registry` 从 `data/agent_cards.json` 加载 AgentCard、按依赖拓扑排序供编排器发现调用。

设计贯彻两条原则：**workflow_config 是单一事实来源**（提示词、字段、门控均从配置动态构建）；**确定性快车道优先、LLM 只做补空的慢车道兜底**（LLM 绝不覆盖确定性抽到的真实值）。

`intent/extract/tool/verify/reply_agent.py` 是**兼容 shim**，仅继承对应新 Agent 以保留旧类名，并非第 6 个 Agent。

## 文件说明

| 文件 | 主要功能 |
| --- | --- |
| `base.py` | 抽象基类 `BaseAgent` + 模块级 `AsyncOpenAI` 客户端。封装 `call_llm`（JSON 模式或原生 tool call，解析失败重试一次）、抽象 `run()` 与提示词辅助方法。 |
| `agent_registry.py` | `AgentRegistry` 从 `agent_cards.json` 加载全部 AgentCard，提供按 id 查询、列出需人工复核项、依赖拓扑排序（`get_execution_order`），导出单例 `agent_registry`。 |
| `classifier_agent.py` | **业务 Agent 1 / 分类**。将工单分类到预定义业务场景，确定性命中优先，纯咨询短路为 UNKNOWN，其余走 LLM 并强制回填契约字段防措辞漂移。 |
| `intake_agent.py` | **业务 Agent 2 / 接单抽取**。确定性快车道抽全必填字段即返回，否则走 LLM 慢车道并 `_merge_fields` 只补空缺。含缺字段催单话术 `build_follow_up_prompt`。 |
| `resolution_agent.py` | **业务 Agent 3 / 解决方案**。选择业务工具并构建调用参数，FITS 场景默认确定性回退，LLM 用原生 tool call 选择并配合名称纠错、参数归一、候选集校验。 |
| `escalation_agent.py` | **业务 Agent 4 / 升级**。完整性、风险与人工交接决策。先跑确定性守卫，仅中风险/需确认场景才调 LLM 补充评估，输出 `risk_level`/`can_auto_proceed`/`missing_fields` 等门控字段。 |
| `escalation_guards.py` | EscalationAgent 使用的确定性守卫集合（非 Agent）。含 `CompletenessGuard`、`RiskGuard`、`ToolResultGuard` 三类静态守卫，返回标准化升级判定。 |
| `notification_agent.py` | **业务 Agent 5 / 通知回单**。生成客户回单与内部通知，先构建确定性兜底再调 LLM，`_normalize_result` 强制回填并按状态校正证据号与 `can_close`（只给结案建议，不能自动结案）。 |
| `intent_agent.py` | 兼容 shim：`IntentAgent` 继承 `ClassifierAgent`。 |
| `extract_agent.py` | 兼容 shim：`ExtractAgent` 继承 `IntakeAgent`。 |
| `tool_agent.py` | 兼容 shim：`ToolCallingAgent` 继承 `ResolutionAgent`。 |
| `verify_agent.py` | 兼容 shim：`VerifyAgent` 继承 `EscalationAgent`。 |
| `reply_agent.py` | 兼容 shim：`ReplyAgent` 继承 `NotificationAgent`。 |
