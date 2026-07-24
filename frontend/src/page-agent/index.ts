import { PageAgentCore } from './core/PageAgentCore'
import { PageController } from './controller/PageController'

export function createTicketPageAgent() {
  const controller = new PageController({
    enableMask: true,
    highlightOpacity: 0.015,
    highlightLabelOpacity: 0.24,
    interactiveBlacklist: [
      () => document.querySelector('[data-sunpilot-panel]') || document.createElement('div'),
      () => document.querySelector('[data-page-agent-ignore="true"]') || document.createElement('div'),
    ],
  })
  return new PageAgentCore({
    pageController: controller,
    model: 'qwen3.7-plus',
    baseURL: import.meta.env.VITE_PAGE_AGENT_LLM_BASE_URL || 'http://localhost:8000/api/llm/proxy',
    language: 'zh-CN',
    maxSteps: 15,
    stepDelay: 0.8,
    experimentalScriptExecutionTool: false,
    instructions: {
      system: [
        '你正在 TicketAgent 企业工单页面内操作。这是一个 Vue SPA，页面元素带有稳定的 data-page-agent-target 属性。',
        '',
        '执行策略（分层）:',
        '1. 如果收到结构化 PageTask → 优先走确定性执行通道，使用 fill_form_by_targets、fill_textarea_by_target、click_semantic_target 等语义工具',
        '2. 如果 PageTask 未覆盖或语义工具失败 → 使用 scroll_to_region、highlight 定位并提示坐席，不要强行猜测 DOM index',
        '3. 仅在操作外部遗留页面（无 data-page-agent-target、无 Store 绑定）时 → 启用 click_element_by_index、input_text 等 ReAct DOM 探索工具',
        '',
        '不要直接结案；结案按钮由坐席手动操作。',
        '当后端结果已通过 observation 推送时，直接引用其中的 target 和 value，不要重新猜测。',
        '忽略 SunPilot 自己的右侧控制台、模型配置区和对话历史；它们不是业务页面目标。',
      ].join('\n'),
    },
  })
}

export { PageAgentCore } from './core/PageAgentCore'
export { PageController } from './controller/PageController'
export type {
  AgentActivity,
  AgentStatus,
  ExecutionResult,
  HistoricalEvent,
} from './core/types'
