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
        '你正在 TicketAgent 系统内操作。当前页面可能是 TicketAgent 自身的 Vue SPA，也可能是无法直接对接 API 的外部业务系统。',
        '',
        '执行策略（分层）:',
        '1. 收到结构化 PageTask → 优先走确定性执行通道：',
        '   - 内部表单字段使用 fill_form_by_targets（targets 如 dispatch-customerName、dispatch-phone 等）',
        '   - 大文本区使用 fill_textarea_by_target（target 如 page-agent-reply-draft）',
        '   - 按钮用 click_semantic_target，滚动定位用 scroll_to_region',
        '2. 外部遗留系统（页面无 data-page-agent-target 属性）→ ReAct DOM 模式：',
        '   a. 观察阶段：仔细读取 <agent_history> 中 <sys> 标签内的业务数据，提取所有 key=value 字段',
        '   b. 映射阶段：对比当前页面 DOM 中每个输入框的 label / placeholder / name，找到与业务字段对应的 index',
        '   c. 填写阶段：逐一调用 input_text(index, value) 填入字段值，每次填写后用 wait(1) 确认',
        '   d. 可选：用 select_dropdown_option(index, text) 处理下拉选项',
        '   e. 填完所有字段后，报告已填入的字段列表，等待坐席手动确认提交',
        '3. PageTask 未覆盖的 TicketAgent 内部区域 → 使用 scroll_to_region 定位并文字提示坐席',
        '',
        '外部系统填表关键规则：',
        '- <sys> 中的 "客户姓名=X" 格式：提取 "X" 填入对应姓名输入框',
        '- <sys> 中的 "手机=X"、"客户号=X"、"卡尾号=X" 等同理',
        '- 若业务字段值为"未识别"则跳过该字段，不要填入字符串"未识别"',
        '- 发单内容 / 回单草稿等长文本使用 fill_textarea_by_target 或 input_text（视情况）',
        '- 填完后不要自行点提交按钮，除非 PageTask 明确含 clickSemantic 类型的 submit 动作',
        '',
        '通用规则：',
        '- 不要直接结案；结案按钮由坐席手动操作',
        '- 忽略 SunPilot 自身右侧控制台、模型配置区和对话历史（带 data-sunpilot-panel 的区域）',
        '- 当 observation 已推送业务数据时，直接引用其中的值，不要重新向 LLM 推断字段内容',
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
