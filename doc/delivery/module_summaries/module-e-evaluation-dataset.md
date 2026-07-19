# 模块 E：数据集构建与场景扩展总结

## 1. 模块定位

模块 E 位于 TicketAgent 核心闭环的评测数据底座层，承接模块 A 到 D 已经跑通的“接单、分类、执行、通知、升级”业务链路，为后续模块 F 的 Agent 测评提供统一样本来源。

它解决的核心问题是：系统不能只依赖 `ai-engine/data/tickets.json` 中少量 Demo 工单来证明能力，而需要有一组独立、可读取、可回归的小型业务样本集，用来说明系统覆盖了多类信用卡工单场景，并能验证每类 Agent 输出是否符合预期。

没有模块 E 时，系统虽然可以演示单个工单闭环，但缺少三个关键能力：
- 无法证明场景覆盖不是硬编码在 3 到 5 个 Demo 案例上。
- 无法为模块 F 的准确率、完整率、工具命中率和闭环成功率提供统一标签。
- 无法在后续修改 Agent、Prompt、工具规则后做稳定回归。

## 2. 做了什么

模块 E 最终沉淀了一套独立于 Demo 种子数据的 40 条中文模拟标注样本，并建立了样本读取和校验入口。

这批样本不是训练数据，而是评测数据和回归数据。它主要服务三件事：
- 证明 TicketAgent 覆盖了优惠券补发、资料变更、申请进度、权益查询、交易争议、投诉、征信异议等多类业务场景。
- 为每条工单标注正确意图、正确工单类型、必填字段、期望工具、期望状态、期望处理结果、回单要点和是否需要人工介入。
- 让评测脚本和 `/api/evaluation/metrics` 可以读取真实样本数量，后续模块 F 在此基础上计算真实 Agent 指标。

同时，模块 E 明确了数据边界：
- `ai-engine/data/tickets.json` 继续作为小规模 Demo 种子数据。
- `ai-engine/data/evaluation_samples.json` 作为独立评测样本集。
- `ai-engine/data/external/` 和 `ai-engine/data/generated/` 用于外部大数据和生成数据，已通过 `.gitignore` 避免进入 Git。

## 3. 工作原理

模块 E 的输入来自两类来源。

第一类是业务场景规划。系统根据当前信用卡工单闭环，优先覆盖已经具备工具能力的标准高频场景，例如优惠券补发、申请进度查询、资料变更、权益资格核验和交易查询。

第二类是外部数据源参考。CFPB 投诉库适合参考金融投诉、争议和账单类工单；BANKING77 适合参考短文本银行意图分类。但它们都不是最终可直接使用的中文工单标注集，所以模块 E 没有直接把英文原文放进评测集，而是构建中文模拟样本并补齐期望输出。

每条样本采用统一结构：
- `ticket` 描述工单输入，包括标题、原文、风险等级、模拟客户号、脱敏手机号和卡号后四位。
- `expected` 描述期望输出，包括意图、工单类型、workflow、必填字段、字段值、期望工具、期望状态、处理结果、回单要点和人工介入判断。

评测链路读取 `evaluation_samples.json` 后，可以用样本标签和真实 Agent 输出对比。模块 E 阶段只保证样本结构和读取能力；真实 Agent 输出评分由模块 F 承接。

## 4. 核心内容

核心数据集：
- `ai-engine/data/evaluation_samples.json`：40 条中文模拟标注样本。

核心脚本：
- `ai-engine/evaluation/smoke_module_e.py`：模块 E 验收脚本，校验样本数量、结构、脱敏、核心工具覆盖、状态覆盖、Demo/评测分离，以及评测入口读取。
- `ai-engine/evaluation/evaluator.py`：支持读取新的 `expected` 样本结构，并保持旧字段兼容。

核心接口：
- `/api/evaluation/metrics`：通过 `Evaluator.compute()` 返回指标结构；模块 E 完成后，`totalSamples` 由真实样本数量驱动。

核心场景覆盖：
- 已接入工具闭环的场景：优惠券补发、资料变更、交易查询、权益查询、申请进度查询。
- 扩展和兜底场景：分期提前结清、还款协商、挂失补卡、额度咨询、年费、积分、征信异议、投诉催办、跨部门协办。

## 5. 结果表现

模块 E 完成后，系统拥有 40 条可评测样本，并通过脚本验证：
- 样本数量达到 MVP 验收下限。
- 每条样本都有明确标签和期望输出。
- 所有客户号、手机号、卡号均为模拟或脱敏值。
- Demo 种子数据和评测数据分开存放，避免演示数据污染评测数据。
- 样本覆盖自动处理、待补充、人工确认、升级人工等关键路径。
- `/api/evaluation/metrics` 可以读取真实样本数量，返回 `totalSamples=40`。

已通过的验证命令：

```powershell
.venv\Scripts\python.exe -m compileall ai-engine
.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_e.py
.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_a.py
.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_b.py
.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_c.py
.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_d.py
```

## 6. 代表性例子

### 例子：优惠券补发自动执行

输入：客户反馈参加餐饮满减活动后已达标，但 App 优惠券中心未收到 `DINING_100_20` 券。

处理：样本标注期望意图为 `COUPON_REISSUE`，必填字段为客户号、券类型和补发原因，期望工具为 `coupon.reissue`。

结果：模块 F 可用这条样本验证 Classifier 是否识别为补券场景，Intake 是否抽取关键字段，Resolution 是否选择补券工具，Notification 是否覆盖回单要点。

### 例子：优惠券补发缺少券类型

输入：客户只说明活动达标但未收到优惠券，没有提供具体活动名称或券类型。

处理：样本标注期望意图仍为 `COUPON_REISSUE`，但 `couponType` 为未提供，期望状态为 `pending_info`。

结果：评测时可以验证系统是否识别缺失字段，并生成补充信息追问，而不是强行调用补券工具。

### 例子：资料变更需要人工确认

输入：客户要求修改账单寄送地址，并提供新地址和身份核验通过状态。

处理：样本标注期望意图为 `CUSTOMER_ADDRESS_UPDATE`，期望工具为 `customer.update-address`，但由于资料变更属于敏感操作，期望状态为 `pending_human_confirm`。

结果：评测时可以验证系统是否在敏感资料变更前进入人工确认，而不是直接自动修改。

### 例子：非本人消费争议升级人工

输入：客户反馈某笔交易非本人消费，并怀疑卡片被盗刷。

处理：样本标注期望意图为 `TRANSACTION_DISPUTE`，期望工具为 `transaction.query`，但期望最终状态为 `escalated`。

结果：评测时可以验证系统是否识别高风险争议场景，并将后续处理交给人工争议岗。

## 7. 边界与后续

模块 E 只解决“有没有可评测、可回归、结构清楚的数据集”这个问题，不直接承诺 Agent 在这些样本上的真实效果分数。

当前边界：
- 40 条样本是 MVP 评测集，适合答辩演示和阶段性回归，不等同于生产级大规模评测集。
- 样本为中文模拟工单，不是真实客户数据；真实业务数据接入前仍需脱敏、合规审查和标注复核。
- CFPB 和 BANKING77 仅作为扩展参考，不直接作为最终中文标注样本。
- 模块 E 阶段 `/api/evaluation/metrics` 主要完成真实样本数量读取；真实 Agent 输出评分由模块 F 承接。

后续模块 F 已在模块 E 的基础上继续完成真实 Agent 测评，模块 G 则应把这些样本和指标转成更容易被业务观众理解的前端展示。
