# TicketAgent 前端代码导览

这份文档面向刚开始接触 Vue 前端的开发者，帮助你从 `frontend/src/` 读懂这个信用卡工单多 Agent 工作台的代码结构、页面组织、数据流和常见 Vue 写法。

## 技术栈

- Vue 3：页面和组件框架，当前项目主要使用 `<script setup lang="ts">` 和 Composition API。
- TypeScript：给接口数据、组件 props、store 状态提供类型约束。
- Vite：开发服务器和前端构建工具。
- Vue Router：管理 `/tickets` 和 `/tickets/:id` 两个页面路由。
- Pinia：前端全局状态管理，保存工单列表、当前工单、AI 处理结果和 Trace。
- Axios：调用 FastAPI 后端接口。
- EventSource/SSE：接收 AI 多 Agent 流程的实时事件。

## 常用命令

```powershell
cd frontend
npm install
npm run dev
npm run build
```

开发时前端默认由 Vite 启动，后端 API 当前写死为 `http://localhost:8000/api`，所以需要同时启动后端服务。

## src 目录一眼看懂

```text
src/
  main.ts                  # 创建 Vue 应用，安装 Pinia 和 Router，挂载到 index.html
  App.vue                  # 根组件，只负责放置 router-view
  router/index.ts          # 页面路由配置
  api/index.ts             # 后端 API 封装
  stores/ticket.ts         # 工单业务的 Pinia store
  types/index.ts           # 前后端数据契约的 TypeScript 类型
  utils/business.ts        # 状态、风险、场景、指标等业务展示辅助函数
  assets/                  # 全局样式和静态图片
  views/                   # 页面级组件
  components/              # 可复用业务组件
```

## 应用启动流程

入口在 `src/main.ts`：

1. `createApp(App)` 创建 Vue 应用实例。
2. `app.use(createPinia())` 安装 Pinia，使所有组件能使用 store。
3. `app.use(router)` 安装 Vue Router，使 URL 能映射到页面。
4. `app.mount('#app')` 把 Vue 应用挂到 `index.html` 的 `<div id="app"></div>`。

`src/App.vue` 很薄，只写了：

```vue
<template>
  <router-view />
</template>
```

`router-view` 是路由出口。当前 URL 匹配到哪个页面组件，这里就渲染哪个页面。

## 页面路由

`src/router/index.ts` 定义了三个路由：

| 路径 | 页面 | 作用 |
| --- | --- | --- |
| `/` | redirect | 自动跳转到 `/tickets` |
| `/tickets` | `TicketListView.vue` | 工单工作池首页，展示待处理队列和评测摘要 |
| `/tickets/:id` | `TicketDetailView.vue` | 单个工单处理台，展示详情、AI 流程、回单和工具审计 |

路由组件使用懒加载：

```ts
component: () => import('../views/TicketDetailView.vue')
```

这样页面代码会按需加载，首屏包更小。

## 数据流

这个前端的核心数据流可以这样理解：

```text
页面组件
  -> 调用 useTicketStore()
  -> store 调用 api/index.ts
  -> FastAPI 后端返回 Ticket / AiProcessResult / TraceStep
  -> store 更新 ref/computed 状态
  -> Vue 自动重新渲染组件
```

AI 实时处理流程稍微特殊：

```text
点击“启动 AI 辅助”
  -> TicketDetailView 调用 store.startAiProcess(ticketId)
  -> store 创建 EventSource 连接 /ai-process-stream
  -> 后端持续推送 agent_start / agent_thinking / agent_complete 等事件
  -> store 更新 traceSteps、aiResult、replyDraft、workflowPaused
  -> 页面实时显示处理链路和最终回单建议
```

## 每个 src 文件的作用

### 根目录文件

| 文件 | 作用 |
| --- | --- |
| `src/main.ts` | 应用入口，创建 Vue app，安装 Pinia 和 Router，引入全局 CSS。 |
| `src/App.vue` | 根组件，目前只提供 `<router-view />`，具体布局放在页面组件里。 |
| `src/vite-env.d.ts` | Vite 自动生成/使用的类型声明，让 TypeScript 认识 Vite 环境变量和资源导入。 |

### router

| 文件 | 作用 |
| --- | --- |
| `src/router/index.ts` | 配置前端路由，负责 URL 与页面组件之间的映射。 |

### api

| 文件 | 作用 |
| --- | --- |
| `src/api/index.ts` | 用 Axios 封装后端接口，包括工单列表、工单详情、AI 结果、Trace、工具目录、评测指标、确认敏感操作、结案等。 |

主要对象：

- `ticketApi`：工单相关接口。
- `agentApi`：Agent Card 列表接口。
- `toolApi`：工具目录和工具执行接口。
- `evalApi`：评测指标接口。

### stores

| 文件 | 作用 |
| --- | --- |
| `src/stores/ticket.ts` | 全局工单状态中心。页面和组件不直接到处请求后端，而是通过这个 store 统一加载、选择、处理和关闭工单。 |

里面的关键状态：

- `tickets`：工单列表。
- `selectedTicketId`：当前选中的工单 ID。
- `selectedTicket`：由 `tickets` 和 `selectedTicketId` 计算出来的当前工单。
- `isProcessing`：AI 流程是否运行中。
- `aiResult`：后端返回的结构化 AI 处理结果。
- `traceSteps`：多 Agent 执行轨迹。
- `replyDraft`：坐席最终复核和提交的回单草稿。
- `workflowPaused`：是否因为人工确认而暂停。

关键动作：

- `fetchTickets()`：加载工单列表。
- `loadTicketContext(id)`：进入详情页时加载 AI 结果和 Trace。
- `startAiProcess(id)`：打开 SSE，实时接收 AI 流程事件。
- `confirmAction(id, approved)`：处理敏感动作人工确认。
- `closeTicket(id, finalReply)`：提交最终回单并结案。

### types

| 文件 | 作用 |
| --- | --- |
| `src/types/index.ts` | 定义前后端共享的数据形状。它不是运行时代码，而是给 TypeScript 检查使用。 |

重要类型：

- `Ticket`：工单基础信息。
- `TicketStatus`：工单状态枚举。
- `TraceStep`：Agent 执行步骤。
- `AiProcessResult`：AI 处理总结果。
- `NotificationBundle`：结构化通知、回单、复核摘要和结案建议。
- `ToolDefinition` / `ToolResult` / `ToolCallLog`：业务工具目录、执行结果和审计记录。
- `EvaluationMetrics`：评测指标。

### utils

| 文件 | 作用 |
| --- | --- |
| `src/utils/business.ts` | 把后端状态和业务字段转换成前端展示需要的文案、颜色、分组、建议动作和格式化结果。 |

常见函数：

- `statusMeta(status)`：把状态转成标签、颜色和说明。
- `riskMeta(riskLevel, riskLabel)`：把风险等级转成展示信息。
- `scenarioFamily(ticket, result)`：识别工单业务场景族。
- `workBuckets(tickets)`：统计侧边栏/首页工作池数量。
- `bucketMatches(bucket, ticket)`：判断工单是否属于某个筛选桶。
- `businessSteps(traceSteps, result, processing)`：把底层 Agent Trace 转成业务处理链路。
- `evidenceIds(result)`：从多个位置提取证据编号。
- `suggestedAction(ticket, result, processing)`：给坐席展示下一步建议动作。
- `metricCards(metrics)`：把评测指标转成卡片展示数据。

### assets

| 文件 | 作用 |
| --- | --- |
| `src/assets/styles.css` | 全局样式，定义颜色变量、字体、通用类和基础交互样式。 |
| `src/assets/hero.png` | 静态图片资源。 |
| `src/assets/vue.svg` | Vue 模板默认图标资源。 |
| `src/assets/vite.svg` | Vite 模板默认图标资源。 |

## 页面组件

### `src/views/TicketListView.vue`

工单工作池首页。它会：

- 在 `onMounted` 时调用 `store.fetchTickets()` 加载工单。
- 使用 `computed` 算出工作池统计和紧急队列。
- 显示左侧 `AppSidebar`、顶部工作池卡片、当前优先队列和 `EvaluationSummaryPanel`。
- 点击工单时用 `router.push('/tickets/:id')` 跳转到详情页。

### `src/views/TicketDetailView.vue`

单个工单的处理台，是当前前端最核心的页面。它负责组合各个业务组件：

- `AppHeader`：详情页顶部标题和“启动 AI 辅助”按钮。
- `TicketInfo`：工单摘要、状态、风险、证据编号。
- `TicketContent`：客户诉求原文。
- `AiProcessPanel`：业务处理链路。
- `AiResultCard`：AI 处理结果、字段、工具证据。
- `NotificationBundlePanel`：客户回单、内部通知、复核摘要、结案建议、回访计划。
- `AgentTraceTimeline`：底层 Agent 执行明细。
- `ToolRegistryPanel`：可用业务工具目录。
- `PageAssistantPanel`：右侧坐席动作栏。
- `ReplyDraftEditor`：回单复核和结案提交。
- `ConfirmDialog`：敏感操作人工确认弹窗。

它还监听 `ticketId` 变化：

```ts
watch(ticketId, async id => {
  if (id) await store.loadTicketContext(id)
})
```

所以用户从一个工单切换到另一个工单时，详情页会自动刷新上下文。

## 组件目录

### layout

| 文件 | 作用 |
| --- | --- |
| `src/components/layout/AppSidebar.vue` | 左侧工单导航栏。提供状态桶筛选、场景筛选、工单列表、当前选中态和跳转逻辑。 |
| `src/components/layout/AppHeader.vue` | 详情页顶部栏。展示工单标题、编号、场景和状态，并向父组件发出 `process`、`reset` 事件。 |

### shared

| 文件 | 作用 |
| --- | --- |
| `src/components/shared/StatusBadge.vue` | 通用状态标签组件。根据 `value` 或显式 `tone` 显示不同颜色的小标签。 |

### ticket

| 文件 | 作用 |
| --- | --- |
| `src/components/ticket/TicketInfo.vue` | 工单摘要面板。展示场景、结论、下一责任人、建议动作、证据编号、客户信息和状态说明。 |
| `src/components/ticket/TicketContent.vue` | 客户诉求原文卡片。只接收 `content` 字符串并展示。 |

### ai

| 文件 | 作用 |
| --- | --- |
| `src/components/ai/AiProcessPanel.vue` | 把 `traceSteps` 和 `aiResult` 转成“接单提取、业务分诊、风险拦截、执行处理、回单生成”的业务链路。 |
| `src/components/ai/AgentTraceTimeline.vue` | 技术审计抽屉，逐条展示 Agent 执行状态、耗时和摘要。 |
| `src/components/ai/AiResultCard.vue` | AI 结果主卡片，展示意图、工作流、风险判断、字段提取、缺失字段、工具入参、工具证据和校验结果。 |
| `src/components/ai/VerifyChecks.vue` | 风险与兜底检查列表，被 `AiResultCard` 引用。 |
| `src/components/ai/NotificationBundlePanel.vue` | 模块 D 的结构化通知展示。展示标准回单、内部通知、人工复核摘要、结案建议和回访预留。 |
| `src/components/ai/PageAssistantPanel.vue` | 右侧坐席动作栏。根据当前状态给出下一步动作，并发出滚动、填入回单、启动处理等事件。 |
| `src/components/ai/ReplyDraftEditor.vue` | 回单编辑器。通过 `v-model:draft` 与 store 中的 `replyDraft` 双向绑定，并提交最终结案。 |
| `src/components/ai/ConfirmDialog.vue` | 人工确认弹窗。工作流暂停时出现，向父组件发出 `confirm` 或 `reject`。 |

### tools

| 文件 | 作用 |
| --- | --- |
| `src/components/tools/ToolRegistryPanel.vue` | 调用 `toolApi.list()` 读取后端工具目录，展示工具名称、风险等级和是否需要人工确认。 |

### metrics

| 文件 | 作用 |
| --- | --- |
| `src/components/metrics/EvaluationSummaryPanel.vue` | 调用 `evalApi.metrics()` 读取评测指标，并显示链路质量、工具命中、字段完整率、平均耗时等摘要。 |

## Vue 单文件组件怎么读

这个项目的 `.vue` 文件通常分三段：

```vue
<script setup lang="ts">
// 组件逻辑：导入依赖、定义 props、状态、计算属性、事件和函数
</script>

<template>
  <!-- 组件 HTML 模板：把状态渲染成界面 -->
</template>

<style scoped>
/* 只作用于当前组件的 CSS */
</style>
```

### `<script setup>`

`<script setup>` 是 Vue 3 推荐写法之一。里面写的变量和函数可以直接在 `<template>` 使用，不需要再写 `return`。

```ts
const props = defineProps<{ content: string }>()
```

表示父组件必须传入一个 `content` 字符串。

```ts
const emit = defineEmits<{ process: []; reset: [] }>()
```

表示当前组件可以向父组件发出 `process` 和 `reset` 事件。

### `ref`

`ref` 用来定义会变化的响应式数据：

```ts
const loading = ref(false)
loading.value = true
```

在 `<script>` 里访问要写 `.value`，在 `<template>` 里 Vue 会自动解包，可以直接写 `loading`。

### `computed`

`computed` 用来从已有状态派生新值：

```ts
const openCount = computed(() =>
  tickets.value.filter(t => t.status !== 'closed').length
)
```

只要 `tickets` 变了，`openCount` 会自动重新计算，页面也会自动更新。

### `onMounted`

`onMounted` 是生命周期钩子，表示组件第一次挂载到页面后执行：

```ts
onMounted(() => store.fetchTickets())
```

常用于初始加载接口数据。

### `watch`

`watch` 用来监听响应式值变化：

```ts
watch(ticketId, async id => {
  if (id) await store.loadTicketContext(id)
})
```

详情页用它监听路由里的工单 ID，切换工单时自动加载新工单上下文。

### props 向下传，事件向上传

Vue 组件之间常见的数据流是：

```text
父组件通过 props 把数据传给子组件
子组件通过 emit 把用户动作通知父组件
父组件再决定是否调用 store 或 API
```

例如 `TicketDetailView.vue`：

```vue
<AppHeader
  :ticket="ticket"
  :processing="store.isProcessing"
  @process="handleProcess"
  @reset="handleReset"
/>
```

这里 `ticket` 和 `processing` 是传给 `AppHeader` 的 props；`process` 和 `reset` 是 `AppHeader` 点击按钮后发回来的事件。

### `v-if`、`v-for`、`:prop`、`@event`

模板里常见语法：

- `v-if="ticket"`：条件渲染，有工单才显示。
- `v-for="ticket in tickets"`：循环渲染列表。
- `:ticket="ticket"`：把 JS 表达式作为 prop 传入。
- `@click="handleProcess"`：监听 DOM 或组件事件。
- `v-model="model"`：表单双向绑定。
- `v-model:draft="store.replyDraft"`：自定义字段的双向绑定，本项目在 `ReplyDraftEditor.vue` 使用。

## Pinia 在这里怎么用

`src/stores/ticket.ts` 使用的是 Pinia setup store：

```ts
export const useTicketStore = defineStore('ticket', () => {
  const tickets = ref<Ticket[]>([])
  const selectedTicket = computed(() => ...)

  async function fetchTickets() {
    tickets.value = await ticketApi.list()
  }

  return { tickets, selectedTicket, fetchTickets }
})
```

组件里这样使用：

```ts
const store = useTicketStore()
await store.fetchTickets()
```

store 的好处是：多个页面和组件可以共享同一份工单状态，不需要层层传递所有数据。

## 后端接口和前端类型的关系

`api/index.ts` 负责真正发请求，`types/index.ts` 负责告诉 TypeScript “接口会返回什么形状的数据”。

例如：

```ts
list: () => api.get<Ticket[]>('/tickets').then(r => r.data)
```

含义是：

1. 请求 `/api/tickets`。
2. 后端返回的数据应该是 `Ticket[]`。
3. `.then(r => r.data)` 只取响应体，组件不需要关心 Axios 的完整响应对象。

如果后端字段变了，通常需要同时检查：

- `src/types/index.ts`
- `src/api/index.ts`
- 使用该字段的组件
- `src/utils/business.ts` 中的业务转换函数

## 修改代码时建议的阅读顺序

### 想改页面布局

先看：

1. `src/views/TicketListView.vue`
2. `src/views/TicketDetailView.vue`
3. 对应 `src/components/` 下的子组件
4. `src/assets/styles.css`

### 想改接口或数据字段

先看：

1. `src/types/index.ts`
2. `src/api/index.ts`
3. `src/stores/ticket.ts`
4. 使用该字段的页面或组件

### 想改 AI 处理流程显示

先看：

1. `src/stores/ticket.ts` 的 `startAiProcess`
2. `src/components/ai/AiProcessPanel.vue`
3. `src/components/ai/AgentTraceTimeline.vue`
4. `src/components/ai/AiResultCard.vue`
5. `src/utils/business.ts` 的 `businessSteps`

### 想改回单、通知、结案链路

先看：

1. `src/types/index.ts` 的 `NotificationBundle`
2. `src/components/ai/NotificationBundlePanel.vue`
3. `src/components/ai/ReplyDraftEditor.vue`
4. `src/stores/ticket.ts` 的 `applyProcessResult` 和 `closeTicket`
5. `src/api/index.ts` 的 `close`

## 一个典型工单处理过程

1. 用户打开 `/tickets`。
2. `TicketListView` 加载工单列表。
3. 用户点击一个工单，路由跳到 `/tickets/:id`。
4. `TicketDetailView` 加载该工单已有 AI 结果和 Trace。
5. 用户点击“启动 AI 辅助”。
6. `ticket.ts` 通过 SSE 接收多 Agent 事件。
7. `AiProcessPanel` 和 `AgentTraceTimeline` 实时更新。
8. 后端返回 `AiProcessResult`。
9. `NotificationBundlePanel` 展示结构化回单和复核建议。
10. 坐席在 `ReplyDraftEditor` 复核或修改回单。
11. 点击结案按钮，调用 `/api/tickets/{ticket_id}/close`。

## 新手注意点

- 组件文件名一般使用 PascalCase，例如 `TicketInfo.vue`。
- 页面级组件放在 `views/`，可复用组件放在 `components/`。
- 不要在很多组件里重复写接口请求，优先放到 `api/` 和 `stores/`。
- 后端返回的新字段先写进 `types/index.ts`，再在组件里使用。
- 展示文案、状态颜色、业务分类优先放到 `utils/business.ts`，避免散落在多个组件。
- 修改样式时先看 CSS 变量，例如 `var(--green)`、`var(--line)`、`var(--radius)`。
- `scoped` 样式只影响当前组件，适合大多数组件局部样式。
- 结案动作不要只改前端状态，应通过 `ticketApi.close()` 调后端接口。
