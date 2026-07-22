import { PageAgentCore } from './core/PageAgentCore'
import { PageController } from './controller/PageController'

export function createTicketPageAgent() {
  const controller = new PageController({ enableMask: true })
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
        '你正在 TicketAgent 企业工单页面内操作。',
        '优先使用页面上可见的按钮、输入框和文本区域完成发单、回单、定位证据和滚动复核区。',
        '不要直接结案；结案必须等待坐席在人工作业区确认。',
        '当后端 Agent 结果已经通过 observation 告诉你时，直接把对应字段填到页面，不要要求坐席复制粘贴。',
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
