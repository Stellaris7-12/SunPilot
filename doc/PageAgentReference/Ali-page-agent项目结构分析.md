# Ali page-agent 项目结构分析

> 源码位置：`C:\Users\heyunhui\OtherProjects\page-agent-main`
>
> GitHub：<https://github.com/alibaba/page-agent>
>
> License：MIT（Copyright (c) 2026 SimonLuvRamen and Alibaba Group Holding Limited）

---

## 一、项目顶层结构

```text
page-agent-main/
├── packages/
│   ├── core/              ← 核心引擎: ReAct 循环 + 工具系统
│   ├── page-controller/   ← DOM 操作层: 页面交互 + 鼠标动画
│   ├── page-agent/        ← 聚合入口: 组合 Core + Controller + Panel
│   ├── ui/                ← UI 面板: 对话输入 + 步骤展示 (React)
│   ├── llms/              ← LLM 调用: OpenAI 兼容接口封装
│   ├── extension/         ← Chrome 扩展
│   ├── mcp/               ← MCP Server
│   └── website/           ← 官网 / Demo 页
├── docs/                  ← 文档
├── scripts/               ← 构建/发布脚本
├── package.json           ← pnpm workspace
└── tsconfig.base.json
```

### 1.2 `packages/core` — 核心引擎

| 文件 | 职责 |
|---|---|
| `PageAgentCore.ts` (~660行) | **ReAct 执行循环**：每步 observe（DOM 脱水）→ think（LLM 决策输出 evaluation_previous_goal / memory / next_goal / action）→ act（执行工具）。管理 status（idle/running/completed/error/stopped）、history（步骤历史 + observation + 错误）、activity 事件（thinking/executing/executed/retrying/error）、abort 取消、maxSteps 步数限制（默认 40）。 |
| `tools/index.ts` | **8 个内置工具**：done（完成任务）、wait（等待 x 秒）、ask_user（向用户提问）、click_element_by_index（点击编号元素）、input_text（向编号元素输入文本）、select_dropdown_option（选择下拉选项）、scroll / scroll_horizontally（滚动）、execute_javascript（执行 JS，默认禁用）。通过 `MacroTool` 将所有工具合并为一个工具，LLM 在 action 字段中选择工具名 + 参数。 |
| `types.ts` | 类型定义：`AgentConfig`（配置）、`AgentStepEvent`（步骤事件，含 reflection + action + usage）、`ExecutionResult`（执行结果）、`HistoricalEvent`（历史事件联合类型）、`AgentStatus`（生命周期状态）、`AgentActivity`（瞬时活动） |
| `prompts/system_prompt.md` | **系统提示词**（~150 行）：定义 ReAct 思维框架、浏览器操作规则、任务完成规则、推理规则和输出格式（evaluation_previous_goal / memory / next_goal / action 的 JSON 结构） |
| `utils/autoFixer.ts` | LLM 返回自动修复：处理 JSON 解析错误、缺失字段补全、格式修正 |

### 1.3 `packages/page-controller` — DOM 操作层

| 文件 | 职责 |
|---|---|
| `PageController.ts` (~435行) | **DOM 状态管理 + 操作入口**：管理 `flatTree`（DOM 扁平树）、`selectorMap`（index → HTMLElement 映射）、`simplifiedHTML`（供 LLM 阅读的页面文本）。核心方法：`getBrowserState()`（每步重新扫描 DOM，返回 url/title/header/content/footer）、`updateTree()`（重建 DOM 树和索引）、`clickElement(index)` / `inputText(index, text)` / `selectOption(index, text)` / `scroll()` / `executeJavascript()` |
| `actions.ts` (~554行) | **W3C 兼容的交互实现**：`clickElement()` 执行完整 PointerEvent + MouseEvent 序列（pointerover→pointerenter→mouseover→mouseenter→pointerdown→mousedown→focus→pointerup→mouseup→click），含 hit-test 找到最深点击目标。`inputTextElement()` 支持 input/textarea/contenteditable，含 React 合成事件兼容。`selectOptionElement()` 处理 select 元素。滚动支持容器感知（遍历祖先链找到可滚动容器）和边界检测。 |
| `dom/index.ts` (~569行) | **DOM 脱水引擎**：`getFlatTree()` 将页面 DOM 转为扁平树（提取可交互元素，赋 index 编号），`flatTreeToString()` 转为 LLM 可读的纯文本（`[1]<button>提交</button>` 格式），`getSelectorMap()` 建立 index→元素引用映射。支持 viewport 扩展、交互元素黑名单、语义标签保留。 |
| `dom/getPageInfo.ts` | 页面尺寸信息：viewport 宽高、总页面宽高、上下剩余像素/页数、当前滚动位置 |
| `dom/dom_tree/` | DOM 树类型定义和序列化类型声明 |
| `mask/SimulatorMask.ts` (~216行) | **可见鼠标动画**：SVG 光标图标（cursor-fill.svg / cursor-border.svg）、光标移动动画、高亮框、暗色模式检测。通过 `wrapper`（遮罩层）block 用户交互，`moveTo(element)` 移动光标到元素中心，`highlight(element)` 高亮目标元素，`click()` 执行点击波纹动画。 |
| `utils/index.ts` | 指针移动、pass-through toggle、原生 value setter 获取、元素类型判断 |
| `patches/` | React 合成事件补丁、Ant Design 补丁 |

### 1.4 `packages/page-agent` — 聚合入口

| 文件 | 职责 |
|---|---|
| `PageAgent.ts` | `extends PageAgentCore`，组合 `PageController`（DOM 操作）+ `Panel`（UI 面板）。对外暴露唯一的 `PageAgent` 类，构造函数接收 `PageAgentConfig`（继承 AgentConfig + PageControllerConfig + PanelConfig）。 |

### 1.5 `packages/ui` — UI 面板（React）

| 文件 | 职责 |
|---|---|
| `Panel.ts` (~697行) | React 组件：右下角浮动卡片，含任务输入框、模型选择器、暗色模式切换、多语言切换、任务历史列表、实时步骤流（thinking/executing/executed/error 状态渲染）。监听 `PageAgentCore` 的 `activity` / `historychange` / `statuschange` 事件驱动 UI 更新。 |

### 1.6 `packages/llms` — LLM 调用

| 文件 | 职责 |
|---|---|
| `LLM.ts` | LLM 调用入口：管理 `OpenAIClient` 实例，提供 `invoke(messages, macroTool, signal, options)` 方法。内置重试机制（通过 `retry` 事件通知）。 |
| `OpenAIClient.ts` (~269行) | OpenAI 兼容接口的客户端实现：支持 streaming、tool calling、token 计算。 |
| `types.ts` | `LLMConfig`（baseURL / apiKey / model / temperature / maxTokens / timeout 等）、模型列表定义 |
| `utils.ts` | Token 估算、响应解析、重试逻辑 |
| `errors.ts` | 自定义错误类型（InvokeError 等） |

---

## 二、License

上游项目 MIT License，Copyright (c) 2026 SimonLuvRamen and Alibaba Group Holding Limited。

