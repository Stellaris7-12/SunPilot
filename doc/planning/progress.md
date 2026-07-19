# 进度日志

## 会话：2026-07-19（模块F+全量真实LLM测评与收口）

### 背景

用户要求继续按照模块 F/F+ 计划完成真实 LLM 全量测评、使用子 Agent 审查、定位链路问题并继续优化迭代。当前环境可读取 `DEEPSEEK_API_KEY`，全程未输出真实 Key。

### 全量前置检查

- `evaluation_samples.json`：确认 40 条样本。
- `DEEPSEEK_API_KEY`：确认存在且长度为 35，未打印真实 Key。
- `run_module_f.py`：确认评测链路直接调用五类 Agent 与 Mock Tool，不写主业务数据库。
- 新增 `--output` 参数用于保存完整 records；新增 `--ids` 参数用于只跑问题样本，避免每次小修都重跑 40 条真实 LLM。
- 发现 `ai-engine/data/generated/` 当前不可写，`PermissionError` 后改将测评 artifact 保存到 `ai-engine/evaluation/`。

### 初始 40 条真实测评

- 命令：
  ```powershell
  .venv\Scripts\python.exe ai-engine\evaluation\run_module_f.py --records --output ai-engine\evaluation\module_f_full_20260719.json
  ```
- 结果：40 条全部跑完，`source=agent_run`。
- 初始指标：`intentAccuracy=0.725`、`fieldCompleteness=0.8911`、`toolCorrectness=0.7778`、`workflowConsistency=0.725`、`replyPointCoverage=0.8539`、`humanInterventionAccuracy=0.7`、`closedLoopSuccessRate=0.6`。

### 子 Agent 审查

- 子 Agent `Maxwell` 只读审查确认三类主因：
  - UNKNOWN 扩展场景被吸进现有 workflow，导致意图、workflow、字段和状态连锁低分。
  - `pending_human_confirm` 未显式建模，中风险资料变更和交易复核被落成 `escalated`。
  - 评分口径混淆 `pending_info`、`pending_human_confirm`、`escalated`，且敏感资料变更存在“先执行工具、后人工/升级”的风险。

### 迭代修复

- 第 1 轮：Classifier 增加 unsupported/out-of-scope 保护，Escalation 对 UNKNOWN 和 high 风险先人工分流，`run_module_f.py` 增加 `pending_human_confirm` 状态映射，Evaluator 跳过安全升级场景的工具扣分，并调整 `pending_info` 的人工介入口径。
- 第 2 轮：Escalation 对中风险、敏感资料变更和需要人工确认的 workflow 做确定性拦截，修复资料变更 `eval-011` 先执行 `customer.update-address` 的 P0 风险。
- 第 3 轮：Classifier 增加已支持场景正向保护，避免 APP 业务流水、交易争议、活动资格码被 UNKNOWN 兜底误伤；Resolution 对 `couponType`、`benefitCode`、`applicationNo`、`verifyStatus` 做机器参数规范化；Escalation 对 `verifyStatus=FAILED` 直接升级。
- 第 4 轮：补积分到账/扣减/兑换失败等扩展场景兜底，并把回单要点评分改成更贴近升级/待确认场景的业务槽位覆盖。
- 第 5 轮：修正活动码正则，确保中文紧贴 `POINT_MILEAGE_2026` 等英文业务码时仍能识别为权益查询。

### 最终 40 条真实测评

- 命令：
  ```powershell
  .venv\Scripts\python.exe ai-engine\evaluation\run_module_f.py --records --output ai-engine\evaluation\module_f_full_final3_20260719.json
  ```
- 结果：40 条全部跑完，`source=agent_run`、`evaluatedSamples=40`。
- 最终指标：`intentAccuracy=1.0`、`fieldCompleteness=1.0`、`toolCorrectness=1.0`、`workflowConsistency=1.0`、`replyPointCoverage=0.9888`、`humanInterventionAccuracy=1.0`、`closedLoopSuccessRate=1.0`、`avgProcessingMs=6529.6`。
- 说明：`closedLoopSuccessRate` 当前含义更准确地说是“期望状态匹配率”，不是实际客户结案率；模块 G 展示时应解释清楚。

### 当前验证结果

- `.venv\Scripts\python.exe -m compileall ai-engine`：通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_a.py`：通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_b.py`：通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_c.py`：通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_d.py`：通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_e.py`：通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_f.py`：通过。
- `cd frontend && npm.cmd run build`：通过。

### 当前阶段

- **状态：** completed
- **阶段名称：** 模块F+：真实 LLM 全量测评与指标收口
- **下一步：** 进入模块 G：前端产品呈现；优先把真实测评摘要、状态匹配口径和 Agent 分项指标产品化展示。

## 会话：2026-07-18/19（重新制定模块F+全量真实LLM测评计划）

### 背景

用户要求先更新 `doc/planning/task_plan.md`，重新制定真实 LLM 测评计划，再继续执行测评。当前模块 F 的测评框架、三轮小样本迭代和 12 条真实扩展回归已完成，但完整 40 条真实 LLM 测评仍未执行。

### 执行内容

- 将 `task_plan.md` 中模块 F 标题从“已完成”调整为“测评框架已完成”，避免把阶段性真实回归误表达为全量验收完成。
- 将原“真实 LLM 测评执行计划”改为“真实 LLM 阶段性执行记录”，保留 5 条预检、3 轮迭代和 12 条扩展回归的已完成事实。
- 新增“模块 F+：真实 LLM 全量测评与指标收口（P1）进行中”，明确全量前置检查、40 条真实测评、指标汇总、低分归因、修复回归和最终文档收口。
- 新计划明确区分 Agent 能力问题、评分口径问题、样本标注问题和外部服务问题，避免低分后盲目改 Agent 或盲目重复运行命令。

### 当前阶段

- **状态：** planned
- **阶段名称：** 模块F+：真实 LLM 全量测评与指标收口
- **下一步：** 按 F+ 清单执行全量前置检查，并运行 40 条真实 LLM 测评。

## 会话：2026-07-18/19（模块F真实LLM测评三轮迭代）

### 背景

用户要求按照模块 F 清单继续完成真实 LLM 测评、链路问题定位，并至少完成 3 轮迭代。当前环境可读取 `DEEPSEEK_API_KEY`，真实测评使用 `ai-engine/evaluation/run_module_f.py`。

### 三轮迭代与问题定位

- 第 1 轮真实 LLM 预检：执行 `.venv\Scripts\python.exe ai-engine\evaluation\run_module_f.py --limit 5 --records`，5 条全部完成且 `source=agent_run`。初始低分集中在 `workflowConsistency=0.0`、`replyPointCoverage=0.0`、`humanInterventionAccuracy=0.0`。
- 第 1 轮优化：`ClassifierAgent` 强制使用 `workflow_config` 的确定性 `workflow_name`；`Evaluator` 放宽中文回单要点匹配并区分 `pending_human_review` 与真正异常人工介入。回归后 `workflowConsistency=1.0`，`humanInterventionAccuracy=0.8`，`replyPointCoverage=0.4286`。
- 第 2 轮优化：修正待补充样本不应惩罚 Resolution 未执行工具、`pending_info` 不应因 `can_auto_proceed=false` 被算成人工介入、参数比较支持中文描述包含标准值。回归后 `toolCorrectness=1.0`、`parameterAccuracy=1.0`、`humanInterventionAccuracy=1.0`。
- 第 3 轮优化：将 Notification 回单要点评测从逐句匹配改为业务槽位覆盖，重点识别处理结论、证据/执行、后续建议、缺失字段/升级原因。5 条真实回归后顶层和分项核心指标均为 1.0。
- 扩展 12 条真实 LLM 回归：覆盖优惠券补发、申请进度、资料变更。严格化代码类参数匹配后最终阶段性结果为 `intentAccuracy=1.0`、`fieldCompleteness=1.0`、`toolCorrectness=0.8571`、`workflowConsistency=1.0`、`replyPointCoverage=0.9655`、`humanInterventionAccuracy=1.0`、`closedLoopSuccessRate=0.8333`、`source=agent_run`。

### 子 Agent 审查

- 子 Agent 只读审查确认低分主因是评分口径误伤和 workflow 归一化问题。
- 第二次只读复查指出参数评分不应对 ID/编号/券码使用过宽字符重叠；已修复为代码类字段严格匹配，中文描述类字段才允许包含/相似。
- 残留 P1：完整 40 条真实 LLM 测评尚未执行；当前阶段性真实结果来自 5 条三轮迭代和 12 条扩展回归。资料变更等敏感场景的 `pending_human_confirm`、`escalated` 分流仍是后续业务策略优化点。

### 当前验证结果

- `.venv\Scripts\python.exe -m compileall ai-engine`：通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_a.py`：通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_b.py`：通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_c.py`：通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_d.py`：通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_e.py`：通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_f.py`：通过。
- `cd frontend && npm.cmd run build`：通过。

### 当前阶段

- **状态：** completed for 3-round Module F iteration
- **阶段名称：** 模块F：真实 LLM 测评与链路优化
- **下一步：** 可选执行完整 40 条真实 LLM 测评；若进入模块 G，则优先把 12 条阶段性真实测评摘要产品化展示。

## 会话：2026-07-18（模块F完成：Agent 测评与效果指标）

### 背景

用户要求参考 `doc/planning/task_plan.md` 完成模块 F，让系统能基于模块 E 的标注样本输出 Agent 分项指标和端到端效果指标。

### 执行内容

- 重构 `ai-engine/evaluation/evaluator.py`：从模块 E 阶段的演示分数改为可对真实 Agent 输出 records 计分，并保留 `/api/evaluation/metrics` 旧顶层字段兼容前端。
- 新增 Agent 分项指标：Classifier 意图/流程/优先级一致率，Intake 字段完整率/缺失字段识别率，Resolution 工具/参数/执行成功率，Notification 回单要点/模板合规/可读性规则评分，Escalation 异常识别/人工介入判断一致率。
- 新增端到端指标：闭环成功率、平均处理耗时、平均人工节省步骤、预计节省时间、评测来源和已评测样本数。
- 新增 `ai-engine/evaluation/run_module_f.py`：配置 LLM Key 后可逐条运行评测样本的五类 Agent 链路，不写主数据库。
- 新增 `ai-engine/evaluation/smoke_module_f.py`：用伪 Agent 输出覆盖自动成功、待补充、升级人工三类评测路径，避免 smoke 依赖真实 LLM。
- 扩展 `ai-engine/models/api_schemas.py`、`ai-engine/main.py` 和 `frontend/src/types/index.ts`，让 API 与前端类型能消费新增评测字段。
- 更新 `doc/planning/task_plan.md` 和 `doc/planning/findings.md`，将模块 F 标记为已完成并记录实现事实。

### 当前验证结果

- `.venv\Scripts\python.exe -m compileall ai-engine`：通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_f.py`：通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_e.py`：通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_a.py`：通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_b.py`：通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_c.py`：通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_d.py`：通过。
- `cd frontend && npm.cmd run build`：通过。

### 当前阶段

- **状态：** completed
- **阶段名称：** 模块F：Agent 测评与效果指标
- **下一步：** 进入模块 G：前端产品呈现，重点把评测摘要和业务流程展示给非技术观众看懂。

## 会话：2026-07-18（模块E完成：40条评测样本与读取校验）

### 背景

用户确认模块 E 的 MVP 样本量采用 40 条左右，而不是 20 条最小集；样本主要用于 Agent 效果评测、场景覆盖证明和后续回归测试，不作为模型训练数据。

### 执行内容

- 新增 `ai-engine/data/evaluation_samples.json`，包含 40 条中文模拟标注样本。
- 样本与 `ai-engine/data/tickets.json` 分离：Demo 种子数据继续用于页面演示，评测样本独立用于模块 E/F。
- 每条样本包含工单原文、正确意图、细分工单类型、workflow、必填字段、期望字段、期望工具、期望状态、期望处理结果、回单要点和是否需要人工介入。
- 样本前 20 条优先覆盖现有工具闭环：优惠券补发、申请进度查询、资料变更、权益资格核验、账单/交易查询和交易争议。
- 后 20 条覆盖后续扩展场景：分期提前结清、还款协商、挂失补卡、额度咨询、年费、积分、征信异议、投诉催办、跨部门协办等。
- 更新 `ai-engine/evaluation/evaluator.py`：支持读取新的 `expected` 样本结构，并保持旧字段兼容；在模块 F 接入真实 Agent 输出前，指标分数仍使用演示值，但 `total_samples` 来自真实样本。
- 更新 `/api/evaluation/metrics`：改为调用 `Evaluator.compute()`，保持前端返回字段不变。
- 新增 `ai-engine/evaluation/smoke_module_e.py`：校验样本数量、结构、脱敏、核心工具覆盖、状态覆盖、Demo/评测分离，以及评测器和指标 API 读取样本数量。
- 更新 `doc/planning/task_plan.md`，将模块 E 标记为已完成。

### 当前验证结果

- `.venv\Scripts\python.exe -m compileall ai-engine`：通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_e.py`：通过，确认 40 条样本可读取，且 `/api/evaluation/metrics` 返回 `totalSamples=40`。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_a.py`：通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_b.py`：通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_c.py`：通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_d.py`：通过。

### 当前阶段

- **状态：** completed
- **阶段名称：** 模块E：数据集构建与场景扩展
- **下一步：** 进入模块 F：Agent 测评与效果指标。

## 会话：2026-07-18（模块E启动：外部数据预检与迁移）

### 背景

用户准备开始模块 E：数据集构建与场景扩展，并提供本地下载数据目录 `C:\Users\heyunhui\Downloads\data`，要求先检查数据是否适用；如适用，先修改 `.gitignore` 停止追踪大文件数据集，再把相关数据移动到项目目录下。

### 执行内容

- 读取模块 E 计划、历史发现和进度，确认当前目标是构建 20-50 条可评测标注样本，并保持 Demo 种子数据与评测数据分离。
- 检查下载数据目录结构：包含 `external/`、`generated/`、`README.md`、`agent_cards.json`、`tickets.json`、`tools.json`。
- 预检 CFPB 数据：`cfpb_complaints.csv.zip` 约 1.42 GB，内部 `complaints.csv` 约 9.06 GB，字段适合生成金融投诉/信用卡争议类工单，但不是中文通话转写，后续需要抽样、脱敏确认、翻译/改写和补充标签。
- 预检 BANKING77 数据：`banking77_intents.json` 共 13,083 条，train 10,003 条、test 3,080 条，适合 Classifier/工具路由评测，但不是完整工单。
- 判断下载目录根部的 `agent_cards.json`、`tools.json`、`tickets.json` 为旧版小配置，不覆盖当前项目内已有新业务 Agent 和 5-tool 配置。
- 更新 `.gitignore`，新增忽略 `ai-engine/data/external/` 和 `ai-engine/data/generated/`。
- 将 `external/` 和 `generated/` 从 `Downloads\data` 移动到 `ai-engine/data/`；保留下载目录根部旧版小 JSON 和 README，避免误覆盖项目配置。
- 更新 `doc/planning/findings.md`，记录模块 E 数据源适用性判断。
- 同步更新 `doc/planning/task_plan.md`：模块 E 标记为进行中，补充数据源预检、`.gitignore` 忽略规则和数据迁移的已完成前置项。

### 当前验证结果

- `git check-ignore -v ai-engine/data/external/cfpb_complaints.csv.zip ai-engine/data/generated/banking77_intents.json`：命中新增忽略规则。
- `git status --short --ignored`：大数据目录显示为 ignored，未作为普通未跟踪文件进入 Git。

### 当前阶段

- **状态：** in_progress
- **阶段名称：** 模块E：数据集构建与场景扩展
- **下一步：** 基于 CFPB/BANKING77 抽样并手工或脚本化整理 20-50 条中文标注样本，字段覆盖通话记录/工单原文、意图、工单类型、必填字段、期望工具、处理结果、回单要点和是否人工介入。

## 会话：2026-07-18（模块D完成：Notification 与回单闭环）

### 背景

用户要求按 planning 继续完成模块 D，并执行计划直到测试通过、系统跑通、功能正常，同时使用其他 Agent 进行测试和审查。

### 执行内容

- 扩展 `AiProcessResult`：新增结构化 `notification`，包含标准回单、内部通知、复核摘要、结案建议和回访预留；保留 `replyDraft`/`reply_draft` 兼容旧前端和旧测试。
- 升级 `NotificationAgent`：支持结构化输出，LLM 失败或字段缺失时使用确定性 fallback，避免通知环节拖垮主流程。
- 改造 Orchestrator：低风险成功、待补充、待人工确认、工具失败/冲突/权限不足、高风险直升人工等终态均生成通知与复核摘要。
- 兼容迁移 `ai_results`：新增 `notification_json`、`final_reply`、`closed_at`，并让 `/close` 回写最终回单和结案时间。
- 前端新增通知闭环展示区：标准回单、内部通知、复核摘要、结案建议和回访预留；回单编辑器优先使用结构化标准回单。
- 新增 `ai-engine/evaluation/smoke_module_d.py`，覆盖模块 D 的核心回单、通知和结案追溯场景。
- 更新模块 C smoke 中升级路径的 Trace 预期，使其包含新增的 Notification Agent 终态通知。
- 子 Agent 审查发现两个 P1：LLM 可能伪造成功/可结案通知、人工拒绝分支缺少通知结构；已通过确定性归一规则和人工拒绝升级通知修复，并在模块 D smoke 中加入回归断言。

### 当前验证结果

- `.venv\Scripts\python.exe -m compileall ai-engine`：通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_a.py`：通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_b.py`：通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_c.py`：通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_d.py`：通过。
- `cd frontend && npm.cmd run build`：通过。

### 当前阶段

- **状态：** completed
- **阶段名称：** 模块D：Notification 与回单闭环
- **下一步：** 使用子 Agent 做最终测试和代码审查；如无 P0/P1 问题，进入模块 E：数据集构建与场景扩展。

## 会话：2026-07-18（模块C完成：Resolution 执行能力与工具审计）

### 背景

用户要求继续完成模块 C 代码，并使用子 Agent 进行代码审查、测试、debug 和优化，直到满足 `task_plan.md` 中模块 C 的要求清单。

### 执行内容

- 扩展 Mock Tool 到 5 类：补券、资料修改、交易查询、权益查询、进度查询。
- 扩展 `workflow_config`、Classifier、Intake、Escalation、Resolution 和 Agent Card，使 5 类场景都能被识别、抽取、校验和选择工具。
- 统一 `ToolResult` 返回结构：`action`、`business_result`、`evidence_id`、`next_step`、`requires_human`、`failure_reason`。
- 重构 `MockExecutor`，生成业务证据编号，并对权限、冲突、失败等业务异常标记人工复核。
- 重构 Orchestrator 工具执行链：执行前缺参校验，缺参时生成补充提示并暂停；执行后再次调用 Escalation Agent 做失败、冲突、权限和人工复核判断。
- 补齐工具审计：Orchestrator 路径写 `tool_call_log`，直接工具调试接口在传入 `ticketId` 时也写审计。
- 新增 `GET /api/tickets/{ticket_id}/tool-calls` 只读审计接口。
- 前端新增业务执行审计展示：工具名、关键入参、业务结果、证据编号、下一步建议、是否需人工、失败原因。
- 前端新增当前工单页“页面助手”，仅支持本页低风险动作：填入回单、检查风险、定位工具、滚动审核区。
- 修复详情页刷新/路由切换后不恢复 AI 结果、可能操作错工单，以及 `AppSidebar` 未显式导入的问题。
- 新增 `ai-engine/evaluation/smoke_module_c.py`，覆盖 5 类工具、工具审计接口、缺参暂停、失败升级、业务冲突升级和直接工具接口审计。

### 子 Agent 审查与修复

- 后端子 Agent 发现直接工具接口绕过审计、缺参缺少客户可读补充提示、成功但业务冲突时可能跳过升级；已全部修复并加回归断言。
- 前端子 Agent 发现刷新后不恢复 AI 结果、路由切换与 store 状态可能脱节、`AppSidebar` 未导入；已全部修复。
- 子 Agent 未发现 P0 问题。

### 验证结果

- `.venv\Scripts\python.exe -m compileall ai-engine`：通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_a.py`：通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_b.py`：通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_c.py`：通过。
- `cd frontend && npm.cmd run build`：通过。

### 当前阶段

- **状态：** completed
- **阶段名称：** 模块C：Resolution 执行能力与工具审计
- **下一步：** 进入模块D：Notification 与回单闭环；重点把工具结果、证据编号、人工复核原因转成更标准的客户回单、内部通知和结案建议。

## 会话：2026-07-17（模块B完成：业务 Agent 受控重构）

### 背景

用户要求按照计划完成模块 B 代码，并使用子 Agent 进行代码审查、测试、debug 和优化，直到满足 `task_plan.md` 中模块 B 的要求清单。

### 执行内容

- 新增业务 Agent 文件：`classifier_agent.py`、`intake_agent.py`、`escalation_agent.py`、`resolution_agent.py`、`notification_agent.py`。
- 将旧 `intent_agent.py`、`extract_agent.py`、`verify_agent.py`、`tool_agent.py`、`reply_agent.py` 改为短期兼容 shim。
- 更新 Orchestrator：使用新业务 Agent 属性和 `agentId`，Trace/SSE 改为 `classifier_agent`、`intake_agent`、`escalation_agent`、`resolution_agent`、`notification_agent`。
- 新增 `ai-engine/data/workflow_config.json` 和 `orchestrator/workflow_config.py`，描述场景、必填字段、推荐工具、人工确认策略和通知模板。
- 更新 `agent_cards.json` 为新业务 Agent Card 和依赖关系。
- 更新前端流程条、Trace 标题、AI 结果卡片、人工确认提示等业务化文案，并让 SSE `agent_complete.status` 可驱动失败状态。
- 更新 `doc/guides/启动与使用指南.md` 的演示轨迹、目录结构、架构流程和新增场景说明。
- 新增 `ai-engine/evaluation/smoke_module_b.py`，覆盖新 Agent ID、`pausedAt=escalation_agent`、高风险升级、旧 shim、workflow_config fallback、Classifier fallback 和 Agent 异常 Trace 失败状态。
- 通过子 Agent 做后端只读审查，并修复：
  - `workflow_config` 加载失败缺少内置 fallback。
  - Classifier 缺失或异常 `workflow_name/type` 时回填不稳。
  - Agent 抛异常时 Trace/SSE 可能保留 RUNNING 状态。
- API 级验证发现 `/api/agent-cards` 仍返回 snake_case 字段，已将 `AgentCard` 接入统一 camelCase API 模型。

### 验证结果

- `.venv\Scripts\python.exe -m compileall ai-engine`：通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_a.py`：通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_b.py`：通过。
- `cd frontend && npm.cmd run build`：通过。
- 临时数据库 + FastAPI TestClient 验证 `GET /api/tickets`、`GET /api/agent-cards`、`GET /api/tools` 均返回 200，且 Agent Card 对外字段为 `agentId`、`inputSchema`。
- Agent Registry 当前加载顺序为 `classifier_agent -> intake_agent -> escalation_agent -> resolution_agent -> notification_agent`。
- `workflow_config` 可加载三类核心场景和 `UNKNOWN` 兜底，旧 Agent shim 继承关系验证通过。

### 当前阶段

- **状态：** completed
- **阶段名称：** 模块B：Agent 编排与业务化封装
- **下一步：** 进入模块C：Resolution 执行能力与工具审计；重点梳理 Mock Tool、统一工具返回结构、强化工具参数缺失和失败升级链路。

## 会话：2026-07-17（模块B实施策略调整：受控重构新业务 Agent）

### 背景

用户质疑单独增加 Agent 映射层是否冗余，并提出相比维护 `IntentAgent -> ClassifierAgent` 这类翻译关系，是否更适合直接把旧 Agent 重构为新业务 Agent。

### 执行内容

- 读取 `planning-with-files-zh` 技能说明。
- 重新读取 `doc/planning/task_plan.md`、`doc/planning/findings.md`、`doc/planning/progress.md`。
- 更新 `doc/planning/task_plan.md`：将模块 B 从“映射/adapter 方案”调整为“代码层受控重构为新业务 Agent”。
- 更新 `doc/planning/findings.md`：记录映射层在当前 Demo 阶段偏冗余，模块 B 改为受控重构。
- 明确旧 Agent 文件短期保留为兼容 shim，模块 B/C 稳定后再评估删除。
- 明确模块 A 不重新开发；模块 B 完成后只做 API、SSE 终态、状态机、持久化和工具审计契约的回归验证。

### 当前共识

- 模块 B 采用受控重构，不长期维护单独业务映射层。
- 新 Agent 代码命名目标：`ExtractAgent -> IntakeAgent`、`IntentAgent -> ClassifierAgent`、`ToolCallingAgent -> ResolutionAgent`、`ReplyAgent -> NotificationAgent`、`VerifyAgent -> EscalationAgent`。
- 旧文件短期作为兼容 shim，避免测试或旧导入立刻断裂。
- 模块 A 不重做；模块 B 必须保持模块 A 契约不变，并通过模块 A smoke 回归。

### 当前阶段

- **状态：** in_progress
- **阶段名称：** 模块B：Agent 编排与业务化封装
- **当前任务：** 按受控重构方案统一代码层、Trace、前端和文档中的业务 Agent 命名。
- **下一步：** 开始模块 B 代码改造：新增业务 Agent 文件、旧文件改兼容 shim、调整 Orchestrator/Agent Card/前端流程条，并补充模块 B smoke 测试。

## 会话：2026-07-17（Page Agent 进阶路线补充）

### 背景

用户希望在计划中补充 Page Agent 的推荐引入方式：不要直接做外部系统自动化，而是分阶段从低风险页面助手开始。

### 执行内容

- 更新 `doc/planning/task_plan.md` 的进阶模块，加入 Page Agent 三阶段路线。
- 更新 `doc/planning/findings.md`，补充 Page Agent 推荐引入路线和安全边界。
- 保持 `doc/planning/任务顺序.md` 不变。

### 当前共识

- 第一阶段：在 `frontend/src/views/TicketDetailView.vue` 增加“页面助手”入口，只操作当前工单详情页。
- 第二阶段：动态工单表单完善后，将 Intake Agent/ExtractAgent 抽取结果转成发单/回单页面填充动作。
- 第三阶段：只有在行内系统没有 API 时，才考虑 Page Agent Ext / MCP 操作外部浏览器页面。
- 外部遗留系统自动化属于高风险能力，必须有白名单、脱敏、审计和人工确认。
## 会话：2026-07-17（planning 文件按新 Agent 方案重构）

### 背景

用户对原 planning 不满意，主要原因：

- 低/中/高风险分级不应作为核心模块强调，它只是业务策略细节。
- 原 Agent 划分偏技术实现，不如 Intake、Classifier、Dispatcher、Resolution、Notification、Escalation 这套业务命名适合工单场景和答辩表达。
- Resolution Agent 中的接口调用、MCP、PageAgent 体现不够明确。
- 只考虑 3 类业务场景不足，需要更多工单场景支撑数据集和测评。
- 本轮只重构 `doc/planning/任务顺序.md` 以外的 planning 文件。

### 执行内容

- 读取 `planning-with-files-zh` 技能说明。
- 读取当前 `doc/planning/task_plan.md`、`doc/planning/findings.md`、`doc/planning/progress.md`、`doc/planning/任务顺序.md`。
- 读取 `doc/design/` 下现有设计文档，确认旧技术型 Agent 口径仍有残留。
- 保留 `doc/planning/任务顺序.md` 不变。
- 重写 `doc/planning/task_plan.md`：改为核心闭环开发路线，采用新业务 Agent 分类。
- 重写 `doc/planning/findings.md`：记录新旧 Agent 方案对比、是否重构、编排取舍、场景扩展和产品形态判断。
- 重写 `doc/planning/progress.md`：记录本次 planning 重构背景、执行内容、当前共识和下一步。

### 当前共识

- 新业务 Agent 主口径：Intake、Classifier、Resolution、Notification、Escalation。
- Dispatcher Agent 难度较高，先作为进阶模块，不进入当前核心闭环。
- 当前代码不长期维护映射层，模块 B 采用受控重构，旧 Agent 文件短期保留为兼容 shim。
- Resolution Agent 必须明确包含 API/Mock Tool 调用和审计证据；MCP 与 PageAgent 是进阶扩展。
- 风险分级不再作为核心模块，只作为分类、执行和升级策略中的细节。
- 工单场景需要扩展到 10 类以上，用于数据集和测评，而不是只围绕 3 个固定 Demo。
- 当前仍优先手写 Orchestrator + 轻量 `workflow_config`，暂不迁移 LangGraph。

### 当前阶段

- **状态：** in_progress
- **阶段名称：** 新 Agent 方案规划收口
- **当前任务：** 将规划文件对齐到业务型 Agent 编排，为后续代码开发提供稳定导航。
- **下一步：** 开始代码开发前，先检查 AGENTS.md、design 文档和前端 Trace 文案是否也需要同步到新 Agent 口径。

## 历史基线摘要

### 2026-07-16 初版系统建设

- 完成 FastAPI 后端、SQLite 数据库、5 个技术型 Agent、Tool Registry、MockExecutor、手写 Orchestrator、SSE Trace、Vue 前端工作台。
- 完成启动指南、规划文件、AGENTS.md、.gitignore。
- 已重新初始化 Git，并完成初始提交：`64535e6 Initial TicketAgent project snapshot`。

### 2026-07-17 文档目录整理

- `doc/` 已整理为 requirements、design、guides、demo、planning 等子目录。
- 新增 `doc/README.md` 作为文档索引。
- Demo 讲解稿已转向面向产品经理、客户和领导的业务表达。
- `doc/guides/vibe-coding指南.md` 已创建，用于通用 AI coding 工作流。

## 已验证能力

| 能力 | 状态 |
|------|------|
| 后端基础服务 | 已完成初版 |
| SQLite 数据库 | 已完成初版 |
| Agent Registry 加载旧 5-Agent | 已完成初版 |
| Tool Registry 和 MockExecutor | 已完成初版 |
| 手写 Orchestrator | 已完成初版 |
| SSE 实时 Trace | 已完成初版，仍需契约稳定 |
| Vue 前端工作台 | 已完成初版 |
| Git 初始提交 | 已完成 |
| 新业务 Agent 规划 | 本轮重构中 |

## 后续进度更新规则

每完成一个模块后更新本文件：

- 写明日期、阶段、完成内容。
- 记录修改的文件。
- 记录运行过的测试，或无法运行的原因。
- 记录遇到的问题和解决方式。
- 如果阶段状态变化，同步更新 `task_plan.md`。
- 如果 Agent 命名、流程顺序或验收标准变化，必须同步更新 `findings.md`。

## 五问重启检查

| 问题 | 当前答案 |
|------|----------|
| 我在哪里？ | 模块 A 和模块 B 已完成，系统已统一到业务 Agent 命名和轻量 workflow_config |
| 我要去哪里？ | 进入模块 C，强化 Resolution 执行能力、工具审计和失败兜底 |
| 目标是什么？ | 做出可演示、可测评、可解释的信用卡工单智能处理系统 |
| 我学到了什么？ | 受控重构比长期映射层更适合当前项目；workflow_config 需要内置 fallback，Agent 失败 Trace 也要明确落为 FAILED |
| 我做了什么？ | 完成模块 B 代码改造、前端和文档同步、模块 A/B smoke 回归、前端构建和子 Agent 审查修复 |

## 会话：2026-07-17（模块A完成：后端契约与状态稳定化）

### 背景

用户要求根据 planning 继续开发，优先完成模块A，并通过子 Agent 做代码审查和优化，确保系统能跑通。

### 执行内容

- 稳定 API 对外契约：`TicketResponse`、`AiProcessResult`、`ToolDefinition`、`ToolResult`、`ProcessTicketResponse` 对外统一 camelCase。
- 新增 `POST /api/tickets`，补齐工单创建入口。
- 扩展工单状态：新增 `pending_info`、`failed`，并统一 `workflow_complete`、`workflow_paused`、`workflow_escalated`、`workflow_failed` 四类 SSE 终态。
- 补齐 AI 结果结构化持久化字段，记录 workflow、intent、fields、tool request/response、evidence、reply、status、duration、failure reason。
- 工具调用通过 Orchestrator 写入 `tool_call_log`，记录成功/失败、证据编号、耗时和失败原因。
- 人工拒绝确认会写入 trace 和 `ai_results`，不再只改工单状态。
- 中风险人工确认接口增加状态前置校验，避免重复确认导致重复执行工具。
- 前端 Pinia store 同步消费新 SSE 终态；只有 `pauseType=human_confirm` 时才弹人工确认框，信息不足暂停不再误弹确认。
- 新增 `ai-engine/evaluation/smoke_module_a.py`，用临时 SQLite 和伪 Agent 覆盖自动处理、信息不足、人工确认、人工拒绝、工具失败、升级人工和旧状态 CHECK 迁移。
- 使用两个子 Agent 做只读代码审查，修复了 trace alias、SSE 先发终态后落库、确认接口重复执行、人工拒绝未持久化等问题。

### 验证结果

- `.venv\Scripts\python.exe -m compileall ai-engine`：通过。
- `.venv\Scripts\python.exe ai-engine\evaluation\smoke_module_a.py`：通过。
- `cd frontend && npm.cmd run build`：通过。
- 临时数据库启动后端，`GET /api/tickets`、`GET /api/tools`、`GET /docs`：均返回 200。
- 临时数据库调用 `POST /api/tickets/dispute/ai-process`：返回 `status=escalated`、`terminalEvent=workflow_escalated`、trace 使用 `agentId`。
- `GET /api/tickets/dispute/ai-result`：可读取最新持久化 AI 结果。
- 前端 dev server 已验证首页返回 200。

### 当前阶段

- **状态：** completed
- **阶段名称：** 模块A：后端契约与工单状态稳定化
- **下一步：** 进入模块B：Agent 编排与业务化封装。

## 会话：2026-07-19（模块F漏勾状态核对）

### 背景

用户发现 `doc/planning/task_plan.md` 的模块 F 中仍有一条“预检链路稳定后执行完整 40 条真实 LLM 测评”未勾选，要求检查是否已经可以勾选。

### 核对结果

- 已确认最终真实 LLM 全量测评产物存在：`ai-engine/evaluation/module_f_full_final3_20260719.json`。
- 产物指标显示 `source=agent_run`、`evaluated_samples=40`、`intent_accuracy=1.0`、`closed_loop_success_rate=1.0`。
- 模块 F+ 中已记录最终 40 条真实 LLM 回归结果和收口结论。

### 执行内容

- 将模块 F 中“预检链路稳定后执行完整 40 条真实 LLM 测评”标记为已完成。
- 修正旁边过期的“本轮未跑完整 40 条”历史表述，改为引用最终 F+ 全量测评产物。
