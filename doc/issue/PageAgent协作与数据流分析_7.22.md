# PageAgent 协作机制、数据流与编排问题分析

> 2026-07-22，基于当前实际实现代码

---

## 一、演示视角：如何向领导介绍

### 一句话

"两层 AI：后台五个 Agent 分析工单、调工具、生成回单——业务大脑。前端 PageAgent 自动填表、点按钮、定位证据——执行手。两个大脑通过自然语言消息对话，谁都不需要知道对方是谁。"

### 发单侧完整流程

坐席挂断电话，选中通话记录。对右侧 PageAgent 说"根据这通电话帮我发单"。

```
通话记录文本
  -> 发单Agent(后端) 提取: 客户号=C88123, 姓名=王小明, 场景=优惠券补发
  -> ticketDraft 写入 Pinia Store
  -> bridge.ts watch 检测到 -> pushObservation("发单Agent已生成草稿: 客户姓名=王小明, 客户号=C88123...")
  -> PageAgentCore ReAct 循环下一轮看到此 observation
  -> LLM 观察当前 DOM: 页面有发单按钮[1], 表单区域[2-8]
  -> 自主决策: click发单按钮 -> 逐个 input_text 填入字段 -> scroll 到提交按钮
  -> Panel 每步展示: 思考 -> 执行 -> 完成
  -> SimulatorMask 同步: 鼠标移动 + 高亮 + 点击波纹
  -> 坐席看到表单填好 -> 点击提交 -> 工单创建 -> 跳转详情页
```

### 回单侧完整流程

坐席打开工单详情页，点击"AI处理"按钮。

```
POST /api/tickets/:id/ai-process (SSE)
  -> ClassifierAgent: 识别为优惠券补发 (2.1s)
  -> IntakeAgent: 提取 3/3 字段 (1.8s)
  -> EscalationAgent: 低风险通过 (1.5s)
  -> ResolutionAgent: 选择 coupon.reissue (1.2s)
  -> NotificationAgent: 生成回单草稿 (2.3s)
  -> SSE 推送 trace 到前端 Store

bridge.ts:
  watch(store.traceSteps) -> 每步 pushObservation("ClassifierAgent: 识别中...")
  Panel 实时展示处理进度（不打断 PageAgent）

管道完成:
  AiProcessResult -> Store 更新
  bridge watch 检测 -> pushObservation("回单草稿已生成(186字), 证据=EVID-001, 可结案")

PageAgent 收到 observation:
  LLM 观察 DOM: "回单编辑器空, 操作按钮可用, 证据在下方"
  自主决策: input 填入回单 -> scroll 到证据区 -> highlight 证据 -> stop
  坐席复核 -> 点击结案
```

### 架构图

```
业务大脑（后台 FastAPI）
  Classifier -> Intake -> Escalate -> Resolve -> Execute -> Notify
        |  SSE
        v
  Pinia Store: ticket / aiResult / traceSteps
        |  watch + pushObservation
        v
执行手（前端浏览器）
  PageAgentCore (ReAct: observe -> think -> act)
    Panel(对话面板) + Mask(鼠标动画) + Controller(W3C点击/输入)
         |
    坐席: 点"AI处理" + 点"结案"（其余全自动）

两个大脑之间的语言: 自然语言 observation 文本
```

---

## 二、数据流深度拆解

### 2.1 关键数据结构及其流动

| 结构 | 来源 | 到达 | 转换方式 |
|---|---|---|---|
| `ticketDraft` | 发单Agent (POST /call-records/generate-ticket-draft) | `store.ticketDraftResult` -> bridge -> PageAgent | bridge.ts 的 `describeDraft()`: 结构化字段 -> 自然语言 |
| `TraceStep[]` | 多Agent管道 SSE 实时推送 | `store.traceSteps` -> bridge -> Panel | bridge.ts 的 `describeTrace()`: agent/status/summary/duration -> 一句进度描述 |
| `AiProcessResult` | 多Agent管道最终输出 | `store.aiResult` -> bridge -> PageAgent | bridge.ts 的 `describeAiResult()`: intent/fields/replyDraft/evidence -> 自然语言 |
| `isProcessing` | SSE workflow_start/complete | `store.isProcessing` -> bridge -> PageAgent | 布尔值 -> "开始处理" / "处理结束" |
| `workflowPaused` | SSE workflow_paused | `store.workflowPaused` -> bridge -> PageAgent | 布尔值 -> "需要人工确认，停下" |

### 2.2 bridge.ts 的转换逻辑（当前实现，摘自 bridge.ts:27-56）

每个 watch 回调将结构化数据转为自然语言文本：

- `describeDraft(result)`: "发单Agent已生成工单草稿。客户姓名=王小明；客户号=C88123；场景=优惠券补发；标题=618活动达标未到账；请打开发单表单并填入以上字段。"
- `describeTrace(step)`: "后端Agent进度：Classifier Agent / SUCCESS / 已识别为优惠券补发场景 / 2100ms。"
- `describeAiResult(result, paused)`: "后端多Agent处理完成。场景=优惠券补发；缺失字段=无；证据编号=EVID-001；可结案=是；请填入回单编辑器。回单草稿=尊敬的王小明客户..."

### 2.3 AgentPanel 的自动执行机制（摘自 AgentPanel.vue:199-207）

bridge 触发 observation 后，AgentPanel 根据 kind 自动调度 PageAgent 任务：

| bridge kind | 自动执行的指令 | 触发条件 |
|---|---|---|
| `draft` | "根据刚收到的发单Agent草稿，填入发单表单并提交标准工单。" | store.ticketDraftResult 首次更新 |
| `ai_result` | "根据刚收到的后端AI处理结果，填入回单编辑器，定位证据链，并滚动到复核区。" | store.aiResult 首次更新 |
| `paused` | "根据刚收到的高风险或人工确认信息，定位风险原因和人工确认区域，然后停止等待坐席处理。" | store.workflowPaused 变为 true |
| `trace` | 不自动执行 | 仅在 Panel 中展示进度 |

自动执行前检查 `agent.status !== 'running'` 避免打断正在进行的任务。去重通过 `lastAutoSignature` 防止同一 observation 反复触发。

### 2.4 完整时序

```
发单侧:
  坐席选通话 -> store.fetchDraft(sampleId)
  -> POST /api/call-records/generate-ticket-draft
  -> 发单Agent -> ticketDraft -> store.ticketDraftResult 更新
  -> bridge watch -> pushObservation(草稿描述)
  -> AgentPanel 检测 kind='draft' -> scheduleAutoRun("填入发单表单并提交")
  -> 350ms 后 -> agent.execute(task)
  -> PageAgentCore ReAct: observe DOM -> LLM 决策 -> 逐字段填入 -> 定位提交按钮 -> stop

回单侧:
  坐席点"AI处理" -> store.startAiProcess(ticketId)
  -> POST /api/tickets/:id/ai-process (SSE)
  -> Agent1..5 依次执行 -> trace 实时推送 -> store.traceSteps 更新
  -> bridge watch -> pushObservation(进度) -> Panel 展示（不影响 PageAgent）
  -> 管道完成 -> store.aiResult 更新
  -> bridge watch -> pushObservation(完整结果)
  -> AgentPanel 检测 kind='ai_result' -> scheduleAutoRun("填入回单编辑器...")
  -> PageAgentCore ReAct: observe DOM -> LLM 决策 -> 填入回单 -> 定位证据 -> 滚动复核区 -> done
```

---

## 三、当前手写编排的具体问题

### 3.1 process_ticket 的结构问题

`orchestrator.py` 的 `process_ticket()` (267行) 中，执行路径分散在多个位置：

- 行 83-92: 高风险门控 -> return 路径1
- 行 139-150: escalate 后 `_maybe_stop_before_resolution` -> return 路径2-4
- 行 183-184: `_handle_tool_missing_params` -> return 路径5
- 行 190-235: execute + escalate_post, 工具失败 -> return 路径6
- 行 237-264: 正常完成 -> return 路径7

**7条return路径分布在3个方法里，阅读时必须在脑子里拼接。**

### 3.2 "暂停 -> 通知 -> 构建结果 -> 变更状态 -> SSE" 重复5次

`_maybe_stop_before_resolution` 里 3 处 + `_handle_tool_missing_params` 里 1 处 + `process_ticket` 工具失败分支 1 处。每处都是 `notify + build_result + set_status + emit_terminal` 的相同结构，仅参数不同。

### 3.3 上下文传递是松散 dict

每个 Agent 的 input 由 orchestrator 手动拼装 dict，无类型检查。Agent output 格式变更要到运行时 LLM 失败才会发现。AgentCard 中定义的 `input_schema` / `output_schema` 在运行时完全不被校验。

### 3.4 段间通信的"模糊"

当前 bridge 和 AgentPanel 之间的映射是隐式的：

```
bridge 输出 kind='ai_result' -> AgentPanel onMounted 中硬编码映射到 "填入回单编辑器..."
```

这个映射藏在组件初始化代码里，不显眼。新增一个后端事件类型时，需要改 bridge（加 watch）+ AgentPanel（加 scheduleAutoRun 分支）。

---

## 四、关于 LangGraph

### 4.1 LangGraph 能解决什么，不能解决什么

你的架构有三段：

```
段1: 后端 orchestrator.process_ticket()  -- Agent 编排
段2: SSE 传输层                           -- 事件流
段3: 前端 bridge + PageAgent              -- ReAct + 页面操作
```

LangGraph **只影响段1**。段2和段3（SSE 传输、bridge 转换、PageAgent 的 ReAct 循环）与 LangGraph 无关。

### 4.2 当前阶段不建议引入

| 原因 | 说明 |
|---|---|
| 段1是简单DAG | 7个节点、5个分支、0个循环。手写代码量不大，LangGraph 的并行/循环/子图能力都用不上 |
| 你已经在 fork Ali page-agent 上投入了时间 | 再引入 LangGraph 分散精力 |
| 段2/3才是核心差异化 | bridge + observation + PageAgent ReAct 是你架构最独特的部分，LangGraph 帮不了这里 |
| "模糊"主要来自段间通信 | "什么 observation 触发什么 PageAgent 行为"的映射不够显式——这个问题和 LangGraph 无关 |

**什么时候重新考虑**: 当段1出现循环（工具失败后换工具重试）、动态并行（同时拉3个业务系统）、子工作流（场景A和B的子流程不同且超过10个节点）时。这些是700+场景阶段的事。

### 4.3 更紧迫的改进：不换框架，换组织方式

三个改进，总共约150行代码改动，零新依赖：

**改进1: 显式 Pipeline 定义**

```python
# orchestrator/pipeline.py -- 以后看这个文件就知道流程
PIPELINE = [
    Step("classify",   handler=classify,   next="extract"),
    Step("extract",    handler=extract,    next="enrich"),
    Step("enrich",     handler=enrich,     next="escalate_pre"),
    Step("escalate_pre", handler=escalate, routes={
        "needs_more": "notify", "cannot_auto": "notify",
        "human_confirm": "notify", "proceed": "resolve",
    }),
    Step("resolve",    handler=resolve,    routes={
        "skip": "notify", "missing_params": "notify", "proceed": "execute",
    }),
    Step("execute",    handler=execute,    routes={
        "failed": "notify", "success": "notify",
    }),
    Step("notify",     handler=notify,     next=None),
]
```

**改进2: 类型化上下文**

```python
@dataclass
class PipelineContext:
    ticket: Ticket
    intent: IntentResult | None = None
    fields: list[FieldResult] = field(default_factory=list)
    verify: VerifyResult | None = None
    tool_name: str = ""
    tool_params: dict = field(default_factory=dict)
    tool_result: ToolResult | None = None
    reply_draft: str = ""
    notification: dict | None = None
    status: str = ""
    failure_reason: str = ""
```

**改进3: 统一暂停逻辑（消除5处重复）**

```python
async def _pause(self, ctx, *, status, pause_type, failure_reason=""):
    ctx.status = status
    ctx.failure_reason = failure_reason
    ctx = await self._notify(ctx)
    await self._set_ticket_status(ctx.ticket, status)
    await self._emit_terminal(ctx)
    return ctx
```

**改进4: 显式 ActionMap（消除段间通信模糊）**

```typescript
// bridge.ts 中显式定义 observation -> PageAgent 指令的映射
const OBSERVATION_ACTIONS: Record<ObservationKind, string | null> = {
  draft: "根据刚收到的发单Agent草稿，填入发单表单并提交标准工单。",
  ai_result: "根据刚收到的后端AI处理结果，填入回单编辑器，定位证据链，并滚动到复核区。",
  paused: "根据刚收到的高风险或人工确认信息，定位风险原因和人工确认区域，然后停止等待坐席处理。",
  trace: null,
  processing: null,
}
```

---

## 五、结论

| 问题 | 答案 |
|---|---|
| PageAgent 和其他 Agent 如何协作？ | 通过 bridge.ts 的 observation 机制。后端输出 -> Store -> watch -> pushObservation(自然语言) -> PageAgent ReAct 看到 -> 自主执行。两个大脑不直接通信，通过自然语言文本解耦 |
| 数据流清晰吗？ | 主线清晰（Store 是唯一数据汇聚点），但段间映射隐式。可以改用显式 ActionMap 优化 |
| 要不要 LangGraph？ | 当前不建议。段1是简单 DAG，LangGraph 的主要价值用不上。段2/3 才是你架构的核心差异，它们和 LangGraph 无关 |
| 手写编排有什么问题？ | 7条return路径分散、暂停逻辑重复5次、上下文松散dict、段间映射隐式 |
| 怎么办？ | 4个改进（显式Pipeline + 类型化Context + 统一暂停 + 显式ActionMap），约150行代码，零新依赖 |

**优先级: 显式 ActionMap > 统一暂停逻辑 > 显式 Pipeline 定义 > 类型化 Context > 考虑 LangGraph**
