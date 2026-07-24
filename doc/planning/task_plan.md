# TicketAgent 答辩前验收清单（2026-07-23）

> 3 小时窗口。覆盖 5 个真实业务场景 + 数据库表重构。

---

## P0-1 工单差异化表单 + 数据库重构（120 min）

### 5 个业务场景（基于真实招商银行 FITS 系统）

| # | 场景 | 编号前缀 | 特有字段（与通用字段不同） |
|---|---|---|---|
| A | 伪冒预防 | 12xxxx | CALLID, 主叫号, 是否消费者本人, 投诉人姓名, 投诉人证件号, 投诉人手机号, 案件编号, 工单类别, 被投诉内容, 主体诉求 |
| B | 伪冒调查 | 13xxxx | 卡片列表(BLOCK状态), 备注(卡号段), 管制原因, X-DK |
| C | 客户经营 | 29xxxx | 接单单位(卡部), 业务细类, 资料类型 |
| D | 市场企划 | 30xxxx | 卡片列表, 卡片名称, 订单号备注, 客户反馈, 接单单位(市场), 业务细类 |
| E | 征信 | 42xxxx | 账户类型, 账户号, 是否敏感, 逾期状态 |

**通用字段**（所有场景共有）: 客户姓名, 客户号, 证件号, 手机号, 预警等级, 发单内容, 具体内容, 是否需要回复, 补充信息, 规定回件日期

### 子任务

#### [x] D1-1 数据库表重构（25 min）

当前 `tickets` 表 30 个字段全部平铺。重构为通用字段 + JSON 扩展：

```sql
ALTER TABLE tickets 
  ADD COLUMN ext_json JSON NULL COMMENT '场景特有字段',
  ADD COLUMN order_prefix VARCHAR(8) NOT NULL DEFAULT '' COMMENT '编号前缀(12/13/29/30/42)',
  ADD COLUMN biz_type VARCHAR(64) NOT NULL DEFAULT '' COMMENT '业务类型',
  ADD COLUMN biz_sub_type VARCHAR(64) NOT NULL DEFAULT '' COMMENT '业务细分类型',
  ADD COLUMN deadline DATETIME NULL COMMENT '规定回件日期(SLA)',
  ADD COLUMN receive_unit VARCHAR(64) NOT NULL DEFAULT '' COMMENT '接单单位',
  ADD COLUMN need_reply TINYINT NOT NULL DEFAULT 1 COMMENT '是否需要回复';

-- ext_json 示例:
-- 伪冒预防: {"callId":"xxx","complainantName":"张三","caseNo":"801114413001",...}
-- 市场企划: {"cardName":"白金卡","remark":"订单号0006258...","customerFeedback":"...",...}
-- 征信:     {"accountType":"个人消费账户","isSensitive":true,"overdueStatus":"正常"}
```

**优势**：不改动现有查询逻辑，通用字段保持不变。`ext_json` 按场景动态填充，前端 v-for 渲染时同时从通用字段和 ext_json 取值。

迁移脚本：`ai-engine/migrations/mysql/002_dispatch_ext.sql`

执行记录：迁移脚本、初始化 DDL、运行时 schema upgrade、Repository 入库/查询响应已接入；已执行 `init_db()` 完成真实 MySQL schema 升级。

#### [x] D1-2 workflow_config 扩展（15 min）

文件：`ai-engine/data/workflow_config.json`

新增 5 个场景的 `specificFields`：

```json
{
  "scenarios": {
    "伪冒预防": {
      "label": "伪冒预防", "orderPrefix": "12",
      "slaDays": 2,
      "specificFields": [
        {"name":"callId","label":"CALLID","type":"text"},
        {"name":"callerNo","label":"主叫号","type":"text"},
        {"name":"isConsumerSelf","label":"是否消费者本人","type":"select","options":["是","否"]},
        {"name":"complainantName","label":"投诉人姓名","type":"text"},
        {"name":"complainantIdNo","label":"投诉人证件号","type":"text"},
        {"name":"complainantPhone","label":"投诉人手机号","type":"text"},
        {"name":"caseNo","label":"案件编号","type":"text"},
        {"name":"workOrderCategory","label":"工单类别","type":"select","options":["投诉引导(接受投调引导)","伪冒交易预警"]},
        {"name":"complaintContent","label":"被投诉内容","type":"textarea"},
        {"name":"mainDemand","label":"主体诉求","type":"textarea"}
      ]
    },
    "伪冒调查": {
      "label": "伪冒调查", "orderPrefix": "13",
      "slaDays": 3,
      "specificFields": [
        {"name":"cardList","label":"卡片列表(BLOCK)","type":"text"},
        {"name":"cardRemark","label":"备注(卡号段)","type":"text"},
        {"name":"controlReason","label":"管制原因","type":"text"},
        {"name":"xdk","label":"X-DK","type":"text"}
      ]
    },
    "客户经营": {
      "label": "客户经营", "orderPrefix": "29",
      "slaDays": 6,
      "specificFields": [
        {"name":"receiveUnit","label":"接单单位","type":"select","options":["卡部[上海卡部]","卡部[北京卡部]"]},
        {"name":"bizSubType","label":"业务细类","type":"select","options":["资料借阅","解抵押","汽车分期结清证明","个人金普卡业务","AE百夫长卡"]},
        {"name":"materialType","label":"资料类型","type":"text"}
      ]
    },
    "市场企划": {
      "label": "市场企划", "orderPrefix": "30",
      "slaDays": 5,
      "specificFields": [
        {"name":"cardList","label":"关联卡片列表","type":"text"},
        {"name":"cardName","label":"卡片名称","type":"text"},
        {"name":"remark","label":"订单号/备注","type":"text"},
        {"name":"customerFeedback","label":"客户反馈情况","type":"textarea"},
        {"name":"receiveUnit","label":"接单单位","type":"select","options":["市场[020营销管理团队]","市场[030品牌团队]"]},
        {"name":"bizSubType","label":"业务细类","type":"select","options":["饭票总对总-麦当劳","影票","掌上生活","新品牌","品质电商","代金券"]}
      ]
    },
    "征信": {
      "label": "征信", "orderPrefix": "42",
      "slaDays": 3,
      "specificFields": [
        {"name":"accountType","label":"账户类型","type":"select","options":["个人消费账户","个人储蓄账户"]},
        {"name":"accountNo","label":"账户号","type":"text"},
        {"name":"isSensitive","label":"是否敏感","type":"select","options":["是","否"]},
        {"name":"overdueStatus","label":"逾期状态","type":"select","options":["正常","已逾期","待确认"]}
      ]
    }
  }
}
```

#### [x] D1-3 发单表单 v-for 动态渲染（25 min）

从硬编码 11 个 `<label>` 改为通用字段 + 特有字段动态组合。同一个 Vue 模板适配 5 种表单——切换通话后字段自动变化。

```vue
<!-- 通用字段 -->
<label v-for="field in commonFields" :key="field.name">
  <span>{{ field.label }}</span>
  <input v-model="draftForm[field.name]" 
         :data-page-agent-target="`dispatch-${field.name}`" />
</label>

<!-- 场景特有字段 -->
<label v-for="field in scenarioFields" :key="field.name">
  <span>{{ field.label }}</span>
  <select v-if="field.type==='select'" v-model="draftForm[field.name]"
          :data-page-agent-target="`dispatch-${field.name}`">
    <option v-for="opt in field.options" :key="opt" :value="opt">{{ opt }}</option>
  </select>
  <textarea v-else-if="field.type==='textarea'" v-model="draftForm[field.name]"
            :data-page-agent-target="`dispatch-${field.name}`" />
  <input v-else v-model="draftForm[field.name]"
         :data-page-agent-target="`dispatch-${field.name}`" />
</label>
```

#### [x] D1-4 通话记录样本（15 min）

5 类场景各 1 条：

| ID | 场景 | 内容摘要 |
|---|---|---|
| `call-fraud-prevent` | 伪冒预防 | 客户称收到非本人申请的信用卡还款提醒，情绪激动，要求调查处理 |
| `call-fraud-invest` | 伪冒调查 | 客户卡片被系统管制，客户两核身不过，需要调查组介入处理 |
| `call-customer-mgmt` | 客户经营 | 客户申请汽车分期结清证明和资料借阅，接单单位卡部 |
| `call-marketing` | 市场企划 | 参加麦当劳满减活动，达标后优惠券未到账，含订单号 |
| `call-credit` | 征信 | 客户贷后历史风险待确认，账户逾期状态需要核实 |

#### [x] D1-5 发单Agent 扩展（20 min）

识别场景后查 `workflow_config[scene].specificFields`，追加特有字段提取。5 个场景共用一个 Agent，差异全在配置。

#### [x] D1-6 验收（20 min）

- [x] 选择不同通话 → 表单切换为对应特有字段（至少验证 3 类：伪冒预防 vs 市场企划 vs 征信）
- [x] 发单提交后 `ext_json` 正确存储特有字段

---

## P0-2 发单 / 回单页面分离（50 min）

### 子任务

#### [x] S2-1 拆分 DispatchView.vue（20 min）

从 `EnterpriseTicketShellView.vue` 拆出发单代码：

- 通话记录列表 + 选中通话全文
- 发单 Agent 生成草稿按钮
- 动态表单（D1-3 产物）+ 一键提交
- 字段来源提示条

路由：`/dispatch`

#### [x] S2-2 回单侧保留（15 min）

`/tickets/:id` 保留：工单信息 + AI 结果 + 回单编辑器 + 证据区 + SunPilot Panel

#### [x] S2-3 跳转衔接（5 min）

发单提交成功 → `router.push(/tickets/${id})`。SunPilot 两页面均可用。

#### [x] S2-4 验收（10 min）

- [x] `/dispatch` 只看到发单内容
- [x] `/tickets/:id` 只看到回单内容
- [x] 发单 → 跳转回单页

---

## 降级项（3 小时内不执行）

| 模块 | 状态 | 答辩口径 |
|------|------|----------|
| Mock 独立化 | 降级 | "架构抽象已正确，Agent 不感知数据来源，换真实接口只改 executor 层" |
| PageTask 链路 | 降级 | "协议已定义，执行器已完成，当前用自然语言 observation 通道" |
| Schema 校验 | 降级 | "框架已建，demo 阶段未强制启用，生产环境必须开" |

---

## 执行顺序

| 顺序 | 任务 | 时间 |
|------|------|------|
| 1 | D1-1 DB 重构 | 25 |
| 2 | D1-2 workflow_config | 15 |
| 3 | D1-3 表单动态渲染 | 25 |
| 4 | D1-4 通话样本 | 15 |
| 5 | D1-5 发单Agent 扩展 | 20 |
| 6 | D1-6 验收差异化 | 20 |
| 7 | S2-1 拆分 DispatchView | 20 |
| 8 | S2-2 回单侧保留 | 15 |
| 9 | S2-3 跳转 + S2-4 验收 | 15 |
| **总计** | | **170 min** |

---

## 验收清单（总）

- [x] 5 个场景在 workflow_config 中有独立的 specificFields 定义
- [x] tickets 表新增 ext_json + order_prefix + biz_type 等字段
- [x] 选择不同通话后，发单表单展示不同特有字段组合（至少验证 3 类）
- [x] 发单提交后 ext_json 正确存储
- [x] `/dispatch` 和 `/tickets/:id` 独立可用
- [x] 发单提交 → 自动跳转回单页，SunPilot 不中断

---

## 参考文件

| 文件 | 路径 | 内容 |
|------|------|------|
| 工单系统分类体系总结 | `C:\Users\heyunhui\Downloads\资料-工单多Agent系统\工单系统案例\ocr_output\工单系统分类体系总结.md` | 7 大类工单编号前缀、业务类型、发单表单通用字段、功能导航 |
| 工单字段结构详解 | `C:\Users\heyunhui\Downloads\资料-工单多Agent系统\工单系统案例\ocr_output\工单字段结构详解.md` | 7 大类逐字段对照表、字段差异矩阵、特有字段详细定义 |
