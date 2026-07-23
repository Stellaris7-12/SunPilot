# 答辩前收口计划

> 2026-07-23，feature/sunpilot-agent-architecture

---

## 一、目标

在答辩前让系统具备三个关键差异化展示能力：

1. **工单差异化** — 不同业务类型展示不同的表单结构和字段
2. **发单/回单分离** — 独立的发单工作台和回单处理台，而非万能企业壳
3. **架构完整性** — 补齐当前阻碍 demo 流畅性的缺口

---

## 二、工单差异化改造（4h）

### 2.1 数据来源

基于真实招商银行信用卡工单系统（50 张截图 OCR 提取），系统覆盖 7 大类工单：

| 编号前缀 | 业务类型 | 特有字段 |
|---|---|---|
| 12xxxx | 伪冒预防 | 投诉人信息组（姓名/证件号/手机号）、案件编号、主叫号、CALLID、被投诉内容、主体诉求 |
| 13xxxx | 伪冒调查 | 卡片列表（BLOCK 状态）、备注（卡号段）、管制原因 |
| 29xxxx | 客户经营 | 接单单位（卡部）、汽车分期资料类型 |
| 30xxxx | 市场企划 | 卡片列表、卡片名称、订单号备注、客户反馈、接单单位（市场） |
| 41xxxx | 调单扣款 | CALLID、主叫号、是否消费者本人、投诉人信息、案件编号 |
| 42xxxx | 征信 | 账户类型、是否敏感、逾期状态 |
| 11/71xxxx | 协商还款 | 账户类型、客助标签 |

### 2.2 数据库

tickets 表当前 30 个字段全部平铺，所有类型通用。改造：

```text
tickets（精简，只保留通用字段）:
  id, no(前缀区分), title, customer_id, customer_name, phone, 
  card_last4, scene(一级分类), biz_type(业务类型), biz_sub_type(业务细类),
  priority, risk_level, status, content, deadline(SLA), created_at, updated_at

新增扩展表（按业务类型）:
  ticket_fraud_ext:   call_id, caller_no, is_consumer_self, complainant_name,
                      complainant_id, complainant_phone, case_no, work_order_category,
                      complaint_content, main_demand

  ticket_marketing_ext: card_list(JSON), card_name, remark(订单号),
                        customer_feedback, receive_unit

  (其他类型扩展表按需新增，当前 demo 先做伪冒和市场两类)
```

种子数据：准备独立的 `mock_domain_seed.json`（客户/卡片/交易/权益数据独立于工单，不再是循环论证）。

### 2.3 前端：发单表单改为场景驱动

当前：`EnterpriseTicketShellView.vue` 的发单区是 11 个硬编码字段全展开。

改造：

```html
<!-- 从硬编码改为 v-for 动态渲染 -->
<label v-for="field in commonFields" :key="field.name">
  <span>{{ field.label }}</span>
  <input :data-page-agent-target="`dispatch-${field.name}`" v-model="form[field.name]" />
</label>

<label v-for="field in scenarioFields" :key="field.name">
  <span>{{ field.label }}</span>
  <input :data-page-agent-target="`dispatch-${field.name}`" v-model="form[field.name]" />
</label>
```

`scenarioFields` 从 `workflow_config[scene].specificFields` 取。场景切换（伪冒→市场企划）时表单自动换字段。

### 2.4 ai-engine：发单Agent 扩展

```text
当前: 发单Agent 只提取通用字段
改造: 识别业务类型后，查 workflow_config 获取该类型的特有字段列表，
      在提取 prompt 中追加特有字段，输出包含 scene + 通用字段 + 特有字段

workflow_config 新增:
  "伪冒预防": {
    "specificFields": [
      {"name":"callId","label":"CALLID"},
      {"name":"complainantName","label":"投诉人姓名"},
      ...
    ]
  }
```

---

## 三、发单/回单页面分离（2h）

### 3.1 当前问题

所有功能堆在 `EnterpriseTicketShellView.vue` 一个文件里：发单表单、工单信息、AI 结果、回单编辑器、SunPilot 面板。没有"发单"和"回单"的流程感。

### 3.2 改造方案

```text
拆为两个独立路由:

1. /dispatch — 发单工作台
   ┌─────────────────────────────────────────────┐
   │  左侧: 通话记录列表 + 选中通话的全文展示       │
   │  主区: 发单表单（动态字段，按业务类型切换）     │
   │        + 一键提交按钮                        │
   │                                             │
   │  右上: SunPilot Panel（只保留发单相关快捷指令）│
   │  右下: 草稿操作区（字段来源提示 + 缺失项提示）  │
   └─────────────────────────────────────────────┘

2. /tickets/:id — 回单处理台
   ┌─────────────────────────────────────────────┐
   │  主区: 工单信息 + AI结果 + 回单编辑器 + 证据区 │
   │  右上: SunPilot Panel（保留，不动）           │
   │  右下: 回单复核区（结案按钮）                  │
   └─────────────────────────────────────────────┘

两个页面的 SunPilot Panel 完全相同，只需要分开渲染。
```

### 3.3 具体工作

- 从 `EnterpriseTicketShellView.vue` 拆出发单表单部分 → 新建 `DispatchView.vue`
- 回单部分保留在 `EnterpriseTicketShellView.vue`（或重命名为 `ReplyView.vue`）
- SunPilot Panel 作为独立组件，在两个页面中引用
- 路由: `/dispatch` + `/tickets/:id`

---

## 四、阻碍 demo 流畅性的缺口（2h）

### 4.1 PageTask 协议未与后端打通

```text
问题: pageTaskExecutor.ts（确定性执行器）和 taskBridge.ts（指令构造器）
      已完成，但没有数据源——bridge.ts 只推自然语言 observation，
      不读 PageTaskEnvelope。

修法: 在 bridge.ts 的 watch(store.aiResult) 中检测是否有 pageTask 字段，
      有则构造 PageTaskEnvelope → 走确定性执行器。30 分钟。
```

### 4.2 后端不产出页面执行指令

```text
问题: AiProcessResult 里有 replyDraft 和 evidenceId，
      但没有告诉前端「填到哪个 target」「滚到哪个 target」。
      PageAgent 还要靠 LLM 自己观察 DOM。

修法: 在 Orchestrator._finish_review() 中，根据 workflow_config 拼一个
      基础 PageTask，包含两条 action:
        fillTextarea(target="page-agent-reply-draft", value=reply_draft)
        locateEvidence(target="sunpilot-evidence", evidenceIds=[...])
      随 AiProcessResult 一起下发。20 分钟。
```

### 4.3 Schema 校验未启用

```text
问题: schema_validator.py 存在但 orchestrator 没有调用入口。
      答辩时说"有 schema 校验"会被质疑。

修法: 在 _run_agent_step 中加一行 validate(agent_card.output_schema, result)，
      不匹配就记 warning trace。10 分钟。
      或者答辩时主动声明"校验框架已建，当前 demo 未启用"——
      这比声称"有校验"安全。
```

### 4.4 PipelineContext 仍是松散 dict

```text
问题: intent_result: dict[str, Any] 而非 IntentResult 类型。

评估: 这是架构债务，但不影响 demo 的视觉展示。
      答辩时如果有人问"怎么保证数据类型安全"，
      答"当前用 dataclass 框架，类型化 DTO 已定义，全量替换是后续的渐进工作"。
      不必今天改。
```

---

## 五、工作量汇总

```text
┌─────────────────────────────────────────────────────────────┐
│  二、工单差异化                                                │
│    DB 扩展表                                      1h          │
│    发单表单动态字段                                1h           │
│    发单Agent 特有字段提取                           1h          │
│    workflow_config 场景配置                         0.5h        │
│    mock 数据独立化（种子文件分离）                   0.5h         │
│                                                             │
│  三、发单/回单分离                                            │
│    拆出 DispatchView.vue                           1h          │
│    回单侧保留/重命名                                 0.5h        │
│    路由调整                                         0.5h        │
│                                                             │
│  四、demo 流畅性                                              │
│    bridge 打通 PageTask                              0.5h       │
│    后端产出 PageTask                                 0.5h       │
│    schema校验入口 / 答辩降级话术                     0.25h      │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  总计                                              ~7.5h       │
│                                                             │
│  一天做完，明天演示。                                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 六、执行顺序

```text
1. DB 扩展表 + mock 独立 seed        ← 先做，后续都依赖
2. 发单Agent 扩展 + workflow_config   ← 和 DB 并行
3. 发单表单动态字段 + 拆分 DispatchView  ← 核心视觉差异
4. bridge 打通 PageTask + 后端产出    ← 让 demo 跑在快车道
5. schema 校验入口 / 答辩降级话术     ← 收尾
```
