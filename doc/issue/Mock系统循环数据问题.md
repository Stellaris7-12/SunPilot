# Mock 系统循环数据问题与修正方案

> 2026-07-23

---

## 问题：循环论证

```
tickets.json 里写:  customer_id=C88123, phone=138****6789
       │
       ▼
seed 脚本提取:      INSERT INTO mock_customers (customer_id=C88123, phone=138****6789)
       │
       ▼
MockExecutor:       customer.lookup(C88123) → 返回 C88123 + 138****6789
       │
       ▼
前端展示:           "已从客户资料系统自动调取客户号 C88123"

闭环: 工单 → Mock表 → "查到" → 展示。Mock 没有引入任何工单之外的独立信息。
```

**真实场景应该是**：客户资料系统独立于工单存在。通话记录只提供"线索"（客户号），Agent 用线索去外部系统查，补全通话里没提到的信息（如该客户有两张卡、曾有过争议记录等）。

---

## 当前 seed 脚本的工作方式

`_seed_mock_domain_data()` 遍历 `tickets` 表和 `call_transcripts.json`，对每条记录：

| Mock 表 | 数据来源 |
|---|---|
| `mock_customers` | 直接从 ticket 行提取 customer_id / customer_name / phone |
| `mock_cards` | 直接从 ticket 行提取 card_last4，写死 product_name="Credit Card" |
| `mock_benefits` | 正则从 ticket.content 提取业务编码（如 `COUPON_REISSUE`） |
| `mock_applications` | 正则从 ticket.content 提取 `APP` 开头的申请单号 |
| `mock_transactions` | 正则从 ticket.content 提取 `TXN` 开头的交易编号、金额 |
| `mock_permissions` | 硬编码 6 条权限记录 |
| `mock_coupons` | 不做 seed（运行时由 coupon.reissue 写） |

**所有 Mock 数据都源自 tickets.json 或 call_transcripts.json。没有独立数据源。**

---

## 修正方案

### 核心原则

**Mock 表的数据独立于工单存在。工单只提供"线索"，Mock 表提供"补充信息"。**

### 做法

**1. 准备独立 seed 数据文件** `ai-engine/data/mock_domain_seed.json`

```json
{
  "customers": [
    {"customer_id":"C88123","customer_name":"王小明","phone":"138****6789","segment":"premium","risk_level":"low"},
    {"customer_id":"C20001","customer_name":"张明","phone":"139****1234","segment":"standard","risk_level":"medium"}
  ],
  "cards": [
    {"card_id":"CARD-C88123-8812","customer_id":"C88123","card_last4":"8812","product_name":"白金卡","card_status":"active","credit_limit":100000},
    {"card_id":"CARD-C20001-3456","customer_id":"C20001","card_last4":"3456","product_name":"金卡","card_status":"frozen","credit_limit":50000}
  ],
  "benefits": [
    {"benefit_id":"BEN-C88123-618","customer_id":"C88123","benefit_code":"618_PROMO","benefit_name":"618年中大促","remaining_count":1,"expire_at":"2026-12-31"}
  ],
  "transactions": [
    {"transaction_id":"TXN20260715001","customer_id":"C88123","card_last4":"8812","amount":128.00,"merchant":"星河商场","transaction_time":"2026-07-15 12:00:00","status":"posted"}
  ],
  "applications": [
    {"application_no":"APP20260723001","customer_id":"C20001","product_name":"信用卡申请","current_node":"under_review","expected_finish_at":"2026-07-30 18:00:00"}
  ]
}
```

**2. 修改 seed 脚本：从独立数据文件加载，而非从工单提取**

```python
# 改 _seed_mock_domain_data:
# 旧: 遍历 tickets 表 + call_transcripts.json，正则提取字段
# 新: 读取 mock_domain_seed.json，直接 INSERT
```

**3. 通话记录只提供线索，enrich_params 用线索查 Mock 表**

```
通话记录: "客户王小明来电..."
  → 发单Agent 提取: customerId=C88123, scene=优惠券补发
  → 这张工单里只提取了客户号和场景，缺手机号、信用卡信息

MockExecutor.enrich_params:
  → customer.lookup(C88123) → 从 mock_customers 查到 phone=138****6789, risk_level=low
  → card.account-status-query(C88123) → 从 mock_cards 查到有一张白金卡+一张金卡(冻结)
  → benefit.query(C88123, 618_PROMO) → 从 mock_benefits 查到参加618活动，剩余1次

补全后的信息比工单原文更丰富——
特别是"有一张冻结的金卡"这个信息，通话里完全没提到，
但对风险判断很重要。
```

### 修正后的效果

```
修正前（循环论证）:
  工单说 C88123 → Mock表里 C88123 的数据就是从工单提取的 → 查回来还是那些

修正后:
  工单说 C88123 → 查独立的 Mock 表 → 返回比工单更丰富的信息
  通话记录里只提到了优惠券问题，但 Mock 表揭示了这个客户还有一张冻结的金卡
  → EscalationAgent 可以参考这个信息做更准确的风险判断
```

---

## 答辩话术

"当前 demo 的 Mock 数据种子是从工单样本中抽取的——这是 demo 阶段的妥协。但架构上的抽象是正确的：Agent 不知道数据来自 Mock 还是真实系统，只知道 'customer.lookup(客户号)' 返回一个结构化的客户信息。换真实系统时，改 executor 层的方法实现即可。

如果要继续推进，第一优先级是把 Mock 数据独立化——准备独立于工单的客户/卡片/交易/权益种子数据——这样才能验证 'Agent 从通话记录获取线索 → 查询外部系统补充信息' 这个真实的生产流程。"
