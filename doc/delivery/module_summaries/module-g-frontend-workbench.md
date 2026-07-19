# 模块 G：坐席业务工作台重构总结

生成日期：2026-07-19

## 1. 模块定位

模块 G 位于 TicketAgent 核心闭环的产品呈现层，负责把后端 Agent、工具、证据、通知和评测结果转化为一线坐席/业务员能直接使用的操作界面。

它承接模块 A 到 F+ 已经稳定下来的能力：

- 模块 A 提供稳定的工单状态、API、SSE 和持久化契约。
- 模块 B 到 D 提供 Intake、Classifier、Resolution、Notification、Escalation 五类业务 Agent，以及工具执行、证据编号、回单和复核摘要。
- 模块 E/F/F+ 提供评测样本、真实 LLM 回归指标和效果证明。

没有模块 G 时，系统虽然能跑通智能处理链路，但前端更像开发者 Demo：观众需要理解 Trace、Agent 名称和底层字段，坐席也难以快速判断“这张工单现在该谁处理、该点哪个按钮、能不能结案”。模块 G 的核心价值就是把系统从“能演示 AI 链路”推进到“像真实业务工作台一样可操作、可复核、可解释”。

## 2. 做了什么

模块 G 最终把前端重构为面向一线坐席的信用卡工单处理工作台。

第一，首页从普通工单列表改为坐席工作池。页面按待处理、待补充、待人工确认、待复核、已升级、已结案组织队列，并支持按场景族筛选，让坐席先看到等待原因和下一步动作。

第二，工单详情页从“左侧原文 + 右侧 AI 卡片流”改为案件处理台。首屏展示案件卷宗、业务场景、当前状态、风险、处理结论、下一负责人、证据编号和建议动作。

第三，Agent 信息完成业务化降噪。主界面不直接强调 `IntakeAgent`、`ClassifierAgent` 等技术名，而是展示接单提取、业务分诊、风险拦截、执行处理、回单生成等业务动作；底层 Agent Trace 统一收纳到“技术审计 / Agent 执行明细”折叠区。

第四，前端新增评测摘要，把模块 F/F+ 的指标产品化展示。首页可以直接看到状态/预期结果匹配率、工具命中率、字段完整率、平均耗时和样本数。

## 3. 工作原理

模块 G 的输入来自现有前后端契约，不新增后端 schema：

- `GET /api/tickets`：坐席工作池和优先队列。
- `GET /api/tickets/{id}`：案件基础信息。
- `GET /api/tickets/{id}/ai-result`：最新 AI 处理结果、字段、工具结果、证据、通知包和结案建议。
- `GET /api/tickets/{id}/trace`：历史 Agent 执行明细。
- `GET /api/tickets/{id}/ai-process-stream`：实时 SSE 处理链路。
- `GET /api/tools`：业务工具目录。
- `GET /api/evaluation/metrics`：评测摘要。

前端通过 `frontend/src/utils/business.ts` 建立业务语义层，把后端字段转成坐席可理解的页面信息：

- `Ticket.status` 转为待处理、待补充、待确认、待复核、已升级、已结案等状态。
- `Ticket.scene`、`AiProcessResult.intent`、`workflowName` 和 `toolName` 归并为权益/优惠券、申请进度、资料变更、交易/争议、人工协办等场景族。
- `toolResponse`、`toolEvidence` 和 `notification` 中的证据编号汇总成统一证据展示。
- `notification.standardReply`、`reviewSummary` 和 `closureSuggestion` 转成回单复核和结案建议。
- `traceSteps` 转成业务处理链和技术审计抽屉。

交互流程上，坐席先在工作池按状态和场景筛选工单；进入详情后，先看案件卷宗判断当前状态和建议动作；需要处理时从右侧坐席动作栏启动 AI、填入回单、查看风险、定位工具或进入复核；若涉及敏感操作，前端显示人工确认弹窗；如需追问技术链路，再展开审计抽屉查看 Agent Trace。

## 4. 核心内容

关键页面：

- `frontend/src/views/TicketListView.vue`：坐席工作池，展示状态池、优先队列和评测摘要。
- `frontend/src/views/TicketDetailView.vue`：案件处理台，串联案件卷宗、客户诉求、处理链、证据、回单和坐席动作栏。

关键业务语义：

- `frontend/src/utils/business.ts`：场景族、状态文案、风险文案、下一负责人、证据编号、建议动作、业务处理链和评测指标格式化。

关键前端组件：

- `frontend/src/components/layout/AppSidebar.vue`：左侧工作池、状态筛选和场景族筛选。
- `frontend/src/components/ticket/TicketInfo.vue`：案件卷宗首屏。
- `frontend/src/components/ai/AiProcessPanel.vue`：业务处理链。
- `frontend/src/components/ai/AiResultCard.vue`：关键字段、工具与证据、风险检查。
- `frontend/src/components/ai/PageAssistantPanel.vue`：坐席动作栏。
- `frontend/src/components/ai/NotificationBundlePanel.vue`：回单与复核闭环。
- `frontend/src/components/ai/AgentTraceTimeline.vue`：技术审计 / Agent 执行明细。
- `frontend/src/components/metrics/EvaluationSummaryPanel.vue`：模块 F/F+ 评测摘要。

关键文档与计划：

- `doc/planning/task_plan.md`：模块 G 任务清单已按坐席工作台方向完成。
- `doc/guides/启动与使用指南.md`：已同步坐席工作池、案件处理台和 Demo 录制路径。

关键忽略规则：

- `.gitignore` 已确认忽略 `frontend/node_modules/`、`frontend/dist/`、`frontend/.vite/` 和本地验证截图 `frontend-module-g-*.png`，避免把前端依赖、构建产物或临时截图提交到仓库。

## 5. 结果表现

模块 G 完成后，前端具备了更接近真实业务场景的可观察效果：

- 坐席进入首页即可看到当前待接管、已结案、各状态队列数量、优先工单和评测摘要。
- 工单详情首屏能直接回答：当前是什么案子、处于什么状态、风险是什么、下一步谁处理、证据编号是什么、建议动作是什么。
- 自动工具型场景突出字段完整性、工具执行、业务结果、证据编号和回单建议。
- 敏感确认型场景突出身份核验、风险原因、人工确认和不可直接自动执行的原因。
- 高风险升级型场景突出升级原因、人工接管建议和禁止自动结论。
- 信息缺失型场景突出缺失字段和补充后继续处理的路径。
- Agent 技术信息保留但不喧宾夺主，默认进入审计抽屉。
- 评测指标可以在首页产品化展示，并明确 `closedLoopSuccessRate` 是“状态/预期结果匹配率”，不是生产真实结案率。

已完成的验证：

```powershell
cd frontend
cmd /c npm run build

cd C:\Users\heyunhui\PyProjects\TicketAgent
.venv\Scripts\python.exe -m compileall ai-engine
.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_d.py
.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_f.py
```

联调验证：

- 前端页面 `http://127.0.0.1:5173/tickets` 返回 200。
- 后端 `GET /api/tickets`、`GET /api/evaluation/metrics` 可被前端消费。
- 同步处理 `POST /api/tickets/{id}/ai-process` 返回 `trace` 和结构化 `notification`。
- SSE 处理 `GET /api/tickets/{id}/ai-process-stream` 返回 `agent_start`、`agent_complete` 和 `workflow_*` 终态。
- Chrome headless 渲染检查通过，工作池和详情页无 console error、无 failed request。

## 6. 代表性例子

### 例子：优惠券补发

输入：客户反馈参加活动达标但未收到餐饮优惠券。
处理：工作池识别为权益/优惠券场景；详情页展示达标原因、补券工具、证据编号和客户回单。
结果：坐席看到 `coupon.reissue` 的业务结果和证据编号，可填入回单草稿并复核结案。

### 例子：地址修改

输入：客户要求修改账单寄送地址，并提供新地址和身份核验状态。
处理：页面识别为资料变更和中风险场景；右侧动作栏提示人工确认敏感操作。
结果：坐席确认后继续执行工具，回单区展示处理结果和结案建议；拒绝时转人工处理。

### 例子：交易争议/盗刷疑似

输入：客户反馈交易非本人消费，怀疑卡片被盗刷。
处理：页面识别为交易/争议和高风险场景，突出风险原因、人工接管建议和禁止自动结论。
结果：系统不把高风险争议包装成自动完成，坐席可查看升级原因和技术审计。

### 例子：缺少申请单号

输入：客户咨询申请进度，但未提供申请单号或业务流水号。
处理：页面展示缺失字段和待补充状态，建议动作变为请求客户补充。
结果：坐席无需阅读底层 Trace 即可知道当前不能继续执行进度查询工具。

## 7. 边界与后续

模块 G 当前完成的是坐席工作台级别的前端重构，不等同于生产级银行核心系统。

当前边界：

- 前端仍消费现有 Mock Tool/API 和本地 Demo 数据；真实业务系统接入后，需要重新验证工具目录、证据编号和异常返回。
- 页面助手只操作当前工单页面内的低风险动作，不执行外部遗留系统自动化。
- 自动流程只生成建议和回单草稿，敏感、高风险、未知场景仍必须人工确认或人工接管。
- 评测摘要展示的是模块 F/F+ 的样本评测指标，不代表生产环境实时质量监控。
- 当前只有坐席主视角；主管视角、团队分派、SLA 监控和批量复核仍属于后续扩展。

后续模块 H 可以在这个工作台基础上继续扩展 Dispatcher Agent、A2A-Lite、MCP、Page Agent 和 LangGraph，但这些能力不应破坏当前已形成的坐席主流程：先看案件状态，再看证据和建议，最后由人工复核敏感动作和结案。
