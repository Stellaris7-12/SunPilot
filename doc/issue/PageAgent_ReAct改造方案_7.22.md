# PageAgent ReAct 改造方案：MVP fork 方案

> 上游源码：`C:\Users\heyunhui\OtherProjects\page-agent-main`
>
> 当前改造代码：`frontend/src/page-agent/`
>
> 策略：复制 Ali page-agent 核心引擎，不加安全层，给予 PageAgent 最大自主性。仅替换 React Panel 为 Vue 版本、新增 LLM 代理端点、保留 SSE 桥接。

---

## 一、MVP 放弃什么，保留什么

| 放弃 | 原因 |
|---|---|
| PolicyLayer 硬约束 | 不加白名单校验、不拦截任何 LLM 输出的 action |
| customTools 语义定位重写 | 直接用原 `click_element_by_index` / `input_text`，让 LLM 自己看 DOM index |
| 风险分级 + 确认门控 | Demo 全自动，不暂停等人工 |
| PageActionLog 审计 | 不做持久化 |

| 保留 | 原因 |
|---|---|
| PageAgentCore ReAct 循环 | 核心引擎，所有能力来源 |
| PageController + DOM 脱水 + W3C 动作 | LLM 的"眼睛和手" |
| SimulatorMask 鼠标动画 | Demo 视觉效果 |
| execute_javascript 工具 | **兜底逃生舱** — 标准工具失败时 LLM 可换 JS 执行，避免 demo 卡住 |
| Vue Panel | 替代 React Panel，嵌入右侧栏 |
| LLM proxy | 不暴露 API Key |
| SSE bridge | 后端多 Agent 结果 → observation 注入 |

**核心思路**：PageAgentCore 本身就是完整的通用网页 Agent。MVP 只需给它一个任务描述（如"在发单表单填入客户号 C88123，场景选优惠券补发，点击提交"），它自己会观察 DOM、自己决策每步做什么。我们不需要 PolicyLayer 做意图路由和计划生成——page-agent 原生就做这件事。

---

## 二、方案对比

| 维度 | 从零重写 | Fork + 完整安全 | **Fork MVP（选这个）** |
|---|---|---|---|
| 需新写代码 | ~1400 行 | ~470 行 | **~250 行** |
| PolicyLayer | — | ~200 行（LLM路由+硬约束） | **删除，不需要** |
| tools 改造 | 全部重写 | 重写语义定位 | **不改，用原 DOM index** |
| Vue Panel | — | ~150 行 | ~150 行 |
| 安全性 | — | 白名单 + 风险分级 | **无（MVP 接受风险）** |
| LLM 调用 | — | 意图+计划+调整 共3-5次 | **仅 ReAct 循环本身（5-10步）** |
| 工作量 | 20h+ | ~10h | **~7h** |

---

## 三、具体方案

### 3.1 复制（从上游直接迁移）

从 `C:\Users\heyunhui\OtherProjects\page-agent-main\packages` 复制以下文件到 `frontend/src/page-agent/`，**不修改业务逻辑**：

| 上游路径 | 目标路径 | 行数 | 说明 |
|---|---|---|---|
| `core/src/PageAgentCore.ts` | `core/PageAgentCore.ts` | 661 | ReAct 循环引擎 |
| `core/src/types.ts` | `core/types.ts` | 285 | AgentConfig、StepEvent |
| `core/src/utils/index.ts` | `core/utils.ts` | 143 | uid、waitFor |
| `core/src/utils/autoFixer.ts` | `core/autoFixer.ts` | 216 | LLM 返回修复 |
| `core/src/tools/index.ts` | `tools/index.ts` | 202 | 8 个内置工具 |
| `llms/src/index.ts` | `llm/LLM.ts` | 109 | LLM 调用入口 |
| `llms/src/OpenAIClient.ts` | `llm/OpenAIClient.ts` | 269 | OpenAI 兼容客户端 |
| `llms/src/types.ts` | `llm/types.ts` | 127 | LLM 配置类型 |
| `llms/src/utils.ts` | `llm/utils.ts` | 235 | token、重试 |
| `llms/src/errors.ts` | `llm/errors.ts` | 56 | 错误类型 |
| `page-controller/src/PageController.ts` | `controller/PageController.ts` | 435 | DOM 状态+操作 |
| `page-controller/src/actions.ts` | `controller/actions.ts` | 554 | W3C 点击/输入/滚动 |
| `page-controller/src/dom/index.ts` | `controller/dom.ts` | 569 | DOM 树+脱水 |
| `page-controller/src/dom/getPageInfo.ts` | `controller/pageInfo.ts` | 42 | 页面尺寸 |
| `page-controller/src/dom/dom_tree/type.ts` | `controller/domTreeTypes.ts` | 51 | DOM 树类型 |
| `page-controller/src/dom/dom_tree/index.d.ts` | `controller/domTreeIndex.d.ts` | 16 | 类型声明 |
| `page-controller/src/utils/index.ts` | `controller/utils.ts` | 80 | 指针/焦点 |
| `page-controller/src/mask/SimulatorMask.ts` | `controller/SimulatorMask.ts` | 216 | 鼠标动画 |
| `page-controller/src/mask/SimulatorMask.module.css` | `controller/SimulatorMask.module.css` | 13 | 遮罩样式 |
| `page-controller/src/mask/cursor.module.css` | `controller/cursor.module.css` | 70 | 光标样式 |
| `page-controller/src/mask/checkDarkMode.ts` | `controller/checkDarkMode.ts` | 181 | 暗色模式 |
| `page-controller/src/patches/react.ts` | `controller/patches/react.ts` | 16 | React 补丁（保留，不影响 Vue） |

导入路径整理（`@page-agent/llms` → `../llm/LLM` 等）是纯机械工作。

### 3.2 不引入的部分

| 不引入 | 原因 |
|---|---|
| `ui/Panel.ts`（React） | 用 Vue 重写 |
| `page-agent/src/PageAgent.ts` | 用我们自己的工厂函数 |
| `patches/antd.ts` | 不使用 Ant Design |
| `extension/` `mcp/` `website/` | 单页面场景不需要 |

### 3.3 新增（TicketAgent 独有，~250 行）

**a) 极简工厂函数（~30 行）**

```typescript
// frontend/src/page-agent/index.ts
// 替代 page-agent/src/PageAgent.ts

import { PageAgentCore } from './core/PageAgentCore'
import { PageController } from './controller/PageController'

export function createTicketPageAgent() {
  const controller = new PageController({ enableMask: true })
  return new PageAgentCore({
    pageController: controller,
    model: 'qwen3.7-plus',
    baseURL: '/api/llm/proxy',
    language: 'zh-CN',
    maxSteps: 15,
    stepDelay: 0.8,
  })
}
```

**和原 `PageAgent` 类的差异**：去掉了 Panel 自动挂载（我们的 Vue Panel 单独挂载），去掉了 demo 模式，去掉了 `promptForNextTask`。

**b) Vue Panel 组件（~150 行）**

替代 React 的 `ui/Panel.ts`（697 行）：

- 挂载在工单详情页右侧栏（`operator-col`），嵌入页面布局
- 输入框 + 发送按钮 + 停止按钮
- 监听 `PageAgentCore` 的事件实时渲染步骤流：

| 事件 | UI |
|---|---|
| `activity: thinking` | "🧠 思考中..." |
| `activity: executing` | "🖱 {动作}" |
| `activity: executed` | "✅ {结果} · {耗时}ms" |
| `activity: error` | "❌ {错误}" |
| `statuschange: completed` | 最终总结卡片 |
| `statuschange: stopped` | "⏸ 已停止" |

- CSS 复用上游 Teal (`#0f766e`) + Amber (`#f59e0b`) 色系，和 SimulatorMask 保持视觉一致

**c) 后端 LLM 代理（~20 行）**

`POST /api/llm/proxy/chat/completions`（兼容 `POST /api/llm/proxy`）— 前端 `OpenAIClient` 通过此端点调 LLM，baseURL 配置为 `/api/llm/proxy`。PageAgent 专用代理使用本地环境变量 `ALI_API_KEY`，模型默认 `qwen3.7-plus`，与后端五个业务 Agent 的 DeepSeek/`LLM_*` 配置分离。

**d) SSE bridge（~40 行）**

`watch(store.aiResult)` + `watch(store.traceSteps)` → `pageAgent.pushObservation()`。后端多 Agent 的执行结果和进度注入到 PageAgent 的 observation 流中，PageAgent 感知到 AI 处理完成后可自动继续操作。

---

## 四、改造后目录

```text
frontend/src/page-agent/
├── index.ts                          ← 工厂函数 (~30行)
│
├── core/                             ← 从上游复制
│   ├── PageAgentCore.ts              ← ReAct 循环 (661行)
│   ├── types.ts
│   ├── utils.ts
│   └── autoFixer.ts
│
├── tools/                            ← 从上游复制（不改）
│   └── index.ts                      ← done/wait/ask_user/click/input/
│                                       select/scroll/execute_javascript
│
├── llm/                              ← 从上游复制
│   ├── LLM.ts / OpenAIClient.ts / types.ts / utils.ts / errors.ts
│
├── controller/                       ← 从上游复制
│   ├── PageController.ts / actions.ts / dom.ts / pageInfo.ts
│   ├── domTreeTypes.ts / domTreeIndex.d.ts / utils.ts
│   ├── SimulatorMask.ts + .module.css
│   ├── cursor.module.css / checkDarkMode.ts
│   └── patches/react.ts
│
├── panel/                            ← 新增（替代 React Panel）
│   └── AgentPanel.vue               ← Vue 对话面板 (~150行)
│
├── bridge.ts                         ← 新增（SSE → observation, ~40行）
└── README.md
```

**关键变化**：没有 `policy/` 目录（PolicyLayer 整个移除），没有 `tools/` 改造（全用原版）。

---

## 五、核心架构：PageAgent 如何贯穿发单和回单

### 5.1 双脑通信机制

PageAgent 不触发后端多 Agent 管道（不点"AI处理"按钮）。后端 Agent 的触发和结果传递是两个独立链路：

```text
发单侧:
  坐席选通话记录 → 发单Agent(后端) → ticketDraft → Store 更新
    → bridge watch 检测到 draft → pushObservation(
        "发单Agent已生成工单草稿: 客户=王小明, 客户号=C88123,
         场景=优惠券补发, 标题=618活动达标50元优惠券未到账...
         请打开发单表单并填入以上字段。"
      )
    → PageAgentCore ReAct 循环下一轮看到此 observation
    → LLM 自主决策: "需要打开发单表单，然后逐个填入字段"
    → 执行: 导航 → input → input → ... → click submit

回单侧:
  坐席点"AI处理"按钮 → 多Agent管道(后端) → AiProcessResult → Store 更新
    → bridge watch 检测到 aiResult → pushObservation(
        "后端AI处理完成: 场景=优惠券补发, 风险=低, 缺失字段=无,
         回单草稿=尊敬的王小明客户...(186字),
         证据编号=EVID-001/EVID-002, 可结案=是。
         请填入回单编辑器并定位证据。"
      )
    → PageAgentCore ReAct 循环下一轮看到此 observation
    → LLM 自主决策: "回单草稿有了，填入编辑器，然后滚动到证据区"
    → 执行: input + scroll + highlight
```

**关键**：PageAgent 不知道"发单Agent"和"多Agent管道"的存在。它只知道 observation 流里出现了数据，该做页面操作了。后端 Agent 和 PageAgent 通过 observation 文本解耦——没有 API 契约，没有结构化接口，只有一段 LLM 天生能理解的自然语言描述。

### 5.2 bridge 的核心工作

把结构化数据转为 LLM 友好的文本。这不是 PolicyLayer，不需要规则引擎——只需要把关键字段拼成一句话：

| 数据来源 | observation 文本示例 |
|---|---|
| 发单草稿 | "发单Agent已生成草稿：客户姓名=王小明, 客户号=C88123, 场景=优惠券补发, 标题=618活动达标未到账。请打开发单表单并填入。" |
| AI 处理完成 | "后端AI处理完成：场景=优惠券补发, 风险=低, 回单草稿已生成(186字), 证据=EVID-001, 可结案。请填入回单编辑器。" |
| 处理进度 | "🔄 ClassifierAgent: 已识别为优惠券补发场景 (2.1s)" → panel 实时展示 |
| 暂停确认 | "⚠️ 流程已暂停，需要人工确认。请告知坐席查看确认对话框。" |

### 5.3 为什么不需要 PolicyLayer

page-agent 的设计就是"给一段自然语言任务描述，自己看 DOM，自己决策，自己执行"。我们不需要把 AiProcessResult 映射为 PageTaskPlan.steps[] —— 那是替 LLM 做决定。LLM 看到 observation 里的数据 + 当前页面的 DOM 脱水文本，自己就能决定"填什么、先填哪个、点什么、滚到哪"。

MVP 的策略是：**信息给够，信任 LLM，不加中间层。**

---

## 六、关于 execute_javascript 工具

原 page-agent 默认禁用（`experimentalScriptExecutionTool: false`）。MVP 建议保留它但默认关闭——标准工具（click_element_by_index、input_text）通过 W3C PointerEvent 序列通常能正常触发 Vue 的事件。如果 demo 调试时发现某个按钮反复点不中，临时开启作为逃生舱：

```text
标准工具失败: click_element_by_index(3) → Vue @click 未触发 → LLM 重试3次 → 步数浪费
逃生舱:        execute_javascript → document.querySelector(...).click() → 成功
```

`execute_javascript` 需要 `experimentalScriptExecutionTool: true` 才会暴露给 LLM。

---

## 七、工作量

| 任务 | 工作量 |
|---|---|
| 复制 22 个源文件 + 修改导入路径 | 1.5h |
| Vue AgentPanel 组件 | 1.5h |
| 极简工厂函数 | 0.5h |
| SSE bridge | 0.5h |
| 后端 `/api/llm/proxy` | 0.5h |
| 调通 + Demo 流程调试 | 2.5h |
| **合计** | **~7h** |

---

## 八、License

上游 `page-agent-main` 为 MIT License。复制到 `frontend/src/page-agent/` 的文件保留原版权声明。`README.md` 中注明来源。新增文件（`index.ts`、`panel/AgentPanel.vue`、`bridge.ts`）为原创。
