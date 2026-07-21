# Agent 编排优化建议（2026.07.21）

## 一、多Agent编排机制梳理（结合代码）

### 1.1 总体架构：中央编排器 + 顺序管道

整个系统采用 **Orchestrator 中心化编排**模式，所有 Agent 之间无法直接通信，全部由 `Orchestrator` 类（`orchestrator/orchestrator.py`）协调调用。核心入口只有一个：`process_ticket()`。

**架构图：**

```text
┌─────────────────────────────────────────────────────────────┐
│                       Orchestrator                          │
│  (模块级单例: orchestrator.py:865)                            │
│                                                             │
│  process_ticket(ticket_id, trace, event_queue)               │
│    │                                                        │
│    ├─ [门控] _load_ticket() → 高风险直接 _handle_high_risk()  │
│    │                                                        │
│    ├─ [步骤1] ClassifierAgent.run()    → intent_result      │
│    ├─ [步骤2] IntakeAgent.run()        → extract_result     │
│    ├─ [步骤3] EscalationAgent.run()    → verify_result      │
│    ├─ [门控] _maybe_stop_before_resolution()                  │
│    │    ├─ needs_more_info      → PENDING_INFO (暂停)        │
│    │    ├─ !can_auto_proceed    → ESCALATED (升级)           │
│    │    └─ risk==medium+未确认  → PENDING_HUMAN_CONFIRM      │
│    │                                                        │
│    ├─ [步骤4] ResolutionAgent.run()  → tool_agent_result    │
│    ├─ [步骤5] MockExecutor.execute() → tool_result          │
│    ├─ [步骤6] EscalationAgent.run()  → verify_result (再次)  │
│    │                                                        │
│    └─ [步骤7] NotificationAgent.run() → reply_result        │
│                                                             │
│  所有异常被 try/except 兜底 → FAILED 状态 + SSE 事件          │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Agent 注册与实例化

Agent 的元数据通过 **JSON Agent Card** 声明式注册（A2A-lite 风格，参照 Google A2A 协议），运行时由 `AgentRegistry` 单例加载：

```python
# agents/agent_registry.py:24-28
class AgentRegistry:
    def __init__(self):
        with open(AGENT_CARDS_JSON, "r", encoding="utf-8") as f:
            cards_data = json.load(f)
        self._cards: dict[str, AgentCard] = {
            c["agent_id"]: AgentCard(**c) for c in cards_data
        }

# 模块级单例，导入时自动加载
agent_registry = AgentRegistry()  # agents/agent_registry.py:76
```

每个 AgentCard 声明了 `agent_id`、`skills`（带 examples）、`input_schema`/`output_schema`（JSON Schema）、`dependencies`（拓扑排序用）、`retry_policy` 等元数据：

```json
// data/agent_cards.json 中 escalation_agent 的声明
{
  "agent_id": "escalation_agent",
  "dependencies": ["classifier_agent", "intake_agent"],
  "retry_policy": "no_retry",
  "max_risk_level": "high",
  "requires_human_review": true,
  ...
}
```

Orchestrator 在 `__init__` 中实例化所有 Agent，每个 Agent 注入自己的 Card：

```python
# orchestrator.py:31-51
def __init__(self):
    self.classifier_agent = ClassifierAgent(
        agent_registry.get("classifier_agent")
        or AgentCard(agent_id="classifier_agent", name="Classifier Agent", description="")
    )
    # ... 其余 4 个 Agent 同理
```

### 1.3 Agent 基类与调用模式

所有 Agent 继承 `BaseAgent`（`agents/base.py`），核心方法是 `call_llm()` + 抽象方法 `run()`。LLM 调用采用 JSON 模式，带一次重试：

```python
# agents/base.py:67-138
async def call_llm(self, system_prompt: str, user_prompt: str) -> dict:
    for attempt in range(2):  # 初始调用 + 1 次重试
        response = await client.chat.completions.create(**payload)
        raw_text = response.choices[0].message.content
        try:
            return json.loads(raw_text)  # 成功则返回
        except json.JSONDecodeError:
            if attempt == 0:
                logger.warning("JSON parse failed — retrying once...")
            else:
                raise  # 第二次失败则抛出
```

每个 Agent 的 `run()` 方法是**无状态纯函数**：接收 `input_data` dict，返回输出 dict。Agent 自身不持有跨请求状态（无状态设计）。

### 1.4 管道中的执行保障

`_run_agent_step()` 对每个 Agent 的执行做了统一包装：SSE 事件推送 → Trace 记录 → 异常捕获 + 重新抛出：

```python
# orchestrator.py:633-692
async def _run_agent_step(self, agent_id, agent_name, agent, input_data, trace, push):
    # 1. 推送 SSE: agent_start + agent_thinking
    await push("agent_start", {...})
    await push("agent_thinking", {...})

    # 2. Trace 记录为 RUNNING
    trace.add_step(agent=agent_name, agent_id=agent_id, status=TraceStatus.RUNNING)

    # 3. 执行
    try:
        result = await agent.run(input_data)
    except Exception as exc:
        # 失败 → trace 标记 FAILED + SSE agent_complete(错误) → 重新抛出
        trace.update_last(summary, f"{elapsed_ms}ms", TraceStatus.FAILED)
        await push("agent_complete", {..., "status": "FAILED"})
        raise  # 由 process_ticket 的最外层 try/except 兜底

    # 4. 成功 → trace 标记 SUCCESS + SSE agent_complete(成功)
    trace.update_last(summary, f"{elapsed_ms}ms", TraceStatus.SUCCESS)
    return result
```

### 1.5 流程门控：三层暂停点

`_maybe_stop_before_resolution()` 实现了三层条件判断：

| 条件 | 触发场景 | 行为 |
|---|---|---|
| `needs_more_info == True` | 必填字段缺失 | 暂停 → PENDING_INFO，生成追问话术 |
| `can_auto_proceed == False` | 未知场景/高风险/身份核验失败 | 升级 → ESCALATED |
| `risk_level == "medium" and not confirmed` | 中风险且未经人工确认 | 暂停 → PENDING_HUMAN_CONFIRM |

```python
# orchestrator.py:299-406
async def _maybe_stop_before_resolution(self, ...):
    if verify_result.get("needs_more_info"):
        # 生成追问通知，状态 = PENDING_INFO，返回 early_result
        ...
    if not verify_result.get("can_auto_proceed", True):
        # 直接升级，状态 = ESCALATED，返回 early_result
        ...
    if risk_level == "medium" and not confirmed:
        # 等待人工确认，状态 = PENDING_HUMAN_CONFIRM，返回 early_result
        ...
    return None  # 都通过，继续管道
```

### 1.6 工具参数缺失的特殊处理

`_handle_tool_missing_params()` 在工具执行前检查参数完整性，利用 IntakeAgent 的 `build_follow_up_prompt()` 生成客户追问话术：

```python
# orchestrator.py:408-481
async def _handle_tool_missing_params(self, ...):
    missing_params = tool_registry.get_missing_required_params(tool_name, tool_params)
    if not missing_params:
        return None  # 参数齐全，继续执行

    follow_up_builder = getattr(self.intake_agent, "build_follow_up_prompt", None)
    if callable(follow_up_builder):
        follow_up = follow_up_builder(missing_params)  # Agent 生成自然语言追问
    # ... 暂停 → PENDING_INFO
```

### 1.7 SSE 实时事件流

`trigger_ai_process_stream` 端点通过 `asyncio.Queue` 实现实时 SSE 推送：

```python
# main.py:226-299
async def trigger_ai_process_stream(ticket_id: str):
    event_queue: asyncio.Queue = asyncio.Queue()
    pipeline_task = asyncio.create_task(
        orchestrator.process_ticket(ticket_id, trace, event_queue)
    )
    # 循环从 queue 取事件 → 格式化 SSE → yield
```

每个 Agent 步骤执行时会推送 `agent_start` → `agent_thinking` → `agent_complete` 三个事件，管道结束推送 `workflow_complete` / `workflow_paused` / `workflow_escalated` / `workflow_failed`。

### 1.8 状态机保护

所有工单状态变更都经过 `TicketStateMachine` 校验：

```python
# orchestrator.py:569-585
async def _set_ticket_status(self, ticket, next_status):
    if not TicketStateMachine.can_transition(current_status, next_status):
        logger.warning("Skipping invalid state transition...")
        return  # 静默跳过非法转换，不抛异常
    # 通过校验 → 写 DB
```

合法状态转换定义在 `_TRANSITIONS` 字典中（`state_machine.py:20-60`），`CLOSED → set()`（终态，无出口）。

### 1.9 5 个 Agent 职责总览

| Agent 类 | ID | 职责 |
|---|---|---|
| **ClassifierAgent** | `classifier_agent` | 工单文本分类到 6 种业务场景，含关键词过滤未接入场景 |
| **IntakeAgent** | `intake_agent` | 根据分类结果从工单内容中抽取结构化字段 |
| **EscalationAgent** | `escalation_agent` | 校验字段完整性 + 风险评估 + 人工确认/升级判断（管道中运行2次） |
| **ResolutionAgent** | `resolution_agent` | 从工具注册表匹配业务工具并生成调用参数 |
| **NotificationAgent** | `notification_agent` | 生成客户回单草稿 + 通知包（含 LLM 失败时的确定性降级） |

---

## 二、编排逻辑的优点

### 2.1 职责清晰，单向依赖

每个 Agent 职责单一且明确：分类 → 提取 → 校验 → 执行 → 通知。与 Google A2A 协议的 "Agent Card + Skill" 理念一致，Agent 之间的依赖关系在 `agent_cards.json` 的 `dependencies` 字段中显式声明，使得执行顺序可推导（`get_execution_order()` 拓扑排序）。

### 2.2 无状态设计，天然可水平扩展

Agent 不持有跨请求状态，每个 `run()` 调用都是纯函数式（input dict → output dict）。这意味着未来可以轻松将 Agent 拆分为独立微服务部署。

### 2.3 防御性编程到位

三层防御保证了系统稳定性：
- **Agent 层**：LLM JSON 解析失败自动重试 1 次
- **管道层**：`_run_agent_step` 中任何异常都通过 trace + SSE 上报后重新抛出
- **最外层**：`process_ticket` 的 `try/except Exception` 确保永远不崩溃，返回 `FAILED` 状态的合法结果

```python
# orchestrator.py:258-267
except Exception as exc:
    logger.exception("[Orchestrator] Workflow failed...")
    result = self._error_result(str(exc), trace, overall_start)
    # 仍会尝试将 ticket 状态设为 FAILED
    await self._emit_terminal(push, ticket_id, result)
    return result  # 优雅降级，不崩溃
```

### 2.4 人机协同设计完整

三层暂停机制（缺信息 / 待确认 / 已升级）配合 `confirm_action` API 端点，形成了完整的人机回路（Human-in-the-loop）。`confirmed` 参数让同一条管道可以处理首次执行和确认后重试两种场景。

### 2.5 SSE 实时可观测性

每个 Agent 的执行都有 `agent_start → thinking → complete` 三阶段 SSE 事件，前端可以实时展示多 Agent 协作的进度条。Trace 持久化到 SQLite 支持事后审计。

### 2.6 状态机保证数据一致性

`TicketStateMachine` 对所有状态变更做白名单校验，非法转换静默跳过且记录 warning 日志，避免了状态污染。这是一个轻量但有效的防护。

### 2.7 NotificationAgent 有确定性降级

唯一有 fallback 的 Agent——LLM 调用失败时走 `_build_fallback()` 生成纯规则驱动的回复，保证系统始终能产出合法输出，不会因为最后一步的 LLM 故障让整个管道结果不可用。

---

## 三、当前编排逻辑的问题

### 3.1 管道硬编码，缺乏可配置性

`process_ticket()` 中的管道顺序是写死的：

```python
# orchestrator.py:95-119 — 顺序是硬编码的
intent_result = await self._run_agent_step("classifier_agent", ...)
extract_result = await self._run_agent_step("intake_agent", ...)
verify_result = await self._run_escalation_step(...)
```

虽然 `agent_cards.json` 定义了 `dependencies` 和 `get_execution_order()` 可以做拓扑排序，但**这个能力完全没有被使用**。管道逻辑和 Agent 元数据是脱节的——改 Agent 依赖需要在两个地方同步修改。

### 3.2 EscalationAgent 承担了过多异构职责

`EscalationAgent.run()` 方法（`escalation_agent.py:56-251`）混合了：
- 确定性规则检查（`_required_fields` 缺字段判断、`MISSING_VALUES` 过滤）
- 硬编码业务逻辑（`TRANSACTION_DISPUTE` 一律升级、`CUSTOMER_ADDRESS_UPDATE` 的 verifyStatus 判断）
- LLM 调用（中风险场景的语义评估）

这导致 Agent 的 `run()` 方法长达 200 行，且规则检查和 LLM 调用混在一起，**测试和调试都困难**。理想情况下，确定性规则应该是独立的校验层，LLM 调用应该是单独的语义判断层。

### 3.3 工具执行结果和 Escalation 判定耦合

在 `process_ticket()` 中，工具执行后的 Escalation 二次判断逻辑分散在 Orchestrator 和 EscalationAgent 两处：

```python
# orchestrator.py:192-227 — 编排器直接判断 tool_result 并构造 failure_reason
if not tool_result.success or not verify_result.get("can_auto_proceed", True):
    failure_reason = (
        verify_result.get("risk_decision")
        or tool_result.failure_reason
        or tool_result.message
        or "工具调用需要人工处理"
    )
```

这违反了"编排器不应关心业务语义"的原则，工具成功/失败的判定逻辑应该完全属于 EscalationAgent 的职责。

### 3.4 上下文传递是松散的字典拼装

Agent 之间的上下文通过手动构造 dict 传递，没有类型安全：

```python
# orchestrator.py:107-116
extract_result = await self._run_agent_step(
    "intake_agent", ...,
    {
        "ticket_content": ticket.content,
        "intent_type": intent_result.get("type", "UNKNOWN"),  # 字符串 key，无类型检查
        "intent_label": intent_result.get("label", "未知"),
        "workflow_config": workflow_config,
    },
)
```

虽然每个 Agent 的 AgentCard 定义了 `input_schema` 和 `output_schema`（JSON Schema），但**这些 Schema 在运行时完全不被校验**。如果上游 Agent 的输出格式变了，下游 Agent 只能在 LLM 调用时出现非确定性错误，调试成本极高。

### 3.5 缺少 Agent 级别的超时和熔断

AgentCard 中定义了 `timeout_seconds: 30`，但 `_run_agent_step()` 中 `agent.run()` 的调用没有 `asyncio.wait_for()` 包裹。如果 LLM 响应极慢（比如模型服务降级），整个管道会一直阻塞。

### 3.6 retry_policy 字段形同虚设

AgentCard 中定义了 `retry_policy`（`no_retry` / `retry_on_error` / `escalate_to_human`），但编排器中完全没有使用这个字段。唯一的重试逻辑在 `BaseAgent.call_llm()` 的 JSON 解析重试，这是 LLM 层面的，不是 Agent 业务层面的重试。

### 3.7 并行能力完全没有利用

当前编排是纯顺序的。但 ClassifierAgent 和 IntakeAgent 之间实际上可以有条件并行——一旦拿到 `intent_type`，IntakeAgent 的字段提取和部分 Escalation 检查（如 `_required_fields` 的确定性校验）可以并行执行。

### 3.8 管道中重复代码严重

`process_ticket()` 中有 5 处几乎相同的"暂停 → 调 NotificationAgent → 调 _build_result → 调 _set_ticket_status → 调 _emit_terminal → return"代码块，分别在：
- `_maybe_stop_before_resolution()` 的 3 个分支（needs_more_info / !can_auto_proceed / medium+unconfirmed）
- `_handle_tool_missing_params()`
- 工具失败后的 escalation 分支（orchestrator.py:192-227）

这些代码块结构高度相似，参数不同但逻辑一致，可以抽象为一个 `_pause_and_notify()` 方法。

### 3.9 Agent 注册表的能力未被编排器利用

`AgentRegistry` 提供了 `get_execution_order()` 拓扑排序和 `list_for_review()` 过滤，但 `Orchestrator` 完全没有使用这些方法。管道顺序是硬编码的，Agent 的 `dependencies` 字段只存在于 JSON 中，对实际执行没有任何约束作用。

---

## 四、优化建议

### 4.1 引入 Pipeline DSL 或配置驱动的管道定义

**针对问题**：3.1 管道硬编码

**建议**：将管道定义为可配置的 DAG（有向无环图），运行时由编排器根据依赖拓扑动态构建执行顺序。

```python
# 概念示例：配置驱动的管道
PIPELINE_DEFINITION = {
    "stages": [
        {"agent": "classifier_agent", "depends_on": []},
        {"agent": "intake_agent", "depends_on": ["classifier_agent"]},
        {"agent": "escalation_agent", "depends_on": ["classifier_agent", "intake_agent"],
         "gate": True},
        {"agent": "resolution_agent", "depends_on": ["escalation_agent"]},
        {"agent": "escalation_agent", "depends_on": ["resolution_agent"],
         "role": "post_tool"},
        {"agent": "notification_agent", "depends_on": ["escalation_agent"]},
    ]
}
```

这样 Agent 的 `dependencies` 字段就和实际执行顺序统一了，不需要两处维护。

### 4.2 拆分 EscalationAgent 为规则引擎 + 语义判断两层

**针对问题**：3.2 EscalationAgent 职责过重

**建议**：

```text
当前: EscalationAgent.run() (200行，混合规则+LLM)
      ↓
优化:
  ├─ FieldCompletenessChecker (确定性规则，纯函数，无 LLM 调用)
  │   - 检查必填字段
  │   - 检查 verifyStatus 等硬编码逻辑
  │   - 返回 {missing_fields, hard_blocks}
  │
  └─ RiskAssessmentAgent (LLM 语义判断)
      - 接收规则引擎的输出 + ticket 上下文
      - 只做语义风险评估
      - 返回 {risk_level, risk_decision, can_auto_proceed}

编排器:
  checker_result = FieldCompletenessChecker.check(...)
  if checker_result.hard_blocks:
      return pause(...)
  risk_result = await RiskAssessmentAgent.run(...)
```

**收益**：(1) 确定性规则可以单元测试，不依赖 LLM；(2) LLM 调用变少（规则能拦住的就不调 LLM）；(3) 缩短了单个 Agent 的执行时间，风险更可控。

### 4.3 引入类型化上下文对象替代松散 dict

**针对问题**：3.4 上下文传递无类型安全

**建议**：定义 `PipelineContext` 数据类，Agent 的 `run()` 方法接收和返回强类型：

```python
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class PipelineContext:
    ticket: Ticket
    intent: Optional[IntentResult] = None
    fields: list[FieldResult] = field(default_factory=list)
    verify_result: Optional[VerifyResult] = None
    tool_request: Optional[ToolRequest] = None
    tool_result: Optional[ToolResult] = None
    workflow_config: dict = field(default_factory=dict)
```

并在 Agent 的输入/输出边界处用 AgentCard 中已有的 `input_schema` / `output_schema` 做 JSON Schema 校验，让 Agent 输出格式变更能被**早期发现**而非在生产环境静默失败。

### 4.4 为 Agent 调用添加超时和熔断

**针对问题**：3.5 缺少超时

**建议**：

```python
async def _run_agent_step(self, agent_id, agent_name, agent, input_data, trace, push):
    timeout = agent.agent_card.timeout_seconds or 60
    try:
        result = await asyncio.wait_for(agent.run(input_data), timeout=timeout)
    except asyncio.TimeoutError:
        # 超时处理：trace 记录 + 按 retry_policy 决定下一步
        ...
```

配合 AgentCard 的 `retry_policy` 实现业务级重试（LLM JSON 重试之外的更高层重试）。同时可考虑引入简单的熔断机制（连续失败 N 次后短暂拒绝该 Agent 的调用）。

### 4.5 抽象暂停-通知模式，消除重复代码

**针对问题**：3.8 重复代码严重

**建议**：`process_ticket()` 中 5 处相似的暂停逻辑可以抽象为：

```python
async def _pause_workflow(
    self, ticket, intent_result, extract_result, verify_result,
    tool_result, tool_params, workflow_config, trace, overall_start, push,
    *, status: str, pause_type: str, failure_reason: str,
    missing_fields: list[str] | None = None,
) -> dict:
    """统一处理管道暂停：通知 + 构建结果 + 状态变更 + SSE 推送"""
    reply = await self._run_notification_step(..., status=status, ...)
    result = self._build_result(..., status=status, ...)
    await self._set_ticket_status(ticket, status)
    await self._emit_terminal(push, ticket.id, result)
    return result
```

### 4.6 利用并行性减少延迟

**针对问题**：3.7 无并行

**建议**：ClassifierAgent 完成后，以下操作可并行：

```python
# 当前（顺序）
extract_result = await intake_agent.run(...)     # 等待
verify_result = await escalation_agent.run(...)  # 再等待

# 优化（并行）
extract_task = asyncio.create_task(intake_agent.run(...))
# 部分 Escalation 检查（确定性部分）也可以并行启动
extract_result, rule_check_result = await asyncio.gather(
    extract_task,
    run_rule_checks(ticket, intent_result, workflow_config)
)
```

对于 5 个 Agent 的管道，即使只有 Classifier → (Intake ∥ RuleCheck) 这一个并行点，也能节省约 20-30% 的端到端延迟。

### 4.7 让 AgentCard 的元数据驱动运行时行为

**针对问题**：3.6 retry_policy 未生效，3.9 注册表能力未利用

**建议**：

1. **retry_policy 生效**：在 `_run_agent_step()` 中根据 AgentCard 的 `retry_policy` 实现差异化处理：
   - `no_retry`：失败直接抛出（当前行为）
   - `retry_on_error`：最多重试 N 次（N 可配置）
   - `escalate_to_human`：失败后不走 `FAILED`，走 `ESCALATED`，生成人工接手通知

2. **管道动态构建**：用 `agent_registry.get_execution_order()` 替代硬编码顺序，当新增 Agent 时只需修改 `agent_cards.json` 和添加 Agent 实现类，不需要改 Orchestrator。

3. **动态 Agent 发现**：Orchestrator 的 `__init__` 可以根据注册表中的 Agent 列表动态实例化，而非逐个硬编码 import。

### 4.8 增加 Agent 间的契约测试

**针对问题**：3.4 Schema 不校验

**建议**：利用 AgentCard 中已有的 `input_schema` / `output_schema`，在 Agent 的输入/输出边界处加一个 `SchemaValidator` 装饰器（开发/测试环境开启，生产环境可选关闭）：

```python
def validate_io(agent_card: AgentCard):
    def decorator(run_fn):
        async def wrapper(input_data):
            # 开发环境校验 input 是否符合 input_schema
            jsonschema.validate(input_data, agent_card.input_schema)
            result = await run_fn(input_data)
            # 校验 output 是否符合 output_schema
            jsonschema.validate(result, agent_card.output_schema)
            return result
        return wrapper
    return decorator
```

这样 Agent 输出格式漂移会在开发阶段被发现，而不是在生产环境的某个下游 Agent 的 LLM 调用中静默失败。

---

## 五、总结

| 维度 | 当前状态 | 评价 |
|---|---|---|
| 编排模式 | 中央编排器 + 硬编码顺序管道 | 简单可靠，但扩展性差 |
| Agent 间通信 | 无直接通信，全部经过编排器 | 职责清晰，但上下文传递松散 |
| 状态管理 | TicketStateMachine + SQLite | 设计良好，状态转换安全 |
| 可观测性 | SSE 实时事件 + Trace 持久化 | 做得很好 |
| 异常处理 | 三层防御（Agent/管道/全局） | 防御充分 |
| 可配置性 | 管道硬编码，AgentCard 元数据未充分利用 | **最大改进空间** |
| 并行性 | 完全没有利用 | 有明显优化空间 |
| 代码重复 | 5 处相似的暂停-通知逻辑 | 可重构消除 |
| 超时与熔断 | AgentCard 定义了 timeout 但未生效 | 需补齐 |
| 类型安全 | dict 传递上下文，无编译/运行时校验 | 生产风险 |

**最核心的改进方向**：让 AgentCard 中的元数据（`dependencies`、`retry_policy`、`timeout_seconds`、`input_schema`/`output_schema`）真正驱动运行时行为，从"硬编码编排"走向"声明式编排"。这样新增 Agent 或调整管道时只需改 JSON 配置而非改 Python 代码，同时获得超时保护、业务级重试、Schema 校验等能力。
