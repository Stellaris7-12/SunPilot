# TicketAgent 核心 Agent 功能与源码梳理

> 2026-07-24，用于答辩准备

---

## 总体架构

```text
SunPilot (TicketAgent 总系统)
│
├── 发单Agent:    通话记录 → 场景识别 + 字段提取 → 工单草稿 + pageHints
├── 回单Agent:    工单 → 5 个 Agent 管道 → 回单 + 证据 + 结案建议
│   ├── ClassifierAgent    判断场景类型
│   ├── IntakeAgent        提取结构化字段
│   ├── EscalationAgent    规则门控（确定性，不调 LLM）
│   ├── ResolutionAgent    选择业务工具
│   └── NotificationAgent  生成回单 + 通知
└── 执行Agent(PageAgent): 页面操作 + 进度展示 + 鼠标动画
```

---

## 一、发单Agent

**职责**：从通话记录生成工单草稿和页面执行提示

**核心逻辑**：
```
输入: 通话记录文本 + workflow_config
处理: LLM 识别场景 → 查 config 获取字段 schema → LLM 提取字段 → 输出草稿
输出: ticketDraft {通用字段 + extJson特有字段} + pageTaskHints
```

**源码位置**：`ai-engine/models/agent_contracts.py` (TicketDraftResult DTO) + Orchestrator 调用 `POST /api/call-records/generate-ticket-draft`

**关键设计**：识别场景后，`extJson` 按场景动态填充——伪冒预防有 `complainantName/caseNo`，市场企划有 `cardName/remark`。同一个 Agent，5 种输出。

---

## 二、ClassifierAgent（场景分类）

**职责**：读工单原文，判断属于哪个 FITS 业务场景

**核心源码**：`ai-engine/agents/classifier_agent.py:64-72`
```python
result = await self.call_llm(CLASSIFIER_SYSTEM_PROMPT, user_prompt)
intent_type = result.get("type") or "UNKNOWN"
if intent_type not in FITS_SCENARIOS:  # 不在合法场景列表中
    intent_type = "UNKNOWN"              # 强制修正
if intent_type not in scenarios:
    intent_type = "UNKNOWN"
```

**设计要点**：
- LLM 自由理解原文语义 → 输出场景名
- 输出必须落在预定义的 FITS_SCENARIOS 集合中，否则强制修正为 UNKNOWN
- 分类前有确定性过滤层：纯咨询类（"如何领取优惠券"）不触发 LLM，直接返回 UNKNOWN

---

## 三、IntakeAgent（字段提取）

**职责**：根据场景类型，从工单原文中提取结构化字段

**核心源码**：`ai-engine/agents/intake_agent.py:95-111`
```python
fields = _fields_from_config(intent_type, workflow_config)  # 从 config 查字段列表
field_descriptions = "\n".join(f"- {name}: {label}" for name, label in fields)

system_prompt = f"""当前工单场景为：{intent_label}。
请从工单内容中抽取以下字段: {field_descriptions}
对于无法抽取的字段，value 设为 "未提供"。只返回 JSON。"""
result = await self.call_llm(system_prompt, user_prompt)
```

**设计要点**：
- 字段列表从 workflow_config 动态获取——不同场景传入不同的字段 schema
- LLM 只看到当前场景的字段（3-10 个），不看其他 690+ 场景的字段
- 输出经过 `coerce_intake_result` 校验

---

## 四、EscalationAgent（规则门控）

**职责**：校验字段完整性 + 风险评估 + 升级判断。**70% 逻辑是确定性规则，不调 LLM。**

**核心源码**：`ai-engine/agents/escalation_guards.py`（三个 Guard 类）

```python
class CompletenessGuard:
    def unsupported_scene(...):    # UNKNOWN 场景 → 升级
    def missing_required(...):     # 必填字段缺失 → 暂停等补充

class RiskGuard:
    def high_risk_ticket(...):     # 高风险工单 → 升级
    def transaction_precheck(...): # 交易争议 → 强制升级
    def failed_identity_check(...):# 身份核验失败 → 升级
    def requires_confirmation(...):# 中风险需要确认 → 暂停

class ToolResultGuard:
    def evaluate(...):             # 工具失败/冲突/需人工 → 升级
```

**设计要点**：
- 所有判断都是 if/else 规则，不调 LLM
- "伪冒预防需要哪些必填字段"从 workflow_config 读取
- 只有极少数模糊场景才调 LLM 做语义级风险评估

---

## 五、ResolutionAgent（工具选择）

**职责**：选择业务工具并构建调用参数

**核心逻辑**：
```
输入: 场景类型 + 提取的字段 + 候选工具列表
处理: 查 _INTENT_TOOL_MAP 或 workflow_config.recommendedTool
      先走确定性映射 → 映射失败再调 LLM
输出: {tool_name, tool_params}
```

**源码位置**：`ai-engine/agents/resolution_agent.py:130-131`
```python
mapped = _INTENT_TOOL_MAP.get(intent_type, [])
recommended = workflow_scenario(workflow_config, intent_type).recommended_tool
```

**设计要点**：
- 1:1 映射优先（config 里有 recommendedTool 就直接用，不调 LLM）
- 候选工具列表由 Orchestrator 预先按场景过滤——LLM 只看到 2-5 个相关工具，不看到全部 22 个
- 输出经过 `coerce_tool_plan` 校验：工具名不在候选列表 → 降级到 recommendedTool

---

## 六、MockExecutor（外部系统适配层）

**职责**：模拟 5 类业务系统调用，生成证据编号

**源码位置**：`ai-engine/tools/mock_executor.py`

**两个关键方法**：

1. `enrich_params()` — **字段自动补全**
   ```python
   # 拿客户号去 mock_customers 查 → 补全姓名/手机/风险等级
   # 拿客户号+活动编码去 mock_benefits 查 → 补全权益信息
   # 补齐了 → 自动填入字段 | 补不齐 → 标记为 unresolvedFields
   ```

2. `execute()` — **工具调用模拟**
   ```python
   # coupon.reissue → 补发优惠券 → 生成 CP... 证据号
   # benefit.query   → 查询权益   → 生成 BEN... 证据号
   # customer.lookup → 查客户资料 → 生成 CUS... 证据号
   ```

**设计要点**：Agent 不知道数据来自 Mock 还是真实系统——它只调 `customer.lookup()`，返回结构化结果。换真实接口只改 executor 层。

---

## 七、NotificationAgent（回单生成）

**职责**：基于全流程结果，生成客户回单和内部通知

**核心源码**：`ai-engine/agents/notification_agent.py:51-108`
```python
async def run(self, input_data):
    result = await self.call_llm(NOTIFICATION_SYSTEM_PROMPT, user_prompt)
    # LLM 失败 → 确定性 fallback
    if not result:
        fallback = self._build_fallback(intent, verify, tool_result, ...)
        return fallback
```

**设计要点**：
- LLM 生成标准回单 + 内部通知 + 结案建议
- LLM 调用失败时走 `_build_fallback()`——用模板生成确定性回复
- 这是唯一一个有确定性降级的 Agent

---

## 八、LLM 输出校验层（coerce 函数）

**职责**：每个 Agent 的输出都经过强制类型校验

**源码位置**：`ai-engine/models/agent_contracts.py:191-227`

```python
def coerce_intent_result(payload):
    return IntentResult(
        type=payload.get("type", "UNKNOWN"),      # 缺 type → UNKNOWN
        confidence=float(payload.get("confidence", 0.0) or 0.0),  # 缺置信度 → 0.0
        ...
    ).model_dump()

def coerce_tool_plan(payload):
    return ToolPlan(
        tool_name=payload.get("tool_name", ""),     # 缺工具名 → 空字符串（后续降级）
        tool_params=payload.get("tool_params", {}) or {},  # 缺参数 → 空 dict
        ...
    ).to_agent_dict()
```

**设计要点**：
- 不赌 LLM 不出错。假设 LLM 可能漏字段、缺类型、输出幻觉。
- 每个 Agent 返回后立即校验 → 缺字段填默认值 → 类型错误强制转换
- 校验失败记入 trace，不阻断流程（降级到 config 默认值或 pending_info）

---

## 九、Orchestrator（编排引擎）

**职责**：按顺序调度 Agent，管理状态流转

**核心设计**：
```python
ctx = PipelineContext(ticket_id, trace, push, ...)  # 类型化上下文

ClassifierInput(...).to_agent_dict() → agent.run() → coerce_intent_result()
IntakeInput(...).to_agent_dict()    → agent.run() → coerce_intake_result()
EscalationInput(...).to_agent_dict() → agent.run() → coerce_risk_decision()
ResolutionInput(...).to_agent_dict() → agent.run() → coerce_tool_plan()
NotificationInput(...).to_agent_dict() → agent.run()

统一出口: _pause() / _escalate() / _finish_review() / _fail()
```

**设计要点**：
- `PipelineContext` dataclass 替代松散 dict
- 每个 Agent 的输入通过 `*Input` DTO 构建，输出通过 `coerce_*` 校验
- 4 个统一出口方法，消除了 7 条分散 return 路径的问题
