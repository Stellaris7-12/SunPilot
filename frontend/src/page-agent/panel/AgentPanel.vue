<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { bindTicketPageAgentBridge } from '../bridge'
import { createTicketPageAgent, type AgentActivity, type AgentStatus, type HistoricalEvent } from '..'
import { executePageTaskDeterministically, type PageTaskActionAuditEntry } from '../pageTaskExecutor'
import { buildPageTaskDirective, type PageTaskDirective } from '../taskBridge'
import { useTicketStore } from '../../stores/ticket'
import type { PageTaskEnvelope } from '../../types'
import { evidenceIds as collectEvidenceIds } from '../../utils/business'

type MessageTone = 'neutral' | 'accent' | 'success' | 'warning' | 'danger'
type MessageKind = 'task' | 'activity' | 'observation' | 'history' | 'result'
type ComposerMode = 'qa' | 'task'

interface PanelMessage {
  id: string
  kind: MessageKind
  title: string
  body: string
  tone: MessageTone
  meta?: string[]
}

interface LlmProxyConfig {
  baseUrl: string
  model: string
  allowedModels: string[]
  apiKeyConfigured: boolean
  apiKeyPreview: string
}

interface ModelOption {
  value: string
  label: string
  shortLabel: string
  hint?: string
}

interface QuickAction {
  label: string
  command?: string
  emit?: 'generateDraft' | 'submitDraft' | 'startAiProcess' | 'scrollReply' | 'scrollMissing' | 'openHumanConfirm'
  disabled?: boolean
}

const businessFieldLabels: Record<string, string> = {
  couponType: '券种',
  reason: '补发原因',
  customerId: '客户号',
  customerName: '客户姓名',
  phone: '手机号',
  cardLast4: '卡号后四位',
  transactionDate: '交易日期',
  transactionAmount: '交易金额',
  merchantName: '商户名称',
  activityName: '活动名称',
}

const emit = defineEmits<{
  generateDraft: []
  submitDraft: []
  startAiProcess: []
  scrollReply: []
  scrollMissing: []
  openHumanConfirm: []
}>()

const MODEL_CATALOG: ModelOption[] = [
  { value: 'qwen3.7-plus', label: 'qwen3.7-plus', shortLabel: 'qwen3.7+', hint: '推荐' },
  { value: 'deepseek-v4-flash', label: 'deepseek-v4-flash', shortLabel: 'ds-flash', hint: '轻量' },
  { value: 'qwen3-8b', label: 'qwen3-8b', shortLabel: 'qwen-8b', hint: '免费额度友好' },
  { value: 'qwen3-14b', label: 'qwen3-14b', shortLabel: 'qwen-14b', hint: '免费额度友好' },
  { value: 'qwen3-30b-a3b', label: 'qwen3-30b-a3b', shortLabel: 'qwen-30b', hint: '免费额度友好' },
  { value: 'qwen3-30b-a3b-instruct-2507', label: 'qwen3-30b-a3b-instruct-2507', shortLabel: 'qwen30b-i' },
  { value: 'qwen3-next-80b-a3b-instruct', label: 'qwen3-next-80b-a3b-instruct', shortLabel: 'qwen-next' },
  { value: 'qwen-plus', label: 'qwen-plus', shortLabel: 'qwen+', hint: '通用' },
  { value: 'qwen-turbo', label: 'qwen-turbo', shortLabel: 'turbo', hint: '低延迟' },
  { value: 'qwen3.7-max', label: 'qwen3.7-max', shortLabel: 'max' },
  { value: 'qwen3.7-max-preview', label: 'qwen3.7-max-preview', shortLabel: 'max-prev' },
  { value: 'qwen3.7-max-2026-06-08', label: 'qwen3.7-max-2026-06-08', shortLabel: 'max-0608' },
  { value: 'qwen3.7-max-2026-05-17', label: 'qwen3.7-max-2026-05-17', shortLabel: 'max-0517' },
  { value: 'qwen3.5-plus-2026-04-20', label: 'qwen3.5-plus-2026-04-20', shortLabel: '3.5+' },
  { value: 'qwen3.5-ocr', label: 'qwen3.5-ocr', shortLabel: 'ocr', hint: 'OCR' },
  { value: 'glm-5.2', label: 'glm-5.2', shortLabel: 'glm-5.2' },
  { value: 'kimi-k2.7-code', label: 'kimi-k2.7-code', shortLabel: 'kimi-code' },
]

const route = useRoute()
const store = useTicketStore()
const agent = createTicketPageAgent()
const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api').replace(/\/$/, '')

const input = ref('')
const composerMode = ref<ComposerMode>('qa')
const messages = ref<PanelMessage[]>([])
const thread = ref<HTMLElement | null>(null)
const running = ref(false)
const status = ref<AgentStatus>(agent.status)
const settingsOpen = ref(false)
const savingSettings = ref(false)
const settingsStatus = ref('')
const llmConfig = ref<LlmProxyConfig | null>(null)
const selectedModel = ref('qwen3.7-plus')
const apiKeyInput = ref('')
const suggestedCommand = ref('')
const latestBusinessContext = ref('')
const latestPageTask = ref<PageTaskEnvelope | null>(null)
const latestPageTaskDirective = ref<PageTaskDirective | null>(null)
let unbindBridge: (() => void) | null = null
let deterministicAbort: AbortController | null = null

const isDispatchPage = computed(() => route.path.startsWith('/dispatch'))
const modeLabel = computed(() => isDispatchPage.value ? '发单辅助' : '回单辅助')
const placeholder = computed(() => {
  if (composerMode.value === 'qa') return isDispatchPage.value ? '可询问发单字段、客户诉求或下一步' : '可询问当前工单、处理依据或下一步'
  return isDispatchPage.value ? '例如：根据这通电话整理发单内容' : '例如：整理处理意见并带入回单'
})
const statusLabel = computed(() => {
  const labels: Record<AgentStatus, string> = {
    idle: '就绪',
    running: '执行中',
    completed: '完成',
    error: '异常',
    stopped: '已接管',
  }
  return labels[status.value]
})
const statusTone = computed(() => {
  if (status.value === 'running') return 'running'
  if (status.value === 'error') return 'danger'
  if (status.value === 'stopped') return 'warning'
  return 'ready'
})
const quickActions = computed<QuickAction[]>(() => {
  if (isDispatchPage.value) {
    return [
      { label: '生成发单草稿', emit: 'generateDraft' },
      { label: '带入来电信息', command: '根据最新发单草稿，填入当前标准工单表单。', disabled: !store.ticketDraftResult },
      { label: '发送工单', emit: 'submitDraft', disabled: !store.ticketDraftResult },
    ]
  }
  const needsConfirm = store.selectedTicket?.status === 'pending_human_confirm'
  const hasMissing = Boolean(store.aiResult?.missingFields?.length)
  if (!store.aiResult) {
    return [
      { label: '开始处理', emit: 'startAiProcess', disabled: !store.selectedTicket || store.isProcessing },
      { label: '查看待补充', emit: 'scrollMissing', disabled: !store.selectedTicket },
    ]
  }
  if (hasMissing) {
    return [
      { label: '补充缺失信息', emit: 'scrollMissing' },
      { label: '查看核验记录', command: '定位外部系统核验过程和核验结果。' },
      { label: needsConfirm ? '人工确认' : '进入复核', emit: needsConfirm ? 'openHumanConfirm' : 'scrollReply', disabled: needsConfirm ? false : !store.replyDraft },
    ]
  }
  return [
    { label: '带入回单内容', command: '根据最新处理结果，填入客户回单编辑器。', disabled: !store.aiResult },
    { label: '查看核验记录', command: '定位处理依据和核验记录。', disabled: !store.aiResult },
    { label: needsConfirm ? '人工确认' : '进入复核', emit: needsConfirm ? 'openHumanConfirm' : 'scrollReply', disabled: needsConfirm ? false : !store.aiResult },
  ]
})
const configSummary = computed(() => {
  if (!llmConfig.value) return '读取中'
  const keyLabel = llmConfig.value.apiKeyConfigured ? `凭据 ${llmConfig.value.apiKeyPreview || '已配置'}` : '凭据未配置'
  return `${llmConfig.value.model} · ${keyLabel}`
})
const modelOptions = computed(() => {
  const allowed = new Set(llmConfig.value?.allowedModels?.length ? llmConfig.value.allowedModels : MODEL_CATALOG.map(model => model.value))
  const byValue = new Map(MODEL_CATALOG.map(model => [model.value, model]))
  const options = Array.from(allowed).map(value => byValue.get(value) || { value, label: value, shortLabel: value })
  if (!options.some(model => model.value === selectedModel.value)) {
    options.unshift({ value: selectedModel.value, label: selectedModel.value, shortLabel: selectedModel.value })
  }
  return options
})
const isAgentRunning = computed(() => running.value || status.value === 'running')
const currentPageTaskLabel = computed(() => {
  if (!latestPageTask.value) return ''
  return cleanBusinessText(latestPageTaskDirective.value?.summary || `待执行 ${latestPageTask.value.actions.length} 步`)
})
const missingFieldLabels = computed(() =>
  (store.aiResult?.missingFields || []).map(field => businessFieldLabel(field))
)
const externalSystemRows = computed(() => {
  const rows: Array<{ label: string; status: string }> = []
  const enrichment = store.aiResult?.fieldEnrichment
  enrichment?.sourceTools?.forEach(tool => {
    rows.push({
      label: toolBusinessLabel(tool),
      status: enrichment.unresolvedFields?.length ? '需补充' : '已核验',
    })
  })
  store.toolCalls.forEach(call => {
    rows.push({
      label: toolBusinessLabel(call.toolName),
      status: call.success ? '已完成' : '未通过',
    })
  })
  return rows.slice(0, 5)
})
const pilotFlowSteps = computed(() => {
  if (isDispatchPage.value) {
    return [
      { label: '读取来电', status: '已完成' },
      { label: store.ticketDraftResult ? '草稿已生成' : '整理草稿', status: store.ticketDraftResult ? '已完成' : '待处理' },
      { label: currentPageTaskLabel.value || '等待发送', status: currentPageTaskLabel.value ? '办理中' : '待处理' },
    ]
  }
  return [
    { label: store.selectedTicket ? '读取工单' : '选择工单', status: store.selectedTicket ? '已完成' : '待处理' },
    { label: store.isProcessing ? '接单处理' : store.aiResult ? '接单处理完成' : '等待处理', status: store.isProcessing ? '办理中' : store.aiResult ? '已完成' : '待处理' },
    { label: externalSystemRows.value.length ? '外部系统核验' : '等待核验', status: store.isProcessing ? '办理中' : externalSystemRows.value.length ? '已完成' : '待处理' },
    { label: missingFieldLabels.value.length ? '信息补充' : (store.replyDraft ? '回单待复核' : '整理回单'), status: missingFieldLabels.value.length ? '需补充' : currentPageTaskLabel.value || store.replyDraft ? '办理中' : '待处理' },
  ]
})

function businessFieldLabel(field: string) {
  return businessFieldLabels[field] || field
}

function toolBusinessLabel(toolName?: string) {
  const name = toolName || ''
  if (/coupon|benefit|权益|优惠|activity/i.test(name)) return '权益活动系统'
  if (/transaction|trade|交易|dispute|chargeback/i.test(name)) return '交易查询系统'
  if (/customer|profile|客户|资料/i.test(name)) return '客户资料系统'
  if (/card|account|卡片|账户/i.test(name)) return '卡片账户系统'
  if (/credit|征信/i.test(name)) return '征信业务系统'
  if (/application|申请/i.test(name)) return '申请进度系统'
  return name || '外部业务系统'
}

function cleanBusinessText(text: string) {
  const withoutTech = text
    .replace(/ticket-reply\s*\/\s*suggest\s*\/\s*\d+\s*个动作[；;]?\s*/gi, '')
    .replace(/PageTask|trace|workflow|tool|confidence|prompt/gi, '')
    .replace(/字段不足/g, '信息不足')
  return Object.entries(businessFieldLabels).reduce(
    (current, [key, label]) => current.replace(new RegExp(key, 'gi'), label),
    withoutTech,
  ).trim()
}

function messageId(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`
}

function pushMessage(message: Omit<PanelMessage, 'id'>) {
  messages.value = [...messages.value, { ...message, id: messageId(message.kind) }].slice(-80)
  void nextTick(() => {
    if (thread.value) thread.value.scrollTop = thread.value.scrollHeight
  })
}

function summarizeInput(inputValue: unknown) {
  const text = typeof inputValue === 'string' ? inputValue : JSON.stringify(inputValue)
  return text.length > 140 ? `${text.slice(0, 140)}...` : text
}

function appendActivity(activity: AgentActivity) {
  if (activity.type === 'thinking') {
    pushMessage({ kind: 'activity', title: '处理中', body: '正在整理当前页面信息。', tone: 'accent' })
    return
  }
  if (activity.type === 'executing') {
    pushMessage({
      kind: 'activity',
      title: '执行操作',
      body: summarizeInput(activity.input),
      tone: 'neutral',
    })
    return
  }
  if (activity.type === 'executed') {
    pushMessage({
      kind: 'activity',
      title: '操作完成',
      body: activity.output,
      tone: 'success',
      meta: [`${activity.duration}ms`],
    })
    return
  }
  if (activity.type === 'retrying') {
    pushMessage({
      kind: 'activity',
      title: '重新尝试',
      body: `第 ${activity.attempt}/${activity.maxAttempts} 次尝试。`,
      tone: 'warning',
    })
    return
  }
  pushMessage({ kind: 'activity', title: '执行异常', body: activity.message, tone: 'danger' })
}

function answerQuestion(question: string) {
  const normalized = question.trim().toLowerCase()
  const ticket = store.selectedTicket
  const evidenceIds = [
    ...collectEvidenceIds(store.aiResult),
    ...(store.toolCalls || []).map(item => item.evidenceId).filter(Boolean),
  ]
  const hasGreeting = /^(你好|您好|hello|hi|在吗|嗨)[!！。,.，\s]*$/i.test(question.trim())
  let body = ''
  if (hasGreeting) {
    body = '你好，我在。当前只回答问题，不会改动页面。要填表、定位依据或整理回单，请点上方快捷按钮。'
  } else if (/能做什么|怎么用|帮助|help/.test(normalized)) {
    body = '我可以说明当前工单、提示缺失字段、梳理处理依据和下一步，也可以按坐席确认带入表单或回单内容。'
  } else if (/当前|工单|案件|客户/.test(question)) {
    body = ticket
      ? `当前工单是 ${ticket.no}：${ticket.title}。客户 ${ticket.customerName || ticket.customerId || '未知'}，状态为 ${ticket.status}。`
      : '当前没有选中的工单。可以先在左侧队列选择一张工单，或在通话发单区选择通话样本。'
  } else if (/证据|依据|审计/.test(question)) {
    body = evidenceIds.length
      ? `当前可见证据编号：${Array.from(new Set(evidenceIds)).join('、')}。`
      : '当前还没有可见依据编号。通常需要先处理当前工单，依据会出现在处理记录中。'
  } else if (/下一步|怎么办|建议/.test(question)) {
    body = ticket
      ? `建议下一步：${store.isProcessing ? '等待处理完成' : store.aiResult?.missingFields?.length ? `先补充 ${store.aiResult.missingFields.join('、')}` : store.aiResult ? '复核回单、处理依据和结案建议' : '先开始处理当前工单'}。`
      : '建议先选择工单或通话样本，再根据页面上方快捷按钮推进。'
  } else {
    body = '我先按问答处理，不会执行页面动作。你可以问“当前工单是什么”“证据有哪些”“下一步怎么办”；需要操作页面时，请切到任务模式。'
  }
  pushMessage({ kind: 'result', title: 'SunPilot 回复', body, tone: 'accent' })
}

async function loadLlmConfig() {
  try {
    const response = await fetch(`${apiBaseUrl}/llm/proxy/config`)
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    const data = await response.json() as LlmProxyConfig
    llmConfig.value = data
    selectedModel.value = data.model
    settingsStatus.value = ''
  } catch (error) {
    const message = error instanceof Error ? error.message : '配置读取失败'
    settingsStatus.value = `配置读取失败：${message}`
  }
}

async function saveLlmConfig() {
  savingSettings.value = true
  settingsStatus.value = '保存中...'
  try {
    const payload: { model: string; apiKey?: string } = { model: selectedModel.value }
    if (apiKeyInput.value.trim()) payload.apiKey = apiKeyInput.value.trim()
    const response = await fetch(`${apiBaseUrl}/llm/proxy/config`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    if (!response.ok) {
      const errorBody = await response.json().catch(() => ({}))
      throw new Error(errorBody.detail || `HTTP ${response.status}`)
    }
    const data = await response.json() as LlmProxyConfig
    llmConfig.value = data
    selectedModel.value = data.model
    apiKeyInput.value = ''
    settingsStatus.value = '已保存到后端当前进程'
  } catch (error) {
    const message = error instanceof Error ? error.message : '保存失败'
    settingsStatus.value = `保存失败：${message}`
  } finally {
    savingSettings.value = false
  }
}

async function saveSelectedModel() {
  savingSettings.value = true
    settingsStatus.value = '保存中...'
  try {
    const response = await fetch(`${apiBaseUrl}/llm/proxy/config`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model: selectedModel.value }),
    })
    if (!response.ok) {
      const errorBody = await response.json().catch(() => ({}))
      throw new Error(errorBody.detail || `HTTP ${response.status}`)
    }
    const data = await response.json() as LlmProxyConfig
    llmConfig.value = data
    selectedModel.value = data.model
    settingsStatus.value = `已切换到 ${data.model}`
  } catch (error) {
    const message = error instanceof Error ? error.message : '保存失败'
    settingsStatus.value = `保存失败：${message}`
  } finally {
    savingSettings.value = false
  }
}

function appendLatestHistory(history: HistoricalEvent[]) {
  const latest = history.at(-1)
  if (!latest) return
  if (latest.type === 'observation') {
    pushMessage({ kind: 'observation', title: '业务提示', body: cleanBusinessText(latest.content), tone: 'accent' })
  }
}

function mapStoreStatus(value: AgentStatus) {
  if (value === 'running') return 'executing'
  if (value === 'completed') return 'done'
  if (value === 'idle') return 'done'
  return value
}

async function runTask(command = input.value) {
  const task = command.trim()
  if (!task || isAgentRunning.value) return
  const taskWithContext = latestBusinessContext.value
    ? `${task}\n\n<latest_business_context>\n${latestBusinessContext.value}\n</latest_business_context>`
    : task
  running.value = true
  input.value = ''
  if (task === suggestedCommand.value) suggestedCommand.value = ''
  store.setPageAgentStatus('thinking', task)
  pushMessage({ kind: 'task', title: '坐席任务', body: task, tone: 'neutral', meta: [modeLabel.value] })

  try {
    const deterministicResult = await maybeRunPageTask(task)
    if (deterministicResult) {
      pushMessage({
        kind: 'result',
      title: deterministicResult.success ? '执行完成' : deterministicResult.stopped ? '等待人工处理' : '执行未完成',
        body: deterministicResult.summary,
        tone: deterministicResult.success ? 'success' : deterministicResult.stopped ? 'warning' : 'danger',
      })
      if (deterministicResult.success || deterministicResult.stopped) return
      pushMessage({
        kind: 'activity',
        title: '继续尝试',
        body: '当前操作未完成，继续根据页面情况处理。',
        tone: 'warning',
      })
    }

    const result = await agent.execute(deterministicResult?.fallbackInstruction || taskWithContext)
    pushMessage({
      kind: 'result',
      title: result.success ? '执行完成' : '执行未完成',
      body: result.data || (result.success ? 'SunPilot 已完成本轮任务。' : 'SunPilot 未能完成本轮任务。'),
      tone: result.success ? 'success' : 'warning',
    })
  } catch (error) {
    const message = error instanceof Error ? error.message : 'SunPilot 执行失败'
    store.setPageAgentStatus('error', task)
    pushMessage({ kind: 'result', title: '执行失败', body: message, tone: 'danger' })
  } finally {
    deterministicAbort = null
    running.value = false
  }
}

async function maybeRunPageTask(task: string) {
  if (!latestPageTask.value || !latestPageTaskDirective.value) return null
  const directive = latestPageTaskDirective.value
  const isStructuredTask =
    task === suggestedCommand.value ||
    task === directive.instruction ||
    task.startsWith('执行当前建议')
  if (!isStructuredTask) return null

  deterministicAbort = new AbortController()
  return executePageTaskDeterministically(
    agent,
    latestPageTask.value,
    directive,
    deterministicAbort.signal,
    recordDeterministicActionLog,
  )
}

async function recordDeterministicActionLog(entry: PageTaskActionAuditEntry) {
  const task = latestPageTask.value
  const ticketId = typeof task?.businessPayload.ticketId === 'string'
    ? task.businessPayload.ticketId
    : typeof route.params.id === 'string'
      ? route.params.id
      : ''
  try {
    await store.recordPageActionLog({
      ticketId,
      taskId: task?.id || '',
      actionKind: entry.actionKind,
      toolName: entry.toolName,
      target: entry.target,
      input: entry.input,
      output: entry.output,
      status: entry.status,
      resultSummary: entry.resultSummary,
      durationMs: entry.durationMs,
      riskLevel: task?.riskLevel || 'low',
      stopReason: entry.stopReason,
      operator: 'sunpilot',
    })
  } catch {
    pushMessage({
      kind: 'activity',
      title: '审计日志暂存失败',
      body: '页面操作已执行，但处理记录暂未保存。',
      tone: 'warning',
    })
  }
}

async function stopAgent() {
  deterministicAbort?.abort()
  await agent.stop()
  running.value = false
  status.value = agent.status
  store.setPageAgentStatus('stopped', '坐席已接管')
  pushMessage({ kind: 'result', title: '已接管', body: '当前 SunPilot 任务已停止。', tone: 'warning' })
}

function submit() {
  const task = input.value.trim()
  if (!task || isAgentRunning.value) return
  input.value = ''
  if (composerMode.value === 'qa') {
    pushMessage({ kind: 'task', title: '坐席提问', body: task, tone: 'neutral' })
    answerQuestion(task)
    return
  }
  void runTask(task)
}

function handleKeydown(event: KeyboardEvent) {
  if (event.isComposing) return
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    submit()
  }
}

function runQuickAction(action: QuickAction | string) {
  if (typeof action === 'string') {
    composerMode.value = 'task'
    void runTask(action)
    return
  }
  if (action.disabled || isAgentRunning.value) return
  if (action.emit) {
    if (action.emit === 'generateDraft') emit('generateDraft')
    else if (action.emit === 'submitDraft') emit('submitDraft')
    else if (action.emit === 'startAiProcess') emit('startAiProcess')
    else if (action.emit === 'scrollReply') emit('scrollReply')
    else if (action.emit === 'scrollMissing') emit('scrollMissing')
    else emit('openHumanConfirm')
    return
  }
  if (action.command) {
    composerMode.value = 'task'
    void runTask(action.command)
  }
}

function setSuggestedCommand(kind: string) {
  const commands: Record<string, string> = {
    draft: '根据刚收到的发单草稿，填入发单表单并提交标准工单。',
    ai_result: '根据刚收到的处理结果，填入回单编辑器，定位处理依据，并滚动到复核区。',
    paused: '根据刚收到的高风险或人工确认信息，定位风险原因和人工确认区域，然后停止等待坐席处理。',
  }
  suggestedCommand.value = commands[kind] || ''
}

onMounted(() => {
  void loadLlmConfig()
  messages.value = [{
    id: messageId('welcome'),
    kind: 'result',
    title: 'SunPilot',
    body: route.path.startsWith('/dispatch') ? '我可以协助整理来电内容、带入发单字段，并在坐席确认后发送工单。' : '我可以协助梳理当前工单、带入回单内容，并提示复核前需要确认的事项。',
    tone: 'neutral',
  }]

  agent.addEventListener('activity', event => appendActivity((event as CustomEvent<AgentActivity>).detail))
  agent.addEventListener('historychange', () => appendLatestHistory(agent.history))
  agent.addEventListener('statuschange', () => {
    status.value = agent.status
    store.setPageAgentStatus(mapStoreStatus(agent.status), agent.task || store.pageAgentGoal)
  })
  unbindBridge = bindTicketPageAgentBridge(agent, store, {
    onObservation: (content, kind) => {
      if (kind !== 'trace' && kind !== 'processing') latestBusinessContext.value = content
      pushMessage({ kind: 'observation', title: '业务提示', body: content, tone: kind === 'paused' ? 'warning' : 'accent' })
      setSuggestedCommand(kind)
    },
    onPageTask: (task, kind) => {
      const directive = buildPageTaskDirective(task)
      latestPageTask.value = task
      latestPageTaskDirective.value = directive
      latestBusinessContext.value = directive.instruction
      suggestedCommand.value = directive.shouldStop ? directive.instruction : `执行当前建议：${directive.summary}`
      pushMessage({
        kind: 'observation',
        title: '操作建议',
        body: cleanBusinessText(directive.summary),
        tone: kind === 'paused' ? 'warning' : 'accent',
      })
    },
  })
})

onBeforeUnmount(() => {
  unbindBridge?.()
  void agent.stop()
  agent.dispose()
})

defineExpose({ runTask, stopAgent })
</script>

<template>
  <aside class="ticket-page-agent" data-page-agent-not-interactive="true" data-sunpilot-panel="true">
    <header class="agent-head">
      <div class="agent-brand">
        <span class="agent-mark">SP</span>
        <div>
          <strong>SunPilot</strong>
          <small>{{ modeLabel }}</small>
        </div>
      </div>
      <div class="agent-state">
        <span :class="`state-dot ${statusTone}`"></span>
        <span>{{ statusLabel }}</span>
        <button class="mini-btn" type="button" :disabled="!isAgentRunning" @click="stopAgent">接管</button>
      </div>
    </header>

    <section v-if="settingsOpen" class="pilot-settings">
      <div class="settings-line">
        <span>连接状态</span>
        <strong>{{ configSummary }}</strong>
      </div>
      <label class="settings-field">
        <span>访问凭据</span>
        <input v-model="apiKeyInput" :disabled="savingSettings" type="password" placeholder="留空则继续使用当前连接" autocomplete="off" />
      </label>
      <label class="settings-field">
        <span>处理通道</span>
        <select
          v-model="selectedModel"
          :disabled="savingSettings || isAgentRunning"
          @change="saveSelectedModel"
        >
          <option v-for="model in modelOptions" :key="model.value" :value="model.value">
            {{ model.shortLabel }}
          </option>
        </select>
      </label>
      <div class="settings-actions">
        <button class="mini-btn" type="button" :disabled="savingSettings" @click="loadLlmConfig">刷新</button>
        <button class="save-config-btn" type="button" :disabled="savingSettings || !selectedModel" @click="saveLlmConfig">保存</button>
      </div>
      <p v-if="settingsStatus" class="settings-status">{{ settingsStatus }}</p>
    </section>

    <section class="pilot-summary">
      <article class="summary-card" :class="{ warning: Boolean(store.aiResult?.missingFields?.length || store.workflowPaused) }">
        <span>当前建议</span>
        <strong>{{ store.isProcessing ? '正在处理，请稍候' : store.aiResult?.missingFields?.length ? '先补充缺失信息' : store.aiResult ? '复核回单内容' : isDispatchPage ? '先整理发单草稿' : '先开始处理工单' }}</strong>
        <p>{{ missingFieldLabels.length ? `待补充：${missingFieldLabels.join('、')}` : store.selectedTicket?.title || '选择左侧业务后继续办理。' }}</p>
      </article>
    </section>

    <section class="quick-card">
      <div class="card-title">快捷操作</div>
      <div class="quick-row">
        <button v-for="action in quickActions" :key="action.label" class="quick-btn" type="button" :disabled="isAgentRunning || action.disabled" @click="runQuickAction(action)">
          {{ action.label }}
        </button>
      </div>
    </section>

    <section class="flow-card">
      <div class="card-title">业务流</div>
      <ol class="pilot-flow">
        <li v-for="step in pilotFlowSteps" :key="step.label">
          <span>{{ step.label }}</span>
          <strong>{{ step.status }}</strong>
        </li>
      </ol>
    </section>

    <details class="fold-card" :open="Boolean(externalSystemRows.length && (store.aiResult?.missingFields?.length || store.workflowPaused))">
      <summary>外部系统核验 <strong>{{ externalSystemRows.length }}</strong></summary>
      <ul v-if="externalSystemRows.length" class="fold-list compact">
        <li v-for="row in externalSystemRows" :key="`${row.label}-${row.status}`">
          <span>{{ row.label }}</span>
          <strong>{{ row.status }}</strong>
        </li>
      </ul>
      <p v-else>开始处理后展示客户、卡片、交易或权益系统核验过程。</p>
    </details>

    <details class="fold-card" :open="Boolean(missingFieldLabels.length)">
      <summary>补充信息 <strong>{{ missingFieldLabels.length }}</strong></summary>
      <ul v-if="missingFieldLabels.length" class="fold-list">
        <li v-for="field in missingFieldLabels" :key="field">{{ field }}</li>
      </ul>
      <p v-else>当前暂无必须补充的字段。</p>
    </details>

    <details class="fold-card" :open="Boolean(!missingFieldLabels.length && collectEvidenceIds(store.aiResult).length)">
      <summary>处理依据 <strong>{{ collectEvidenceIds(store.aiResult).length }}</strong></summary>
      <ul v-if="collectEvidenceIds(store.aiResult).length" class="fold-list">
        <li v-for="id in collectEvidenceIds(store.aiResult)" :key="id" class="mono">{{ id }}</li>
      </ul>
      <p v-else>处理后会在这里显示依据编号。</p>
    </details>

    <details class="fold-card">
      <summary>操作记录 <strong>{{ messages.length }}</strong></summary>
      <section ref="thread" class="agent-thread" aria-label="SunPilot 对话记录">
        <article v-for="message in messages" :key="message.id" class="agent-message" :class="[message.kind, message.tone]">
        <div class="message-head">
          <strong>{{ message.title }}</strong>
          <span>{{ message.meta?.[0] || '' }}</span>
        </div>
        <p>{{ message.body }}</p>
        <div v-if="message.meta?.length" class="meta-row">
          <span v-for="item in message.meta" :key="item">{{ item }}</span>
        </div>
        </article>
      </section>
    </details>

    <footer class="agent-composer">
      <div v-if="suggestedCommand" class="manual-suggestion">
        <span>收到业务信息，等待坐席唤起</span>
        <button type="button" :disabled="isAgentRunning" @click="runQuickAction(suggestedCommand)">执行建议</button>
      </div>
      <div class="input-shell">
        <textarea v-model="input" class="agent-input" :placeholder="placeholder" data-page-agent-target="page-agent-command" @keydown="handleKeydown" />
        <div class="composer-tools">
          <div class="mode-switch" aria-label="SunPilot 输入模式">
            <button
              type="button"
              :class="{ active: composerMode === 'qa' }"
              :disabled="isAgentRunning"
              title="只回答问题，不执行页面动作"
              @click="composerMode = 'qa'"
            >
              询问
            </button>
            <button
              type="button"
              :class="{ active: composerMode === 'task' }"
              :disabled="isAgentRunning"
              title="按坐席确认办理页面操作"
              @click="composerMode = 'task'"
            >
              办理
            </button>
          </div>
          <div class="composer-spacer"></div>
          <button class="key-chip" type="button" title="连接设置" @click="settingsOpen = !settingsOpen">
            设置
          </button>
          <button class="send-btn" type="button" :disabled="!input.trim() || isAgentRunning" @click="submit">↑</button>
        </div>
      </div>
    </footer>
  </aside>
</template>

<style scoped>
.ticket-page-agent {
  display: flex;
  flex-direction: column;
  min-width: 0;
  height: 100%;
  background: #fbfcfe;
  overflow-y: auto;
}
.agent-head {
  min-height: 54px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 12px;
  border-bottom: 1px solid #e2e8f0;
  background: #ffffff;
}
.agent-brand,
.agent-state {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 9px;
}
.agent-brand > div {
  min-width: 0;
  display: grid;
  gap: 1px;
}
.agent-brand strong {
  color: #142033;
  font-size: 14px;
}
.agent-brand small,
.agent-state {
  color: #64748b;
  font-size: 12px;
}
.agent-mark {
  width: 30px;
  height: 30px;
  display: grid;
  place-items: center;
  border: 1px solid #bae6fd;
  border-radius: 6px;
  background: #eff6ff;
  color: #0369a1;
  font-family: var(--mono);
  font-size: 12px;
  font-weight: 900;
}
.state-dot {
  width: 8px;
  height: 8px;
  flex: 0 0 auto;
  border-radius: 999px;
  background: #9aa7b5;
}
.state-dot.ready { background: #22c55e; }
.state-dot.running {
  background: #fbbf24;
  box-shadow: 0 0 0 3px rgba(251, 191, 36, 0.16);
}
.state-dot.warning { background: #c8861a; }
.state-dot.danger { background: #d64545; }
.mini-btn {
  min-height: 26px;
  padding: 0 9px;
  border: 1px solid #dbe4ee;
  border-radius: 6px;
  background: #f8fafc;
  color: #334155;
  font-size: 12px;
  font-weight: 800;
}
.mini-btn:disabled {
  color: #a3adba;
  cursor: not-allowed;
}
.pilot-settings {
  display: grid;
  gap: 10px;
  padding: 12px;
  border-bottom: 1px solid #dce3ea;
  background: #ffffff;
}
.settings-line,
.settings-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.settings-line span,
.settings-field span {
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
}
.settings-line strong {
  min-width: 0;
  color: #0f172a;
  font-size: 12px;
  overflow-wrap: anywhere;
}
.settings-field {
  display: grid;
  gap: 5px;
}
.settings-field select,
.settings-field input {
  min-height: 32px;
  width: 100%;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  background: #f8fafc;
  color: #0f172a;
  font-size: 13px;
}
.settings-field input {
  padding: 0 9px;
}
.save-config-btn {
  min-height: 28px;
  padding: 0 10px;
  border: 1px solid #0e7490;
  border-radius: 6px;
  background: #0e7490;
  color: #fff;
  font-size: 12px;
  font-weight: 900;
}
.save-config-btn:disabled {
  border-color: #cbd5e1;
  background: #e2e8f0;
  color: #94a3b8;
}
.settings-status {
  margin: 0;
  color: #64748b;
  font-size: 12px;
}
.pilot-summary,
.quick-card,
.flow-card,
.fold-card {
  margin: 10px 12px 0;
}
.summary-card,
.quick-card,
.flow-card,
.fold-card {
  border: 1px solid #dbe3eb;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 1px 1px rgba(15, 23, 42, 0.03);
}
.summary-card {
  display: grid;
  gap: 6px;
  padding: 12px;
}
.summary-card.warning {
  border-color: #fde68a;
  background: #fffbeb;
}
.summary-card span,
.card-title {
  color: #64748b;
  font-size: 12px;
  font-weight: 900;
}
.summary-card strong {
  color: #142033;
  font-size: 15px;
}
.summary-card p,
.fold-card p {
  margin: 0;
  color: #64748b;
  font-size: 12px;
  line-height: 1.55;
}
.quick-card {
  display: grid;
  gap: 8px;
  padding: 10px;
}
.flow-card {
  display: grid;
  gap: 8px;
  padding: 10px;
}
.pilot-flow {
  display: grid;
  gap: 0;
  margin: 0;
  padding: 0;
  list-style: none;
}
.pilot-flow li {
  min-height: 32px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
  padding: 7px 0 7px 16px;
  border-top: 1px solid #edf1f5;
  position: relative;
}
.pilot-flow li:first-child {
  border-top: 0;
}
.pilot-flow li::before {
  content: "";
  position: absolute;
  left: 2px;
  top: 13px;
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: #0e7490;
}
.pilot-flow span {
  min-width: 0;
  color: #334155;
  font-size: 12px;
  font-weight: 900;
  overflow-wrap: anywhere;
}
.pilot-flow strong {
  color: #64748b;
  font-size: 11px;
  white-space: nowrap;
}
.fold-card {
  overflow: hidden;
}
.fold-card summary {
  min-height: 36px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 10px;
  color: #334155;
  font-size: 12px;
  font-weight: 900;
  cursor: pointer;
}
.fold-card summary strong {
  color: #64748b;
  font-family: var(--mono);
  font-size: 11px;
}
.fold-card p {
  padding: 0 10px 10px;
}
.fold-subtitle {
  padding: 2px 10px 7px;
  color: #64748b;
  font-size: 11px;
  font-weight: 900;
}
.fold-list {
  display: grid;
  gap: 6px;
  margin: 0;
  padding: 0 10px 10px;
  list-style: none;
}
.fold-list li {
  padding: 6px 7px;
  border: 1px solid #edf1f5;
  border-radius: 6px;
  background: #f8fafc;
  color: #475569;
  font-size: 12px;
  overflow-wrap: anywhere;
}
.fold-list.compact li {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  align-items: center;
}
.fold-list.compact span {
  min-width: 0;
  overflow-wrap: anywhere;
}
.fold-list.compact strong {
  color: #0e7490;
  font-size: 11px;
  white-space: nowrap;
}
.agent-thread {
  max-height: 240px;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow-y: auto;
  padding: 0 10px 10px;
  background: #fff;
}
.agent-message {
  max-width: 100%;
  display: grid;
  gap: 7px;
  padding: 10px 11px;
  border: 1px solid #dbe3eb;
  border-radius: 6px;
  background: #fff;
  color: var(--ink);
  box-shadow: 0 1px 1px rgba(15, 23, 42, 0.03);
}
.agent-message.task {
  width: fit-content;
  max-width: 88%;
  margin-left: auto;
  border-color: #99f6e4;
  background: #ecfeff;
}
.agent-message.accent {
  border-color: #bae6fd;
  background: #f0f9ff;
}
.agent-message.success {
  border-color: #bbf7d0;
  background: #f0fdf4;
}
.agent-message.warning {
  border-color: #fde68a;
  background: #fffbeb;
}
.agent-message.danger {
  border-color: #efc2c2;
  background: #fff5f5;
}
.message-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.message-head strong {
  min-width: 0;
  color: var(--ink);
  font-size: 13px;
}
.message-head span {
  flex: 0 0 auto;
  color: #7d8896;
  font-family: var(--mono);
  font-size: 10px;
}
.agent-message p {
  margin: 0;
  color: var(--ink-soft);
  font-size: 12px;
  line-height: 1.55;
  overflow-wrap: anywhere;
}
.meta-row,
.quick-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.meta-row span {
  min-height: 20px;
  display: inline-flex;
  align-items: center;
  padding: 0 7px;
  border: 1px solid #dbe2ea;
  border-radius: 999px;
  background: #fff;
  color: #536071;
  font-size: 11px;
  font-weight: 800;
}
.agent-composer {
  flex: 0 0 auto;
  position: sticky;
  bottom: 0;
  z-index: 2;
  display: grid;
  gap: 8px;
  margin-top: auto;
  padding: 10px 12px 12px;
  border-top: 1px solid #dce3ea;
  background: #fff;
}
.manual-suggestion {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 9px;
  border: 1px solid #bfdbfe;
  border-radius: 6px;
  background: #eff6ff;
}
.manual-suggestion span {
  min-width: 0;
  color: #315174;
  font-size: 12px;
  font-weight: 800;
}
.manual-suggestion button {
  flex: 0 0 auto;
  min-height: 26px;
  padding: 0 9px;
  border: 1px solid #2563eb;
  border-radius: 6px;
  background: #2563eb;
  color: #fff;
  font-size: 12px;
  font-weight: 900;
}
.manual-suggestion button:disabled {
  border-color: #cbd5e1;
  background: #e2e8f0;
  color: #94a3b8;
}
.page-task-strip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 7px 9px;
  border: 1px solid #d8e0e8;
  border-radius: 6px;
  background: #f8fafc;
}
.page-task-strip span {
  color: #64748b;
  font-size: 11px;
  font-weight: 900;
}
.page-task-strip strong {
  min-width: 0;
  color: #334155;
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.quick-btn {
  min-height: 26px;
  padding: 0 9px;
  border: 1px solid #d8e0e8;
  border-radius: 999px;
  background: #f8fafc;
  color: #344154;
  font-size: 12px;
  font-weight: 800;
}
.quick-btn:hover:not(:disabled) {
  border-color: #0e7490;
  background: #ecfeff;
}
.quick-btn:disabled {
  color: #a3adba;
  background: #f7f8fa;
  cursor: not-allowed;
}
.input-shell {
  display: grid;
  gap: 8px;
  padding: 12px;
  border: 1px solid #d7dde6;
  border-radius: 18px;
  background: #f3f5f7;
}
.agent-input {
  min-height: 76px;
  max-height: 120px;
  resize: vertical;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--ink);
  font-size: 13px;
  line-height: 1.5;
}
.agent-input::placeholder {
  color: #99a4b2;
}
.composer-tools {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}
.mode-switch {
  min-height: 30px;
  display: inline-grid;
  grid-template-columns: 1fr 1fr;
  gap: 2px;
  padding: 2px;
  border: 1px solid #d7dde6;
  border-radius: 999px;
  background: #e8edf3;
}
.mode-switch button {
  min-width: 44px;
  min-height: 26px;
  padding: 0 9px;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: #5d6878;
  font-size: 12px;
  font-weight: 900;
}
.mode-switch button.active {
  background: #ffffff;
  color: #0e7490;
  box-shadow: 0 1px 4px rgba(15, 23, 42, 0.12);
}
.mode-switch button:disabled {
  color: #9ca3af;
  cursor: not-allowed;
}
.composer-spacer {
  flex: 1 1 auto;
  min-width: 8px;
}
.key-chip {
  min-height: 30px;
  min-width: 44px;
  padding: 0 10px;
  border: 0;
  border-radius: 999px;
  background: #e5e7eb;
  color: #475569;
  font-size: 12px;
  font-weight: 900;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.model-select {
  min-height: 34px;
  width: 112px;
  padding: 0 10px 0 12px;
  border: 0;
  border-radius: 999px;
  background: #e5e7eb;
  color: #1f2937;
  font-size: 12px;
  font-weight: 900;
  white-space: nowrap;
}
.model-select:disabled {
  color: #9ca3af;
  cursor: not-allowed;
}
.send-btn {
  width: 34px;
  min-width: 34px;
  height: 34px;
  min-height: 34px;
  border: 0;
  border-radius: 999px;
  background: #d1d5db;
  color: #fff;
  font-size: 21px;
  line-height: 1;
  font-weight: 900;
}
.send-btn:disabled {
  background: #e5e7eb;
  color: #9ca3af;
  cursor: not-allowed;
}
</style>
