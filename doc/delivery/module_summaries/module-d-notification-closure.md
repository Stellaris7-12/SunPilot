# 模块 D：Notification 与回单闭环总结

## 1. 模块定位

模块 D 位于 TicketAgent 核心处理链路的最后一段，承接模块 C 的工具执行结果和证据编号，把“系统已经做了什么”转化为客户能看懂、业务人员能复核、工单系统能追溯的通知与回单结果。

它服务的是工单闭环中的通知、回单、复核和结案建议环节。前面的 `IntakeAgent`、`ClassifierAgent`、`ResolutionAgent` 和 `EscalationAgent` 负责识别问题、判断路径、执行工具和兜底升级；`NotificationAgent` 则负责把这些处理过程沉淀成标准回单、内部通知、复核摘要、结案建议和回访预留。

没有模块 D 时，系统虽然可以调用工具、留下证据，但业务人员仍需要从 Trace 和工具结果里重新整理客户话术；客户也无法直接获得清楚、规范、可解释的处理反馈。模块 D 的价值就是让 TicketAgent 从“会处理”走到“会交付处理结果”。

## 2. 做了什么

模块 D 最终让系统具备了结构化通知和回单闭环能力。

第一，`AiProcessResult` 在保留 `replyDraft` 兼容字段的基础上，新增了结构化 `notification`。这个结构不只是一段文本，而是同时包含客户标准回单、内部通知、人工复核摘要、结案建议和回访预留。

第二，`NotificationAgent` 从单一话术生成升级为通知包生成。它可以基于工单状态、分类结果、抽取字段、工具执行结果、证据编号和升级原因生成不同类型的通知内容；当 LLM 调用失败或输出不完整时，会使用规则 fallback，保证通知环节不会拖垮主流程。

第三，系统把“是否建议结案”和“实际结案”分开。自动链路只输出 `closureSuggestion.canClose` 和最终回单建议，真正把工单置为 `closed` 仍然必须由人工通过 `/api/tickets/{ticket_id}/close` 提交。

## 3. 工作原理

模块 D 的输入来自前序 Agent 和 Orchestrator 汇总的处理上下文，主要包括工单原文、工单状态、分类结果、抽取字段、工具结果、证据编号、是否需要人工介入、失败原因或升级原因。

`NotificationAgent` 会先尝试生成结构化 JSON 通知包。通知包中的关键字段包括：

- `standardReply`：面向客户的标准回单。
- `internalNotice`：面向业务人员的内部状态通知。
- `reviewSummary`：面向人工复核人员的摘要。
- `closureSuggestion`：是否建议结案、原因、最终回单和是否需要人工复核。
- `followUp`：结案后的满意度回访或后续跟进预留。

为了避免 LLM 生成内容突破业务边界，模块 D 使用确定性规则做归一和约束。状态、证据编号、失败原因、是否可结案等关键判断不交给 LLM 自由决定；LLM 可以优化表达，但不能把失败工具包装成成功处理，也不能把高风险或待补充场景伪造成可直接结案。

Orchestrator 会在关键终态都生成通知：自动处理成功、待补充信息、待人工确认、工具失败升级、高风险直升人工和人工拒绝后升级。前端优先读取结构化 `notification.standardReply.body`，同时继续兼容旧的 `replyDraft`。

结案时，前端通过回单编辑器提交最终回单，后端 `/api/tickets/{ticket_id}/close` 更新工单状态，并把 `final_reply` 和 `closed_at` 回写到 `ai_results`，用于后续追溯。

## 4. 核心内容

核心 Agent：

- `ai-engine/agents/notification_agent.py`：生成结构化通知包，并提供规则 fallback 和归一保护。

核心数据结构：

- `NotificationArtifact`：通知项，包含标题、正文、状态、证据编号、下一步责任方和建议动作。
- `NotificationBundle`：通知包，包含标准回单、内部通知、复核摘要、结案建议和回访预留。
- `AiProcessResult.notification`：AI 处理结果中的结构化通知字段。
- `AiProcessResult.replyDraft` / `reply_draft`：兼容旧前端和旧测试的回单草稿字段。

核心接口与持久化：

- `/api/tickets/{ticket_id}/close`：人工确认结案入口，提交最终回单。
- `ai_results.notification_json`：保存结构化通知包。
- `ai_results.final_reply`：保存最终人工确认后的回单内容。
- `ai_results.closed_at`：保存结案时间。

关键前端展示：

- `frontend/src/components/ai/NotificationBundlePanel.vue`：展示标准回单、内部通知、复核摘要、结案建议和回访预留。
- `frontend/src/components/ai/ReplyDraftEditor.vue`：编辑最终回单，并根据结案建议提示是否适合结案。
- `frontend/src/views/TicketDetailView.vue`：在工单详情页串联通知包展示和结案操作。

核心验证脚本：

- `ai-engine/evaluation/smoke_module_d.py`：覆盖模块 D 的通知生成、结案建议、安全归一和结案回写。

## 5. 结果表现

模块 D 完成后，系统在通知和回单层具备了可演示的业务闭环：

- 客户回单不再是开发调试文本，而是包含处理结果、证据编号和后续建议的标准话术。
- 内部通知能说明当前工单是已处理、待补充、待人工确认、已升级还是可复核结案。
- 人工复核人员可以直接看到摘要和建议操作，不需要重新阅读完整 Trace。
- 可自动处理的标准场景会给出 `closureSuggestion.canClose=true`，但仍由人工复核后结案。
- 待补充、高风险、工具失败、人工拒绝等场景会给出不可直接结案的原因。
- 结案后可以追溯结构化通知、最终回单和结案时间。

已通过的验证命令：

```powershell
.venv\Scripts\python.exe -m compileall ai-engine
.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_a.py
.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_b.py
.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_c.py
.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_d.py
cd frontend
npm run build
```

## 6. 代表性例子

### 例子：优惠券补发成功后建议复核结案

输入：客户反馈活动达标但未收到优惠券，系统已抽取客户号和券类型。

处理：`ResolutionAgent` 调用 `coupon.reissue` 成功，返回业务结果和证据编号；`NotificationAgent` 生成标准回单、内部通知和复核摘要。

结果：`closureSuggestion.canClose=true`，前端显示“建议复核后结案”，人工确认最终回单后通过 `/close` 结案并回写 `final_reply`、`closed_at`。

### 例子：缺少关键信息时生成补充提示

输入：客户只说没有收到优惠券，但没有提供券类型或活动名称。

处理：`IntakeAgent` 识别缺失字段，Orchestrator 进入 `pending_info`，`NotificationAgent` 生成面向客户的补充信息提示。

结果：标准回单状态为 `needs_info`，`closureSuggestion.canClose=false`，系统不会调用补券工具，也不会建议结案。

### 例子：资料变更等待人工确认

输入：客户要求修改账单寄送地址，并提供了新地址。

处理：资料变更属于敏感或中风险操作，系统生成复核摘要和建议动作，把下一步责任方交给人工。

结果：通知包说明“暂不建议直接结案”，前端回单编辑器提示人工处理后再结案。

### 例子：工具失败或高风险场景升级

输入：工具返回失败、权限不足、结果冲突，或客户反馈疑似盗刷等高风险争议。

处理：`EscalationAgent` 将工单升级人工，`NotificationAgent` 生成升级说明、内部通知和复核摘要。

结果：标准回单状态为 `escalated`，`closureSuggestion.canClose=false`，LLM 不能把失败结果改写成“已完成处理”。

## 7. 边界与后续

模块 D 当前解决的是通知、回单和结案建议闭环，不等同于完全自动结案系统。

当前边界：

- 工具层仍主要是 Mock Tool/API，真实业务系统接入后需要重新验证证据编号、失败原因和回单模板。
- 自动链路只给出结案建议，实际结案必须由人工通过 `/close` 提交。
- 高风险、敏感操作、工具失败、权限不足、结果冲突和信息缺失场景不允许自动包装为成功闭环。
- 回访能力当前是模板和状态预留，后续可接入满意度收集或外呼/短信渠道。

后续模块 E/F 已在模块 D 的基础上构建评测样本和 Agent 指标；模块 G 应继续把通知包、结案建议和回单可追溯性产品化展示，让非技术观众能快速理解系统做了什么、为什么这么做、下一步由谁处理。
