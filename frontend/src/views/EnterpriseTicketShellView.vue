<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ConfirmDialog from '../components/ai/ConfirmDialog.vue'
import BusinessFlow from '../components/business/BusinessFlow.vue'
import MetricsDashboard from '../components/business/MetricsDashboard.vue'
import type { BusinessFlowStage } from '../components/business/types'
import SunPilotPanel from '../sunpilot/panel/SunPilotPanel.vue'
import { useTicketStore } from '../stores/ticket'
import type { CallRecordSample, CreateTicketPayload, Ticket, WorkflowField } from '../types'
import { businessCategories, businessFieldLabel, businessText, toolBusinessLabel, operationLabel, operatorLabel } from '../domain/ticket/catalog'
import { buildSupplementQuestion, buildSupplementText, missingFieldOptions } from '../domain/reply/missingInfo'
import { evidenceItems, fieldVerificationItems } from '../domain/ticket/evidence'
import { replyWorkspaceSections } from '../domain/ticket/workflow'
import { riskMeta, statusMeta } from '../domain/ticket/status'
import {
  formatShortTime,
} from '../utils/business'

type CommonField = WorkflowField & {
  name: keyof CreateTicketPayload
  required?: boolean
}

type MockToolStep = {
  id: string
  title: string
  source: string
  status: 'waiting' | 'running' | 'done' | 'blocked'
  detail: string
  evidenceId?: string
}

const route = useRoute()
const router = useRouter()
const store = useTicketStore()

const copilotOpen = ref(true)
const operationError = ref('')
const selectedCallId = ref('')
const customTranscript = ref('')
const draftForm = ref<CreateTicketPayload>(emptyTicketDraft())
const draftGenerationStatus = ref('')
const confirmVisible = ref(false)
const replyTouched = ref(false)
const replyTemplate = ref('standard')
const internalNoteDraft = ref('')
const reviewSummaryDraft = ref('')
const customerQuestionDraft = ref('')
const followUpDraft = ref('')
const activeReplyAssist = ref<'internal' | 'review' | 'question' | 'followUp'>('internal')
const quickQuery = ref('')
const statusFilter = ref('all')
const missingFieldDraft = ref<Record<string, string>>({})
const supplementStatus = ref('')

// 工单流转对话框状态
const actionDialog = ref<'assign' | 'cancel' | 'reopen' | null>(null)
const assigneeInput = ref('')
const departmentInput = ref('')
const actionReasonInput = ref('')
const actionStatus = ref('')

const commonFields: CommonField[] = [
  { name: 'customerName', label: '客户姓名', type: 'text', required: true },
  { name: 'customerId', label: '客户号', type: 'text' },
  { name: 'phone', label: '手机号', type: 'text', required: true },
  { name: 'cardLast4', label: '卡号后四位', type: 'text', required: true },
  { name: 'priority', label: '件别', type: 'select', options: ['normal', 'urgent', 'critical'] },
  { name: 'scene', label: '工单分类', type: 'text', required: true },
  { name: 'category', label: '业务类型', type: 'text' },
  { name: 'subcategory', label: '业务细分类型', type: 'text' },
  { name: 'receiveUnit', label: '接单单位', type: 'text' },
  { name: 'needReply', label: '是否需要回复', type: 'select', options: ['是', '否'] },
  { name: 'deadline', label: '规定回件日期', type: 'text' },
  { name: 'content', label: '发单内容', type: 'textarea', required: true },
]

const routeMode = computed<'home' | 'dispatch' | 'reply-list' | 'reply-detail'>(() => {
  if (route.path.startsWith('/dispatch')) return 'dispatch'
  if (route.path.startsWith('/reply/tickets/')) return 'reply-detail'
  if (route.path.startsWith('/reply')) return 'reply-list'
  return 'home'
})
const routeCategoryId = computed(() => typeof route.params.category === 'string' ? route.params.category : '')
const selectedCategory = computed(() => businessCategories.find(item => item.id === routeCategoryId.value) || null)
const ticketId = computed(() => typeof route.params.id === 'string' ? route.params.id : '')
const ticket = computed(() => store.selectedTicket)
const routeHasTicket = computed(() => routeMode.value === 'reply-detail' && Boolean(ticketId.value))
const workflowConfig = computed(() => store.workflowConfig?.scenarios || {})
const selectedCall = computed<CallRecordSample | null>(() =>
  store.callRecords.find(item => item.id === selectedCallId.value) || filteredCalls.value[0] || store.callRecords[0] || null
)
const currentScene = computed(() => draftForm.value.scene || selectedCategory.value?.scenes[0] || selectedCall.value?.scenario || '')
const scenarioConfig = computed(() => workflowConfig.value[currentScene.value] || null)
const scenarioFields = computed<WorkflowField[]>(() => scenarioConfig.value?.specificFields || [])
const draftRequiredMissing = computed(() =>
  commonFields.filter(field => field.required && !String(draftForm.value[field.name] || '').trim()).map(field => field.label)
)
const canSubmitDraft = computed(() => draftRequiredMissing.value.length === 0)
const evidence = computed(() => evidenceItems(store.aiResult, store.toolCalls))
const verificationItems = computed(() => fieldVerificationItems(store.aiResult))
const missingFields = computed(() => store.aiResult?.missingFields || [])
const hasMissingSupplementDraft = computed(() =>
  missingFields.value.some(field => String(missingFieldDraft.value[field] || '').trim())
)
const fieldEnrichment = computed(() => store.aiResult?.fieldEnrichment || null)
const mockToolSteps = computed<MockToolStep[]>(() => {
  const rows: MockToolStep[] = []
  const enrichment = fieldEnrichment.value
  const sourceTools = enrichment?.sourceTools?.length ? enrichment.sourceTools : []
  const filledFields = Object.entries(enrichment?.filledFields || {})
  const unresolvedFields = enrichment?.unresolvedFields || missingFields.value

  sourceTools.forEach((tool, index) => {
    const filledText = filledFields.length
      ? filledFields.map(([key, value]) => `${businessFieldLabel(key)}=${String(value || '-')}`).join('、')
      : '未查到可直接带入的信息'
    rows.push({
      id: `enrichment-${tool}-${index}`,
      title: '字段核验补齐',
      source: toolBusinessLabel(tool),
      status: unresolvedFields.length ? 'blocked' : 'done',
      detail: businessText(filledText),
      evidenceId: enrichment?.evidenceIds?.[index],
    })
  })

  store.toolCalls.forEach(call => {
    rows.push({
      id: `tool-${call.id}`,
      title: call.success ? '外部系统处理完成' : '外部系统处理未通过',
      source: toolBusinessLabel(call.toolName),
      status: call.success ? 'done' : 'blocked',
      detail: businessText(call.success
        ? call.response?.businessResult || '已返回处理结果。'
        : call.failureReason || call.response?.failureReason || '未能完成处理。'),
      evidenceId: call.evidenceId,
    })
  })

  const traceOnly = store.traceSteps.filter(step =>
    /tool|mock|enrich|executor|resolution|field/i.test(`${step.agentId} ${step.agent} ${step.summary}`)
  )
  traceOnly.forEach((step, index) => {
    if (rows.some(row => row.detail === step.summary)) return
    rows.push({
      id: `trace-${index}`,
      title: /enrich|field/i.test(step.agentId) ? '字段补齐尝试' : '处理过程',
      source: '业务处理链路',
      status: step.status === 'FAILED' ? 'blocked' : step.status === 'RUNNING' ? 'running' : 'done',
      detail: businessText(step.summary || '已执行。'),
    })
  })

  if (!rows.length && store.isProcessing) {
    rows.push({
      id: 'waiting-tool',
      title: '等待外部系统返回',
      source: '业务处理链路',
      status: 'running',
      detail: '正在查询客户、卡片、交易或权益信息。',
    })
  }
  if (!rows.length && store.aiResult && !store.isProcessing) {
    if (ticket.value?.status === 'escalated') {
      rows.push({ id: 'escalated-no-tool', title: '已升级，未调用外部系统', source: (store.aiResult?.intent?.label || '') + '风控门禁', status: 'blocked', detail: store.aiResult?.riskDecision || '触发升级规则，跳过自动工具调用。' })
    } else {
      rows.push({ id: 'no-tool-needed', title: '本次无需外部系统调用', source: (store.aiResult?.intent?.label || '') + '处理链路', status: 'done', detail: '字段完整可直接回单复核。' })
    }
  }
  return rows
})
const replySections = computed(() => replyWorkspaceSections(store.aiResult, ticket.value))
const replyStatus = computed(() => store.replyDraft ? '已生成' : '待处理')
const canClose = computed(() => {
  if (!ticket.value || !store.replyDraft || store.isProcessing) return false
  // 高风险已升级工单：人工复核并生成回单后可直接结案
  if (ticket.value.status === 'escalated') return true
  // 常规工单：需通过结案建议门禁
  return ticket.value.status === 'pending_human_review'
    && Boolean(store.aiResult?.notification?.closureSuggestion?.canClose)
})
const needsHumanConfirm = computed(() => ticket.value?.status === 'pending_human_confirm')
const showConfirmDialog = computed(() => Boolean(ticket.value && (store.workflowPaused || confirmVisible.value)))
const replyWorkspaceStatus = computed(() => {
  if (!store.replyDraft) return '待处理'
  if (ticket.value?.status === 'closed') return '已结案'
  if (canClose.value) return '待结案'
  return replyTouched.value ? '坐席已编辑' : '待复核'
})
const replyAssistOptions = computed(() => [
  { id: 'internal' as const, label: '内部处理意见', status: replySections.value.find(section => section.id === 'internal')?.status || '待处理' },
  { id: 'review' as const, label: '复核意见', status: replySections.value.find(section => section.id === 'review')?.status || '待处理' },
  { id: 'question' as const, label: '客户追问', status: replySections.value.find(section => section.id === 'question')?.status || '待处理' },
  { id: 'followUp' as const, label: '跟进计划', status: replySections.value.find(section => section.id === 'followUp')?.status || '待处理' },
])
const activeReplyAssistMeta = computed(() =>
  replyAssistOptions.value.find(item => item.id === activeReplyAssist.value) || replyAssistOptions.value[0]
)
const filteredCalls = computed(() => {
  if (!selectedCategory.value) return store.callRecords
  return store.callRecords.filter(item => selectedCategory.value?.scenes.includes(item.scenario))
})
const filteredTickets = computed(() => {
  const queryText = quickQuery.value.trim().toLowerCase()
  return store.tickets.filter(item => {
    const text = `${item.no} ${item.customerId} ${item.customerName} ${item.title} ${item.scene} ${item.category} ${item.subcategory} ${item.content}`.toLowerCase()
    const queryOk = !queryText || text.includes(queryText)
    // statusOk 由服务端 watch(statusFilter) 发送的过滤参数处理，本地不再二次过滤
    const categoryOk = !selectedCategory.value || selectedCategory.value.pattern.test(`${item.no} ${item.title} ${item.scene} ${item.category} ${item.subcategory} ${item.content}`)
    return queryOk && categoryOk
  })
})
const queueTickets = computed(() => filteredTickets.value.slice(0, 14))
const tabTickets = computed(() => {
  const selected = ticket.value ? [ticket.value] : []
  const others = store.tickets.filter(item => item.id !== ticket.value?.id).slice(0, 2)
  return [...selected, ...others]
})
const dashboardCards = computed(() => [
  { label: '待发单', value: filteredCalls.value.length, hint: '来电待登记' },
  { label: '待回单', value: store.tickets.filter(item => ['open', 'in_progress'].includes(item.status)).length, hint: '待接单处理' },
  { label: '待补充', value: store.tickets.filter(item => item.status === 'pending_info').length, hint: '缺少材料' },
  { label: '待复核', value: store.tickets.filter(item => item.status === 'pending_human_review').length, hint: '回单复核' },
  { label: '即将逾期', value: store.tickets.filter(item => item.riskLevel === 'high' && item.status !== 'closed').length, hint: '优先处理' },
  { label: '已完成', value: store.tickets.filter(item => item.status === 'closed').length, hint: '今日归档' },
])
const businessFlow = computed<BusinessFlowStage[]>(() => {
  const hasDraft = Boolean(store.ticketDraftResult)
  const hasTicket = Boolean(ticket.value || store.selectedTicketId)
  const hasExternalChecks = mockToolSteps.value.length > 0
  const hasReply = Boolean(store.replyDraft || store.aiResult?.notification?.standardReply?.body)
  const hasMissing = missingFields.value.length > 0
  const isEscalated = ticket.value?.status === 'escalated'
  const isClosed = ticket.value?.status === 'closed'
  const hardBlocked = Boolean(store.workflowPaused || ticket.value?.status === 'failed')
  const current = routeMode.value
  const statusFor = (index: number): BusinessFlowStage['status'] => {
    // 高风险已升级工单：前序节点已完成，回单复核待人工处理，结案归档可直接完成
    if (isEscalated) {
      if (index <= 4) return 'done'
      if (index === 5) return 'running'
      return 'waiting'
    }
    if (isClosed && index >= 5) return 'done'
    if (hardBlocked && index >= 5) return 'blocked'
    if (current === 'dispatch') {
      if (index === 0) return selectedCall.value ? 'done' : 'running'
      if (index === 1) return hasDraft ? 'done' : 'running'
      if (index === 2) return hasTicket ? 'done' : 'waiting'
      return 'waiting'
    }
    if (current === 'reply-detail') {
      if (index <= 2) return 'done'
      if (index === 3) return store.isProcessing ? 'running' : store.aiResult ? 'done' : 'waiting'
      if (index === 4) {
        if (store.isProcessing) return 'running'
        if (hasExternalChecks) return 'done'
        if (store.aiResult && hasMissing) return 'blocked'
        return store.aiResult ? 'done' : 'waiting'
      }
      if (index === 5) {
        if (!store.aiResult) return 'waiting'
        if (hasMissing) return hasMissingSupplementDraft.value ? 'running' : 'blocked'
        return 'done'
      }
      if (index === 6) return hasReply && !hasMissing ? 'running' : 'waiting'
      if (index === 7) return ticket.value?.status === 'closed' ? 'done' : 'waiting'
    }
    if (index <= 1) return 'done'
    if (index === 2 && store.tickets.length) return 'done'
    return 'waiting'
  }
  return ['来电受理', '发单登记', '派送接单单位', '接单处理', '外部系统监测', '回单复核', '结案归档']
    .map((label, index) => ({ id: `stage-${index}`, label, status: statusFor(index) }))
})

onMounted(async () => {
  operationError.value = ''
  const loadErrors: string[] = []
  const [ticketsResult, callsResult, workflowResult] = await Promise.allSettled([
    store.fetchTickets(),
    store.fetchCallRecords(),
    store.fetchWorkflowConfig(),
  ])
  if (ticketsResult.status === 'rejected') loadErrors.push('工单列表')
  if (callsResult.status === 'rejected') loadErrors.push('通话记录')
  if (workflowResult.status === 'rejected') loadErrors.push('表单配置')
  store.fetchMetrics().catch(() => { /* 指标看板为增强信息，加载失败不阻断主流程 */ })
  hydrateCallSelection()
  await loadRouteTicket(ticketId.value)
  if (loadErrors.length) operationError.value = `数据加载失败：${loadErrors.join('、')}。请检查服务连接后刷新。`
})

watch(() => route.path, async () => {
  hydrateCallSelection()
  if (routeMode.value === 'dispatch') resetDispatchDraft(selectedCall.value)
  await loadRouteTicket(ticketId.value)
  // 回到首页时，不带状态过滤重新拉取工单列表，确保 dashboard 指标正确
  if (routeMode.value === 'home') await store.fetchTickets()
})

// 状态筛选变化时向服务端请求对应状态工单；quickQuery 仍为本地文本过滤
watch(statusFilter, async (val) => {
  const filters = val !== 'all' ? { status: val as import('../types').TicketStatus } : undefined
  await store.fetchTickets(filters)
})

watch(selectedCall, current => {
  if (!current) return
  resetDispatchDraft(current)
}, { immediate: true })

watch(routeCategoryId, () => {
  if (routeMode.value === 'dispatch') resetDispatchDraft(selectedCall.value)
})

function resetDispatchDraft(current: CallRecordSample | null) {
  store.ticketDraftResult = null
  draftGenerationStatus.value = ''
  if (!current) {
    customTranscript.value = ''
    draftForm.value = { ...emptyTicketDraft(), scene: selectedCategory.value?.scenes[0] || '' }
    return
  }
  customTranscript.value = current.transcript
  draftForm.value = {
    ...emptyTicketDraft(),
    scene: selectedCategory.value?.scenes[0] || current.scenario,
    riskLevel: current.riskLevel,
    riskLabel: current.riskLevel === 'high' ? '高风险' : current.riskLevel === 'medium' ? '中风险' : '低风险',
  }
}

watch([() => store.aiResult, ticket], () => {
  const sections = replySections.value
  internalNoteDraft.value = sections.find(section => section.id === 'internal')?.body || ''
  reviewSummaryDraft.value = sections.find(section => section.id === 'review')?.body || ''
  customerQuestionDraft.value = sections.find(section => section.id === 'question')?.body || ''
  followUpDraft.value = sections.find(section => section.id === 'followUp')?.body || ''
  missingFieldDraft.value = Object.fromEntries(missingFields.value.map(field => [field, missingFieldDraft.value[field] || '']))
  supplementStatus.value = ''
  replyTouched.value = false
}, { immediate: true })

function emptyTicketDraft(): CreateTicketPayload {
  return {
    title: '',
    customerId: '',
    customerName: '',
    phone: '',
    cardLast4: '',
    scene: '',
    category: '',
    subcategory: '',
    extJson: {},
    orderPrefix: '',
    bizType: '',
    bizSubType: '',
    priority: 'normal',
    channel: '客服热线发单',
    assignee: '坐席 A1027',
    department: '信用卡运营组',
    dueAt: '',
    deadline: '',
    riskLabel: '低风险',
    riskLevel: 'low',
    receiveUnit: '',
    needReply: true,
    content: '',
  }
}

function hydrateCallSelection() {
  if (!filteredCalls.value.length) return
  if (!selectedCallId.value || !filteredCalls.value.some(item => item.id === selectedCallId.value)) {
    selectedCallId.value = filteredCalls.value[0].id
  }
}

async function loadRouteTicket(id?: string) {
  confirmVisible.value = false
  if (!id || routeMode.value !== 'reply-detail') {
    store.clearSelectedTicket()
    return
  }
  const matched = store.tickets.find(item => item.id === id || item.no === id)
  if (!matched) {
    store.selectTicket(id)
    return
  }
  await store.loadTicketContext(matched.id)
}

function selectCategory(mode: 'dispatch' | 'reply', id: string) {
  if (mode === 'dispatch') router.push(`/dispatch/${id}`)
  else router.push(`/reply/${id}`)
}

function selectCallRecord(id: string) {
  selectedCallId.value = id
  const record = store.callRecords.find(item => item.id === id)
  resetDispatchDraft(record || null)
}

function draftFieldValue(field: CommonField) {
  const value = draftForm.value[field.name]
  if (field.name === 'needReply') return value === false ? '否' : '是'
  return String(value ?? '')
}

function updateDraftField(field: CommonField, value: string) {
  if (field.name === 'needReply') draftForm.value.needReply = value !== '否'
  else if (field.name === 'priority') draftForm.value.priority = priorityValue(value)
  else draftForm.value = { ...draftForm.value, [field.name]: value }
}

function specificFieldValue(name: string) {
  return String((draftForm.value.extJson || {})[name] ?? '')
}

function updateSpecificField(name: string, value: string) {
  draftForm.value.extJson = { ...(draftForm.value.extJson || {}), [name]: value }
  if (name === 'receiveUnit') draftForm.value.receiveUnit = value
  if (name === 'bizSubType') {
    draftForm.value.bizSubType = value
    draftForm.value.subcategory = draftForm.value.subcategory || value
  }
}

async function generateDraftFromCall() {
  operationError.value = ''
  draftGenerationStatus.value = '正在整理来电内容...'
  try {
    const payload = selectedCall.value && selectedCall.value.transcript === customTranscript.value
      ? { sampleId: selectedCall.value.id, operatorId: 'desk-a1027' }
      : { transcript: customTranscript.value, callMeta: selectedCall.value?.callMeta, operatorId: 'desk-a1027' }
    const result = await store.generateTicketDraft(payload)
    draftForm.value = { ...emptyTicketDraft(), ...result.ticketDraft, extJson: result.ticketDraft.extJson || {} }
    draftGenerationStatus.value = `已带入来电内容：${result.detectedScenario}`
    return result
  } catch {
    draftGenerationStatus.value = '来电内容整理失败，请检查服务后重试。'
    operationError.value = draftGenerationStatus.value
    throw new Error(draftGenerationStatus.value)
  }
}

async function handleSubmitDraft() {
  if (!canSubmitDraft.value) {
    operationError.value = `发单字段不完整：${draftRequiredMissing.value.join('、')}`
    return
  }
  operationError.value = ''
  try {
    const stamp = Date.now().toString().slice(-8)
    const created = await store.createTicket({
      ...draftForm.value,
      id: `call_${stamp}`,
      no: `${draftForm.value.orderPrefix || scenarioConfig.value?.orderPrefix || 'T'}${new Date().toISOString().slice(0, 10).replace(/-/g, '')}${Date.now().toString().slice(-6)}`,
      dueAt: draftForm.value.dueAt || draftForm.value.deadline,
    })
    await router.push(`/reply/tickets/${created.id}`)
  } catch {
    operationError.value = '发送工单失败，请确认编号和字段后重试。'
  }
}

function handleSaveDispatchDraft() {
  draftGenerationStatus.value = '已暂存当前发单草稿。'
}

function selectTicket(id: string) {
  router.push(`/reply/tickets/${id}`)
}

function handleProcess() {
  operationError.value = ''
  if (ticket.value) store.startAiProcess(ticket.value.id)
}

async function handleSaveReply() {
  if (!ticket.value || !store.replyDraft.trim()) return
  operationError.value = ''
  try {
    await store.saveReplyDraft(ticket.value.id, store.replyDraft, 'desk-a1027')
  } catch {
    operationError.value = '保存回单失败，请刷新后重试。'
  }
}

async function handleClose() {
  if (!ticket.value || !store.replyDraft) return
  operationError.value = ''
  try {
    await store.closeTicket(ticket.value.id, store.replyDraft)
  } catch {
    operationError.value = '结案提交失败，请刷新工单状态后重试。'
  }
}

function openHumanConfirm() {
  if (needsHumanConfirm.value) confirmVisible.value = true
}

async function handleHumanConfirm(approved: boolean) {
  if (!ticket.value) return
  operationError.value = ''
  try {
    await store.confirmAction(ticket.value.id, approved)
    confirmVisible.value = false
  } catch {
    operationError.value = '人工确认提交失败，请刷新工单状态后重试。'
  }
}

function fillMissingField(field: string, value: string) {
  missingFieldDraft.value = { ...missingFieldDraft.value, [field]: value }
}

function generateSupplementQuestion() {
  customerQuestionDraft.value = buildSupplementQuestion(missingFields.value)
  activeReplyAssist.value = 'question'
  supplementStatus.value = '已生成客户补充话术。'
  scrollToId('enterprise-reply')
}

async function saveMissingSupplement(restart = false) {
  if (!ticket.value) return
  const supplementText = buildSupplementText(missingFields.value, missingFieldDraft.value, false)
  if (!supplementText) {
    supplementStatus.value = '请先填写至少一项补充信息。'
    return
  }
  operationError.value = ''
  supplementStatus.value = restart ? '正在暂存并重新处理...' : '正在暂存补充信息...'
  try {
    const supplement = Object.fromEntries(
      missingFields.value
        .map(field => [field, String(missingFieldDraft.value[field] || '').trim()])
        .filter(([, value]) => value)
    )
    const currentContent = ticket.value.content || ''
    const nextContent = currentContent.includes(supplementText)
      ? currentContent
      : `${currentContent.trim()}\n\n${supplementText}`.trim()
    await store.updateTicket(ticket.value.id, {
      content: nextContent,
      extJson: {
        ...(ticket.value.extJson || {}),
        // 结构化补充值直接写到 extJson 顶层（键=缺失字段名），供后端 Agent 确定性读取。
        ...supplement,
        supplementInfo: {
          ...((ticket.value.extJson?.supplementInfo as Record<string, unknown> | undefined) || {}),
          ...supplement,
        },
      },
      operator: 'desk-a1027',
    })
    supplementStatus.value = restart ? '已暂存补充信息，正在重新处理。' : '已暂存补充信息，可重新开始处理。'
    if (restart) handleProcess()
  } catch {
    supplementStatus.value = '补充信息暂存失败，请检查服务后重试。'
    operationError.value = supplementStatus.value
  }
}

function applyTemplate() {
  const ids = evidence.value.map(item => item.id).join('、') || '待补充'
  const scene = ticket.value?.scene || '信用卡工单'
  const templates: Record<string, string> = {
    standard: `您好，关于您反馈的${scene}问题，我行已完成核验处理。处理依据编号：${ids}。如仍有疑问可继续联系我行客服。`,
    benefit: `您好，您反馈的活动权益问题已完成资格与发放状态核验。处理依据编号：${ids}。如符合补发条件，将按活动规则处理。`,
    dispute: `您好，您反馈的交易问题已完成初步核查。处理依据编号：${ids}。如需补充材料，我行将继续跟进。`,
  }
  applyReplyText(templates[replyTemplate.value] || templates.standard)
}

function applyReplyText(text: string, markTouched = true) {
  if (!text.trim()) return
  store.replyDraft = store.replyDraft.trim() && replyTouched.value && store.replyDraft.trim() !== text.trim()
    ? `${store.replyDraft.trim()}\n\n${text.trim()}`
    : text
  replyTouched.value = markTouched
}

function replyAssistValue() {
  if (activeReplyAssist.value === 'review') return reviewSummaryDraft.value
  if (activeReplyAssist.value === 'question') return customerQuestionDraft.value
  if (activeReplyAssist.value === 'followUp') return followUpDraft.value
  return internalNoteDraft.value
}

function updateReplyAssist(value: string) {
  if (activeReplyAssist.value === 'review') reviewSummaryDraft.value = value
  else if (activeReplyAssist.value === 'question') customerQuestionDraft.value = value
  else if (activeReplyAssist.value === 'followUp') followUpDraft.value = value
  else internalNoteDraft.value = value
}

function insertEvidenceText(id: string) {
  store.replyDraft = store.replyDraft.trim() ? `${store.replyDraft.trim()}\n处理依据编号：${id}` : `处理依据编号：${id}`
  replyTouched.value = true
}

function markReplyEdited() {
  replyTouched.value = true
}

function openActionDialog(type: 'assign' | 'cancel' | 'reopen') {
  assigneeInput.value = ticket.value?.assignee || ''
  departmentInput.value = ticket.value?.department || ''
  actionReasonInput.value = ''
  actionStatus.value = ''
  actionDialog.value = type
}

function closeActionDialog() {
  actionDialog.value = null
  actionStatus.value = ''
}

async function handleAssign() {
  if (!ticket.value || !assigneeInput.value.trim()) {
    actionStatus.value = '请填写经办人。'
    return
  }
  actionStatus.value = '正在转派...'
  try {
    await store.assignTicket(ticket.value.id, assigneeInput.value.trim(), departmentInput.value.trim() || undefined, 'desk-a1027')
    actionDialog.value = null
    actionStatus.value = ''
  } catch {
    actionStatus.value = '转派失败，请刷新后重试。'
  }
}

async function handleCancel() {
  if (!ticket.value || !actionReasonInput.value.trim()) {
    actionStatus.value = '请填写取消原因。'
    return
  }
  actionStatus.value = '正在取消工单...'
  try {
    await store.cancelTicket(ticket.value.id, actionReasonInput.value.trim(), 'desk-a1027')
    actionDialog.value = null
    actionStatus.value = ''
  } catch {
    actionStatus.value = '取消失败，请刷新后重试。'
  }
}

async function handleReopen() {
  if (!ticket.value) return
  actionStatus.value = '正在重开工单...'
  try {
    await store.reopenTicket(ticket.value.id, actionReasonInput.value.trim(), 'desk-a1027')
    actionDialog.value = null
    actionStatus.value = ''
  } catch {
    actionStatus.value = '重开失败，请刷新后重试。'
  }
}

function scrollToId(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function statusClass(tone?: string) {
  return `status ${tone || 'neutral'}`
}

function priorityLabel(value?: string) {
  if (value === 'critical') return '紧急件'
  if (value === 'urgent') return '加急件'
  return '一般件'
}

function priorityValue(value: string): Ticket['priority'] {
  if (value === '紧急件' || value === 'critical') return 'critical'
  if (value === '加急件' || value === 'urgent') return 'urgent'
  return 'normal'
}

function ticketStatus(item: Ticket) {
  return statusMeta(item.status)
}

function ticketRisk(item: Ticket) {
  return riskMeta(item.riskLevel, item.riskLabel)
}

function statusLabelFor(value?: string) {
  return statusMeta(value).label
}
</script>

<template>
  <div class="enterprise-shell">
    <header class="topbar">
      <button class="brand-strip" type="button" @click="router.push('/')">
        <span class="bank-seal">CC</span>
        信用卡客服工单系统
      </button>
      <div class="top-actions">
        <span>坐席：A1027 李青</span>
        <span class="mono">{{ new Date().toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' }) }}</span>
        <span v-if="operationError" class="status red">{{ operationError }}</span>
      </div>
    </header>

    <div class="layout-core" :class="{ 'copilot-expanded': copilotOpen }">
      <aside class="nav-tree">
        <div class="tree-head">业务菜单</div>
        <button class="tree-root" :class="{ active: routeMode === 'home' }" type="button" @click="router.push('/')">
          <span>工作台</span>
          <strong>{{ store.tickets.length }}</strong>
        </button>
        <div class="tree-group">
          <span class="tree-title">发单</span>
          <button class="tree-item" :class="{ active: route.path === '/dispatch' }" type="button" @click="router.push('/dispatch')">
            <span>全部发单</span>
            <strong>{{ store.callRecords.length }}</strong>
          </button>
          <button
            v-for="item in businessCategories"
            :key="`dispatch-${item.id}`"
            class="tree-item sub"
            :class="{ active: routeMode === 'dispatch' && routeCategoryId === item.id }"
            type="button"
            @click="selectCategory('dispatch', item.id)"
          >
            <span>{{ item.label }}</span>
            <strong>{{ store.callRecords.filter(call => item.scenes.includes(call.scenario)).length }}</strong>
          </button>
        </div>
        <div class="tree-group">
          <span class="tree-title">回单</span>
          <button class="tree-item" :class="{ active: route.path === '/reply' }" type="button" @click="router.push('/reply')">
            <span>全部回单</span>
            <strong>{{ store.tickets.length }}</strong>
          </button>
          <button
            v-for="item in businessCategories"
            :key="`reply-${item.id}`"
            class="tree-item sub"
            :class="{ active: routeMode !== 'dispatch' && routeCategoryId === item.id }"
            type="button"
            @click="selectCategory('reply', item.id)"
          >
            <span>{{ item.label }}</span>
            <strong>{{ store.tickets.filter(ticket => item.pattern.test(`${ticket.no} ${ticket.title} ${ticket.scene} ${ticket.category} ${ticket.subcategory}`)).length }}</strong>
          </button>
        </div>
        <div class="tree-group">
          <span class="tree-title">查询与复核</span>
          <button class="tree-item" type="button" @click="router.push('/reply')"><span>工单查询</span><strong>{{ store.tickets.length }}</strong></button>
          <button class="tree-item" type="button" @click="router.push('/reply?status=pending_human_review')"><span>复核剔退</span><strong>{{ store.tickets.filter(item => item.status === 'pending_human_review').length }}</strong></button>
          <button class="tree-item" type="button" @click="router.push('/')"><span>报表看板</span><strong>{{ dashboardCards.at(-1)?.value }}</strong></button>
        </div>
      </aside>

      <main class="workspace">
        <nav class="tabbar" aria-label="打开的业务页签">
          <button class="tab" :class="{ active: routeMode === 'home' }" type="button" @click="router.push('/')">工作台</button>
          <button class="tab" :class="{ active: routeMode === 'dispatch' }" type="button" @click="router.push('/dispatch')">发单</button>
          <button class="tab" :class="{ active: routeMode === 'reply-list' }" type="button" @click="router.push('/reply')">回单</button>
          <button
            v-for="tab in tabTickets"
            :key="tab.id"
            class="tab"
            :class="{ active: routeHasTicket && tab.id === ticket?.id }"
            type="button"
            @click="selectTicket(tab.id)"
          >
            {{ tab.no }}
          </button>
        </nav>

        <section v-if="routeMode === 'home'" class="home-view">
          <div class="case-toolbar home-toolbar">
            <div>
              <h1>工作台</h1>
              <div class="toolbar-meta">
                <span>信用卡综合业务处理门户</span>
                <span>当前班次：早班</span>
                <span>机构：信用卡运营组</span>
              </div>
            </div>
            <div class="toolbar-actions">
              <button class="btn-primary" type="button" @click="router.push('/dispatch')">进入发单</button>
              <button class="btn-plain" type="button" @click="router.push('/reply')">进入回单</button>
            </div>
          </div>

          <section class="dashboard-strip">
            <button v-for="card in dashboardCards" :key="card.label" type="button" @click="card.label === '待发单' ? router.push('/dispatch') : router.push('/reply')">
              <span>{{ card.label }}</span>
              <strong>{{ card.value }}</strong>
              <small>{{ card.hint }}</small>
            </button>
          </section>

          <MetricsDashboard :metrics="store.metrics" />

          <section class="sys-panel">
            <div class="sys-title">业务流转 <small>今日处理进度</small></div>
            <BusinessFlow :stages="businessFlow" />
          </section>

          <section class="home-grid">
            <section class="sys-panel">
              <div class="sys-title">最近发单 <small>来电登记</small></div>
              <table class="compact-table">
                <thead><tr><th>时间</th><th>客户</th><th>分类</th><th>来电摘要</th></tr></thead>
                <tbody>
                  <tr v-for="call in store.callRecords.slice(0, 6)" :key="call.id" @click="router.push(`/dispatch/${businessCategories.find(item => item.scenes.includes(call.scenario))?.id || ''}`)">
                    <td>{{ call.callMeta.callStartedAt ? formatShortTime(call.callMeta.callStartedAt) : '-' }}</td>
                    <td>{{ call.callMeta.customerName || call.callMeta.customerId }}</td>
                    <td>{{ call.scenario }}</td>
                    <td>{{ call.transcript.slice(0, 48) }}...</td>
                  </tr>
                </tbody>
              </table>
            </section>
            <section class="sys-panel">
              <div class="sys-title">待回单提醒 <small>优先处理</small></div>
              <table class="compact-table">
                <thead><tr><th>工单编号</th><th>客户</th><th>分类</th><th>状态</th></tr></thead>
                <tbody>
                  <tr v-for="item in store.tickets.filter(t => t.status !== 'closed').slice(0, 6)" :key="item.id" @click="selectTicket(item.id)">
                    <td class="mono">{{ item.no }}</td>
                    <td>{{ item.customerName }}</td>
                    <td>{{ item.scene || item.subcategory }}</td>
                    <td><span :class="statusClass(ticketStatus(item).tone)">{{ ticketStatus(item).label }}</span></td>
                  </tr>
                </tbody>
              </table>
            </section>
          </section>
        </section>

        <section v-else-if="routeMode === 'dispatch'" class="dispatch-view">
          <div class="case-toolbar">
            <div>
              <h1>{{ selectedCategory ? `${selectedCategory.label}发单` : '发单工作台' }}</h1>
              <div class="toolbar-meta">
                <span>通话记录转标准工单</span>
                <span v-if="selectedCategory">编号段：{{ selectedCategory.code }}</span>
                <span v-if="draftGenerationStatus" class="status blue">{{ draftGenerationStatus }}</span>
              </div>
            </div>
            <div class="toolbar-actions">
              <button class="btn-plain" type="button" @click="handleSaveDispatchDraft" title="仅本地暂存，不提交系统">暂存（本地）</button>
              <button id="dispatch-submit" class="btn-primary" data-page-agent-target="dispatch-submit" type="button" :disabled="!canSubmitDraft" @click="handleSubmitDraft">发送</button>
            </div>
          </div>

          <section class="sys-panel">
            <div class="sys-title">业务流转 <small>发单阶段</small></div>
            <BusinessFlow :stages="businessFlow.slice(0, 3)" compact />
          </section>

          <section id="call-intake-workspace" class="dispatch-grid" data-page-agent-target="call-intake-workspace">
            <section class="sys-panel call-list-pane">
              <div class="sys-title">通话记录 <small>{{ filteredCalls.length }} 条</small></div>
              <button
                v-for="record in filteredCalls"
                :key="record.id"
                class="call-record-item"
                :class="{ active: selectedCallId === record.id }"
                type="button"
                @click="selectCallRecord(record.id)"
              >
                <span class="mono">{{ record.callMeta.callStartedAt || record.id }}</span>
                <strong>{{ record.callMeta.customerName || '未知客户' }} / {{ record.scenario }}</strong>
                <small>{{ record.callMeta.customerId }} · {{ record.riskLevel === 'high' ? '紧急件' : record.riskLevel === 'medium' ? '普通加急' : '一般件' }}</small>
              </button>
              <div v-if="!filteredCalls.length" class="empty-panel">当前分类暂无通话记录。</div>
            </section>

            <section id="call-transcript-panel" class="sys-panel call-transcript-pane" data-page-agent-target="call-transcript-panel">
              <div class="sys-title">来电内容 <small>{{ selectedCall?.callMeta.agent || '坐席A1027' }}</small></div>
              <textarea v-model="customTranscript" class="transcript-box" data-page-agent-target="call-transcript" />
            </section>

            <section id="ticket-draft-form" class="sys-panel ticket-draft-form" data-page-agent-target="ticket-draft-form">
              <div class="sys-title">标准工单 <small>{{ draftRequiredMissing.length ? `待补充 ${draftRequiredMissing.join('、')}` : '可发送' }}</small></div>
              <div class="draft-section-title">基础信息</div>
              <div class="draft-form-grid">
                <label v-for="field in commonFields" :key="field.name" :class="{ full: field.type === 'textarea' }">
                  <span>{{ field.label }}</span>
                  <select
                    v-if="field.type === 'select'"
                    :value="draftFieldValue(field)"
                    :data-page-agent-target="`dispatch-${field.name}`"
                    @change="updateDraftField(field, ($event.target as HTMLSelectElement).value)"
                  >
                    <option v-for="option in field.options" :key="option" :value="option">{{ field.name === 'priority' ? priorityLabel(option) : option }}</option>
                  </select>
                  <textarea
                    v-else-if="field.type === 'textarea'"
                    :value="draftFieldValue(field)"
                    :data-page-agent-target="`dispatch-${field.name}`"
                    class="draft-content-box"
                    @input="updateDraftField(field, ($event.target as HTMLTextAreaElement).value)"
                  />
                  <input
                    v-else
                    :value="draftFieldValue(field)"
                    :data-page-agent-target="`dispatch-${field.name}`"
                    type="text"
                    @input="updateDraftField(field, ($event.target as HTMLInputElement).value)"
                  />
                </label>
              </div>

              <div class="draft-section-title">分类字段 <small>{{ currentScene || '待选择' }}</small></div>
              <div class="draft-form-grid">
                <label v-for="field in scenarioFields" :key="field.name" :class="{ full: field.type === 'textarea' }">
                  <span>{{ field.label }}</span>
                  <select
                    v-if="field.type === 'select'"
                    :value="specificFieldValue(field.name)"
                    :data-page-agent-target="`dispatch-${field.name}`"
                    @change="updateSpecificField(field.name, ($event.target as HTMLSelectElement).value)"
                  >
                    <option value="">请选择</option>
                    <option v-for="option in field.options" :key="option" :value="option">{{ option }}</option>
                  </select>
                  <textarea
                    v-else-if="field.type === 'textarea'"
                    :value="specificFieldValue(field.name)"
                    :data-page-agent-target="`dispatch-${field.name}`"
                    class="draft-content-box"
                    @input="updateSpecificField(field.name, ($event.target as HTMLTextAreaElement).value)"
                  />
                  <input
                    v-else
                    :value="specificFieldValue(field.name)"
                    :data-page-agent-target="`dispatch-${field.name}`"
                    type="text"
                    @input="updateSpecificField(field.name, ($event.target as HTMLInputElement).value)"
                  />
                </label>
                <div v-if="!scenarioFields.length" class="empty-panel">选择分类或生成草稿后展示对应字段。</div>
              </div>
              <div class="field-source-strip">
                <span v-for="field in store.ticketDraftResult?.keyFields || []" :key="field.name">
                  {{ field.label }}：已从来电内容带入
                </span>
                <span v-if="!store.ticketDraftResult">生成草稿后展示已带入字段。</span>
              </div>
            </section>
          </section>
        </section>

        <section v-else-if="routeMode === 'reply-list'" class="reply-list-view">
          <div class="case-toolbar">
            <div>
              <h1>{{ selectedCategory ? `${selectedCategory.label}回单` : '回单工作台' }}</h1>
              <div class="toolbar-meta">
                <span>待接单处理与回单复核</span>
                <span v-if="selectedCategory">编号段：{{ selectedCategory.code }}</span>
              </div>
            </div>
            <button class="btn-primary" type="button" :disabled="!queueTickets.length" @click="queueTickets[0] && selectTicket(queueTickets[0].id)">处理下一张</button>
          </div>

          <section class="sys-panel">
            <div class="sys-title">业务流转 <small>回单阶段</small></div>
            <BusinessFlow :stages="businessFlow.slice(3)" compact />
          </section>

          <section class="case-query-bar">
            <label>
              <span>快速查询</span>
              <input v-model="quickQuery" type="search" placeholder="工单号 / 客户号 / 姓名 / 分类" />
            </label>
            <label>
              <span>处理状态</span>
              <select v-model="statusFilter">
                <option value="all">全部状态</option>
                <option value="open">待处理</option>
                <option value="in_progress">处理中</option>
                <option value="pending_info">待补充</option>
                <option value="pending_human_confirm">待确认</option>
                <option value="pending_human_review">待复核</option>
                <option value="closed">已结案</option>
              </select>
            </label>
          </section>

          <section class="sys-panel">
            <div class="sys-title">待回单队列 <small>{{ queueTickets.length }} 条</small></div>
            <table class="compact-table queue-table">
              <thead>
                <tr><th>工单编号</th><th>客户号</th><th>客户姓名</th><th>分类</th><th>件别</th><th>状态</th><th>接单单位</th><th>规定回件日期</th></tr>
              </thead>
              <tbody>
                <tr v-for="item in queueTickets" :key="item.id" @click="selectTicket(item.id)">
                  <td class="mono">{{ item.no }}</td>
                  <td class="mono">{{ item.customerId }}</td>
                  <td>{{ item.customerName }}</td>
                  <td>{{ item.scene || item.subcategory }}</td>
                  <td><span :class="statusClass(ticketRisk(item).tone)">{{ priorityLabel(item.priority) }}</span></td>
                  <td><span :class="statusClass(ticketStatus(item).tone)">{{ ticketStatus(item).label }}</span></td>
                  <td>{{ item.receiveUnit || item.department || '-' }}</td>
                  <td>{{ item.deadline || item.dueAt || '-' }}</td>
                </tr>
                <tr v-if="!queueTickets.length"><td colspan="8" class="empty-cell">当前分类暂无待回单。</td></tr>
              </tbody>
            </table>
          </section>
        </section>

        <section v-else-if="ticket" id="enterprise-ticket-detail" class="reply-detail-view" data-page-agent-target="enterprise-ticket-detail">
          <div class="case-toolbar">
            <div>
              <h1>{{ ticket.title }}</h1>
              <div class="toolbar-meta">
                <span class="mono">{{ ticket.no }}</span>
                <span>客户：{{ ticket.customerName }}</span>
                <span>分类：{{ ticket.scene || ticket.subcategory }}</span>
                <span :class="statusClass(ticketRisk(ticket).tone)">{{ ticket.riskLabel }}</span>
                <span :class="statusClass(ticketStatus(ticket).tone)">{{ ticketStatus(ticket).label }}</span>
              </div>
            </div>
            <div class="toolbar-actions">
              <button class="btn-plain" type="button" :disabled="!store.replyDraft" @click="handleSaveReply">保存回单</button>
              <button class="btn-primary" type="button" :disabled="!canClose" @click="handleClose">结案</button>
              <button class="btn-plain" type="button" :disabled="store.isProcessing" @click="openActionDialog('assign')">转派</button>
              <button
                class="btn-plain"
                type="button"
                :disabled="store.isProcessing || ticket.status === 'cancelled' || ticket.status === 'closed'"
                @click="openActionDialog('cancel')"
              >取消工单</button>
              <button
                v-if="ticket.status === 'cancelled'"
                class="btn-plain"
                type="button"
                @click="openActionDialog('reopen')"
              >重开</button>
            </div>
          </div>

          <section class="sys-panel">
            <div class="sys-title">业务流转 <small>当前工单</small></div>
            <BusinessFlow :stages="businessFlow" />
          </section>

          <section class="case-grid">
            <section class="sys-panel">
              <div class="sys-title">工单详情 <small>发单信息</small></div>
              <div class="field-grid">
                <div class="field"><label>发单编号</label><strong class="mono">{{ ticket.no }}</strong></div>
                <div class="field"><label>客户号</label><strong class="mono">{{ ticket.customerId }}</strong></div>
                <div class="field"><label>客户姓名</label><strong>{{ ticket.customerName }}</strong></div>
                <div class="field"><label>手机号</label><strong>{{ ticket.phone }}</strong></div>
                <div class="field"><label>件别</label><strong>{{ priorityLabel(ticket.priority) }}</strong></div>
                <div class="field"><label>处理状态</label><strong>{{ ticketStatus(ticket).label }}</strong></div>
                <div class="field"><label>业务类型</label><strong>{{ ticket.bizType || ticket.category || ticket.scene }}</strong></div>
                <div class="field"><label>业务细分类型</label><strong>{{ ticket.bizSubType || ticket.subcategory || '-' }}</strong></div>
                <div class="field"><label>接单单位</label><strong>{{ ticket.receiveUnit || ticket.department || '-' }}</strong></div>
                <div class="field"><label>规定回件日期</label><strong>{{ ticket.deadline || ticket.dueAt || '-' }}</strong></div>
              </div>
              <div class="case-text">{{ ticket.content }}</div>
              <!-- 结案/取消后补充展示 -->
              <div v-if="ticket.finalReply" class="case-text case-text-secondary">
                <label>最终回复</label>{{ ticket.finalReply }}
              </div>
              <div v-if="ticket.cancelReason" class="case-text case-text-secondary">
                <label>取消原因</label>{{ ticket.cancelReason }}
              </div>
              <div v-if="ticket.closedAt" class="case-text case-text-secondary">
                <label>结案时间</label>{{ ticket.closedAt }}
              </div>
            </section>

            <section class="sys-panel">
              <div class="sys-title">处理记录 <small>近期操作</small></div>
              <ul class="log-list">
                <li v-for="operation in store.operationLogs.slice(0, 6)" :key="operation.id">
                  <span>{{ formatShortTime(operation.createdAt) }}</span>
                  <strong>{{ operationLabel(operation.operation) }}</strong>
                  <small>{{ operatorLabel(operation.operator) }} / {{ statusLabelFor(operation.toStatus) }}</small>
                </li>
                <li v-if="!store.operationLogs.length">
                  <span>{{ formatShortTime(ticket.createdAt) }}</span>
                  <strong>工单登记</strong>
                  <small>等待接单处理。</small>
                </li>
              </ul>
            </section>

            <section id="mock-tool-process" class="sys-panel full-row">
              <div class="sys-title">外部系统操作监测 <small>{{ mockToolSteps.length }} 次调用</small></div>
              <div v-if="mockToolSteps.length" class="mock-tool-flow">
                <article v-for="step in mockToolSteps" :key="step.id" class="mock-tool-step" :class="step.status">
                  <div>
                    <span>{{ step.source }}</span>
                    <strong>{{ step.title }}</strong>
                  </div>
                  <p>{{ step.detail }}</p>
                  <small v-if="step.evidenceId" class="mono">{{ step.evidenceId }}</small>
                </article>
              </div>
              <div v-else-if="store.aiResult?.missingFields?.length" class="empty-panel">本次记录未返回外部系统调用明细；请先补充缺失信息，再重新处理。</div>
              <div v-else class="empty-panel">点击“开始处理”后展示客户、卡片、交易或权益系统核验过程。</div>
            </section>

            <section id="sunpilot-fields" class="sys-panel">
              <div class="sys-title">核验结果 <small>客户、卡片、业务信息</small></div>
              <div class="verification-strip" v-if="verificationItems.length">
                <button v-for="item in verificationItems.slice(0, 6)" :key="item.id" :class="`verification-chip ${item.status}`" type="button">
                  <span>{{ businessText(businessFieldLabel(item.label)) }}</span>
                  <strong>{{ item.value }}</strong>
                  <small>{{ businessText(item.note) }}</small>
                </button>
              </div>
              <div v-else class="empty-panel">点击“开始处理”后展示核验结果。</div>
            </section>

            <section id="missing-info-panel" class="sys-panel missing-info-panel">
              <div class="sys-title">待补充信息 <small>{{ missingFields.length ? '补齐后可重新处理' : '当前无缺失' }}</small></div>
              <div v-if="missingFields.length" class="missing-editor">
                <label v-for="field in missingFields" :key="field" class="missing-field">
                  <span>{{ businessFieldLabel(field) }}</span>
                  <input
                    v-model="missingFieldDraft[field]"
                    type="text"
                    :placeholder="`填写${businessFieldLabel(field)}`"
                  />
                  <div class="missing-options">
                    <button
                      v-for="option in missingFieldOptions(field)"
                      :key="`${field}-${option}`"
                      class="assist-tab"
                      type="button"
                      @click="fillMissingField(field, option)"
                    >
                      {{ option }}
                    </button>
                  </div>
                </label>
                <div class="missing-actions">
                  <button class="btn-plain" type="button" @click="generateSupplementQuestion">生成补充话术</button>
                  <button class="btn-plain" type="button" :disabled="!hasMissingSupplementDraft" @click="saveMissingSupplement(false)">暂存补充信息</button>
                  <button class="btn-primary" type="button" :disabled="!hasMissingSupplementDraft || store.isProcessing" @click="saveMissingSupplement(true)">补充后重新处理</button>
                </div>
                <p v-if="supplementStatus" class="supplement-status">{{ supplementStatus }}</p>
              </div>
              <div v-else class="empty-panel">外部系统和工单内容已满足当前处理所需字段。</div>
            </section>

            <section id="sunpilot-evidence" class="sys-panel">
              <div class="sys-title">处理依据 <small>可带入回单</small></div>
              <button v-for="item in evidence" :key="item.id" class="evidence-token" type="button" @click="insertEvidenceText(item.id)">
                <span class="mono">{{ item.id }}</span>
                <small>{{ item.summary }}</small>
              </button>
              <div v-if="!evidence.length" class="empty-panel">暂无处理依据。</div>
            </section>

            <section id="enterprise-reply" class="sys-panel full-row reply-workspace">
              <div class="sys-title">回单工作区 <small>{{ replyWorkspaceStatus }}</small></div>
              <div class="reply-command-row">
                <label>
                  <span>回单模板</span>
                  <select v-model="replyTemplate">
                    <option value="standard">标准处理结果</option>
                    <option value="benefit">权益活动</option>
                    <option value="dispute">交易调单</option>
                  </select>
                </label>
                <button class="btn-plain" type="button" @click="applyTemplate">套用模板</button>
                <button class="btn-plain" type="button" :disabled="!store.replyDraft" @click="handleSaveReply">保存回单</button>
                <button class="btn-primary" type="button" :disabled="!canClose" @click="handleClose">提交复核并结案</button>
                <button v-if="needsHumanConfirm" class="btn-primary" type="button" @click="openHumanConfirm">人工确认</button>
                <span :class="statusClass(canClose ? 'green' : 'amber')">{{ replyStatus }}</span>
              </div>
              <div class="reply-grid">
                <section class="reply-pane customer-pane">
                  <header><strong>客户回单</strong><span>{{ replyStatus }}</span></header>
                  <textarea
                    v-model="store.replyDraft"
                    class="reply-box"
                    data-page-agent-target="page-agent-reply-draft"
                    placeholder="回单内容由坐席复核后提交。"
                    @input="markReplyEdited"
                  />
                </section>
                <section class="reply-pane">
                  <header><strong>{{ activeReplyAssistMeta.label }}</strong><span>{{ activeReplyAssistMeta.status }}</span></header>
                  <div class="assist-switcher">
                    <button
                      v-for="option in replyAssistOptions"
                      :key="option.id"
                      class="assist-tab"
                      :class="{ active: activeReplyAssist === option.id }"
                      type="button"
                      @click="activeReplyAssist = option.id"
                    >
                      {{ option.label }}
                    </button>
                  </div>
                  <textarea
                    class="reply-small-box assist-box"
                    :value="replyAssistValue()"
                    @input="updateReplyAssist(($event.target as HTMLTextAreaElement).value)"
                  />
                  <button class="btn-plain" type="button" :disabled="!replyAssistValue()" @click="applyReplyText(replyAssistValue())">写入回单</button>
                </section>
              </div>
            </section>
          </section>
        </section>
      </main>

      <button
        class="copilot-toggle"
        type="button"
        data-page-agent-not-interactive="true"
        data-sunpilot-panel="true"
        :aria-label="copilotOpen ? '隐藏辅助面板' : '展开辅助面板'"
        :title="copilotOpen ? '隐藏辅助面板' : '展开辅助面板'"
        @click="copilotOpen = !copilotOpen"
      >
        {{ copilotOpen ? '›' : '‹' }}
      </button>

      <aside v-if="copilotOpen" class="copilot" data-page-agent-not-interactive="true" data-sunpilot-panel="true">
        <SunPilotPanel
          @generate-draft="generateDraftFromCall"
          @submit-draft="handleSubmitDraft"
          @start-ai-process="handleProcess"
          @scroll-reply="scrollToId('enterprise-reply')"
          @scroll-missing="scrollToId('missing-info-panel')"
          @open-human-confirm="openHumanConfirm"
        />
      </aside>
    </div>

    <ConfirmDialog
      v-if="showConfirmDialog && ticket"
      @confirm="handleHumanConfirm(true)"
      @reject="handleHumanConfirm(false)"
    />

    <!-- 工单流转对话框 -->
    <div v-if="actionDialog" class="overlay" @click.self="closeActionDialog">
      <section class="dialog" role="dialog" aria-modal="true">
        <!-- 转派 -->
        <template v-if="actionDialog === 'assign'">
          <h2>转派工单</h2>
          <p>将工单转交其他经办人或单位继续处理。</p>
          <div class="action-form">
            <label>
              <span>经办人 <em>*</em></span>
              <input v-model="assigneeInput" type="text" placeholder="填写经办人" />
            </label>
            <label>
              <span>接单单位</span>
              <input v-model="departmentInput" type="text" placeholder="填写单位（可选）" />
            </label>
          </div>
          <p v-if="actionStatus" class="action-status">{{ actionStatus }}</p>
          <div class="actions">
            <button class="btn btn-reject" type="button" @click="closeActionDialog">取消</button>
            <button class="btn btn-confirm" type="button" :disabled="!assigneeInput.trim()" @click="handleAssign">确认转派</button>
          </div>
        </template>
        <!-- 取消工单 -->
        <template v-else-if="actionDialog === 'cancel'">
          <h2>取消工单</h2>
          <p>工单将变为已取消状态，如需恢复可使用「重开」操作。</p>
          <div class="action-form">
            <label>
              <span>取消原因 <em>*</em></span>
              <textarea v-model="actionReasonInput" placeholder="请填写取消原因" rows="3" />
            </label>
          </div>
          <p v-if="actionStatus" class="action-status">{{ actionStatus }}</p>
          <div class="actions">
            <button class="btn btn-reject" type="button" @click="closeActionDialog">返回</button>
            <button class="btn btn-confirm" type="button" :disabled="!actionReasonInput.trim()" @click="handleCancel">确认取消</button>
          </div>
        </template>
        <!-- 重开工单 -->
        <template v-else-if="actionDialog === 'reopen'">
          <h2>重开工单</h2>
          <p>将已取消的工单重新激活为「待处理」状态。</p>
          <div class="action-form">
            <label>
              <span>重开备注</span>
              <input v-model="actionReasonInput" type="text" placeholder="填写重开原因（可选）" />
            </label>
          </div>
          <p v-if="actionStatus" class="action-status">{{ actionStatus }}</p>
          <div class="actions">
            <button class="btn btn-reject" type="button" @click="closeActionDialog">返回</button>
            <button class="btn btn-confirm" type="button" @click="handleReopen">确认重开</button>
          </div>
        </template>
      </section>
    </div>
  </div>
</template>

<style scoped>
.enterprise-shell {
  min-height: 100vh;
  background: var(--page);
  color: var(--ink);
}
.topbar {
  height: 42px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--line-dark);
  background: #fff;
}
.brand-strip {
  height: 42px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 14px;
  border: 0;
  border-right: 1px solid var(--line);
  background: var(--brand);
  color: #fff;
  font-weight: 900;
}
.bank-seal {
  width: 24px;
  height: 24px;
  display: grid;
  place-items: center;
  border: 1px solid rgba(255, 255, 255, 0.8);
  font-family: var(--mono);
  font-size: 12px;
}
.top-actions,
.toolbar-meta,
.toolbar-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  padding: 0 10px;
  color: var(--ink-soft);
  font-size: 12px;
}
.layout-core {
  height: calc(100vh - 42px);
  display: grid;
  grid-template-columns: 230px minmax(0, 1fr) 0;
  grid-template-areas: "nav workspace copilot";
  transition: grid-template-columns 180ms ease;
}
.layout-core.copilot-expanded {
  grid-template-columns: 230px minmax(0, 1fr) 376px;
}
.nav-tree {
  grid-area: nav;
  overflow: auto;
  border-right: 1px solid var(--line-dark);
  background: #f8fafc;
}
.tree-head {
  min-height: 34px;
  display: flex;
  align-items: center;
  padding: 8px 12px;
  border-bottom: 1px solid var(--line);
  background: #fff;
  font-size: 13px;
  font-weight: 900;
}
.tree-group {
  display: grid;
  gap: 1px;
  padding: 8px;
}
.tree-title {
  padding: 7px 6px 5px;
  color: var(--ink-soft);
  font-size: 12px;
  font-weight: 900;
}
.tree-root,
.tree-item {
  width: 100%;
  min-height: 30px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 6px 8px;
  border: 0;
  background: transparent;
  color: var(--ink);
  font-size: 12px;
  text-align: left;
  cursor: pointer;
}
.tree-root {
  margin: 8px;
  width: calc(100% - 16px);
  font-weight: 900;
}
.tree-item.sub {
  padding-left: 18px;
}
.tree-root.active,
.tree-item.active {
  background: #edf7f4;
  box-shadow: inset 3px 0 0 var(--green);
}
.tree-root strong,
.tree-item strong {
  color: var(--muted);
  font-family: var(--mono);
  font-size: 11px;
}
.workspace {
  grid-area: workspace;
  min-width: 0;
  overflow: auto;
  background: var(--page);
}
.tabbar {
  min-height: 36px;
  display: flex;
  gap: 1px;
  padding: 6px 8px 0;
  border-bottom: 1px solid var(--line-dark);
  background: #f5f7fa;
}
.tab {
  min-width: 92px;
  height: 30px;
  padding: 0 12px;
  border: 1px solid var(--line);
  border-bottom: 0;
  background: #eef2f6;
  color: var(--ink-soft);
  font-size: 12px;
  font-weight: 900;
}
.tab.active {
  background: #fff;
  color: var(--brand);
}
.case-toolbar {
  min-height: 58px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 10px;
  border-bottom: 1px solid var(--line);
  background: #fff;
}
.case-toolbar h1 {
  margin: 0;
  font-size: 17px;
}
.btn-primary,
.btn-plain {
  min-height: 28px;
  padding: 5px 10px;
  border: 1px solid var(--line-dark);
  background: #fff;
  color: var(--ink);
  font-size: 12px;
  font-weight: 900;
}
.btn-primary {
  border-color: var(--brand-dark);
  background: var(--brand);
  color: #fff;
}
.btn-primary:disabled,
.btn-plain:disabled {
  opacity: 0.48;
  cursor: not-allowed;
}
.sys-panel {
  min-width: 0;
  margin: 8px;
  border: 1px solid var(--line-dark);
  background: #fff;
}
.sys-title {
  min-height: 31px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 6px 10px;
  border-bottom: 1px solid var(--line);
  background: var(--section);
  font-size: 13px;
  font-weight: 900;
}
.sys-title small,
.draft-section-title small {
  color: var(--ink-soft);
  font-size: 12px;
  font-weight: 500;
}
.dashboard-strip {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 1px;
  margin: 8px;
  border: 1px solid var(--line);
  background: var(--line);
}
.dashboard-strip button {
  min-height: 74px;
  display: grid;
  gap: 3px;
  padding: 9px;
  border: 0;
  background: #fff;
  text-align: left;
}
.dashboard-strip strong {
  font-family: var(--mono);
  font-size: 22px;
}
.dashboard-strip small {
  color: var(--muted);
  font-size: 12px;
}
.business-flow {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(128px, 1fr));
  gap: 1px;
  background: var(--line);
}
.business-flow.compact {
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
}
.flow-node {
  min-width: 0;
  min-height: 62px;
  display: grid;
  align-content: center;
  gap: 5px;
  padding: 9px;
  background: #fff;
  box-shadow: inset 0 3px 0 var(--line-dark);
}
.flow-node.done { box-shadow: inset 0 3px 0 var(--green); }
.flow-node.running { box-shadow: inset 0 3px 0 var(--blue); background: #f2f8fc; }
.flow-node.blocked { box-shadow: inset 0 3px 0 var(--amber); background: #fff8ea; }
.flow-node span {
  font-size: 12px;
  font-weight: 900;
}
.flow-node strong {
  color: var(--ink-soft);
  font-size: 12px;
}
.home-grid,
.case-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(320px, 0.82fr);
  gap: 8px;
  padding: 0 8px 8px;
}
.dispatch-grid {
  display: grid;
  grid-template-columns: minmax(190px, 240px) minmax(0, 1fr);
  grid-template-areas:
    "calls transcript"
    "calls draft";
  gap: 8px;
  padding: 0 8px 8px;
}
.call-list-pane {
  grid-area: calls;
  max-height: calc(100vh - 190px);
  overflow: auto;
}
.call-transcript-pane { grid-area: transcript; }
.ticket-draft-form { grid-area: draft; }
.call-record-item {
  width: 100%;
  display: grid;
  gap: 4px;
  padding: 9px 10px;
  border: 0;
  border-bottom: 1px solid var(--line);
  background: transparent;
  color: var(--ink);
  text-align: left;
}
.call-record-item.active {
  background: #eef7f4;
  box-shadow: inset 3px 0 0 var(--green);
}
.call-record-item strong,
.call-record-item small {
  overflow-wrap: anywhere;
  font-size: 12px;
}
.call-record-item small {
  color: var(--muted);
}
.transcript-box,
.draft-content-box,
.reply-box,
.reply-small-box {
  width: 100%;
  min-height: 150px;
  resize: vertical;
  border: 1px solid var(--line);
  background: #fff;
  color: var(--ink);
  padding: 10px;
  line-height: 1.55;
  font-size: 12px;
}
.draft-section-title {
  padding: 9px 10px 0;
  color: var(--ink-soft);
  font-size: 12px;
  font-weight: 900;
}
.draft-form-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 9px;
  padding: 10px;
}
.draft-form-grid label {
  display: grid;
  gap: 4px;
  min-width: 0;
}
.draft-form-grid label.full {
  grid-column: 1 / -1;
}
.draft-form-grid span,
.case-query-bar span {
  color: var(--ink-soft);
  font-size: 11px;
  font-weight: 800;
}
.draft-form-grid input,
.draft-form-grid select,
.case-query-bar input,
.case-query-bar select {
  min-width: 0;
  height: 30px;
  border: 1px solid var(--line);
  padding: 0 8px;
  background: #fff;
  color: var(--ink);
  font-size: 12px;
}
.field-source-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 0 10px 10px;
}
.field-source-strip span {
  padding: 4px 7px;
  border: 1px solid var(--line);
  background: #fff;
  color: var(--ink-2);
  font-size: 11px;
}
.case-query-bar {
  display: grid;
  grid-template-columns: minmax(260px, 1fr) minmax(180px, 220px);
  gap: 8px;
  align-items: end;
  margin: 8px;
  padding: 8px;
  border: 1px solid var(--line-dark);
  background: #fff;
}
.case-query-bar label {
  min-width: 0;
  display: grid;
  gap: 4px;
}
.compact-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
}
.compact-table th,
.compact-table td {
  border: 1px solid var(--line);
  padding: 7px 8px;
  overflow-wrap: anywhere;
  vertical-align: top;
  text-align: left;
  font-size: 12px;
  line-height: 1.45;
}
.compact-table th {
  background: var(--table);
  color: var(--ink-soft);
  font-weight: 900;
}
.queue-table tbody tr,
.home-grid tbody tr {
  cursor: pointer;
}
.queue-table tbody tr:hover,
.home-grid tbody tr:hover {
  background: #fff5f6;
}
.field-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
}
.field {
  min-width: 0;
  min-height: 54px;
  padding: 8px 10px;
  border-right: 1px solid var(--line);
  border-bottom: 1px solid var(--line);
}
.field label {
  display: block;
  margin-bottom: 5px;
  color: var(--muted);
  font-size: 12px;
}
.field strong {
  display: block;
  overflow-wrap: anywhere;
  font-size: 13px;
  line-height: 1.45;
}
.case-text {
  min-height: 100px;
  padding: 10px;
  color: var(--ink);
  font-size: 13px;
  line-height: 1.75;
}
.full-row {
  grid-column: 1 / -1;
}
.verification-strip {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1px;
  background: var(--line);
}
.verification-chip {
  min-width: 0;
  min-height: 74px;
  display: grid;
  gap: 4px;
  padding: 9px 10px;
  border: 0;
  background: #fff;
  text-align: left;
}
.verification-chip strong,
.verification-chip small {
  overflow-wrap: anywhere;
}
.verification-chip small {
  color: var(--muted);
  font-size: 12px;
}
.verification-chip.verified,
.verification-chip.enriched { box-shadow: inset 3px 0 0 var(--green); }
.verification-chip.missing,
.verification-chip.conflict,
.verification-chip.review { box-shadow: inset 3px 0 0 var(--amber); }
.mock-tool-flow {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 1px;
  background: var(--line);
}
.mock-tool-step {
  min-width: 0;
  display: grid;
  gap: 7px;
  align-content: start;
  min-height: 106px;
  padding: 10px;
  background: #fff;
  box-shadow: inset 3px 0 0 var(--line-dark);
}
.mock-tool-step.done { box-shadow: inset 3px 0 0 var(--green); }
.mock-tool-step.running { box-shadow: inset 3px 0 0 var(--blue); background: #f2f8fc; }
.mock-tool-step.blocked { box-shadow: inset 3px 0 0 var(--amber); background: #fffaf0; }
.mock-tool-step div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.mock-tool-step span,
.mock-tool-step small {
  color: var(--muted);
  font-size: 12px;
}
.mock-tool-step strong {
  color: var(--ink);
  font-size: 12px;
}
.mock-tool-step p {
  margin: 0;
  color: var(--ink-soft);
  font-size: 12px;
  line-height: 1.55;
  overflow-wrap: anywhere;
}
.missing-info-panel {
  align-self: start;
}
.missing-editor {
  display: grid;
  gap: 10px;
  padding: 10px;
}
.missing-field {
  display: grid;
  gap: 6px;
}
.missing-field > span {
  color: var(--ink-soft);
  font-size: 12px;
  font-weight: 900;
}
.missing-field input {
  min-width: 0;
  height: 30px;
  border: 1px solid var(--line);
  padding: 0 8px;
  background: #fff;
  color: var(--ink);
  font-size: 12px;
}
.missing-options,
.missing-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.supplement-status {
  margin: 0;
  color: var(--ink-soft);
  font-size: 12px;
  line-height: 1.55;
}
.log-list {
  margin: 0;
  padding: 0 10px 10px;
  list-style: none;
}
.log-list li {
  padding: 9px 0;
  border-bottom: 1px solid var(--line);
}
.log-list span,
.log-list small {
  color: var(--muted);
  font-size: 12px;
}
.log-list strong {
  display: block;
  margin: 3px 0;
  font-size: 12px;
}
.reply-command-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  padding: 8px;
  border-bottom: 1px solid var(--line);
}
.reply-command-row label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--ink-soft);
  font-size: 12px;
  font-weight: 900;
}
.reply-command-row select {
  height: 28px;
  border: 1px solid var(--line-dark);
  background: #fff;
  color: var(--ink);
  font-size: 12px;
}
.reply-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(320px, 0.9fr);
  gap: 1px;
  background: var(--line);
}
.reply-pane {
  min-width: 0;
  display: grid;
  align-content: start;
  gap: 8px;
  padding: 10px;
  background: #fff;
}
.reply-pane header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 13px;
}
.reply-pane header span {
  color: var(--muted);
  font-size: 12px;
}
.reply-pane .reply-box {
  min-height: 260px;
}
.reply-small-box {
  min-height: 190px;
  background: var(--panel-2);
}
.assist-switcher {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.assist-tab {
  min-height: 26px;
  padding: 0 9px;
  border: 1px solid var(--line);
  background: #fff;
  color: var(--ink-soft);
  font-size: 12px;
  font-weight: 900;
}
.assist-tab.active {
  border-color: var(--brand);
  background: #eef7f4;
  color: var(--brand);
}
.assist-box {
  min-height: 232px;
}
.evidence-token {
  min-width: 0;
  display: grid;
  gap: 4px;
  margin: 8px;
  padding: 8px;
  border: 1px solid var(--line);
  background: var(--panel-2);
  text-align: left;
}
.evidence-token span,
.evidence-token small {
  overflow-wrap: anywhere;
}
.evidence-token small {
  color: var(--ink-soft);
  font-size: 12px;
  line-height: 1.45;
}
.empty-panel,
.empty-cell {
  padding: 16px;
  color: var(--muted);
  font-size: 12px;
  text-align: center;
}
.status {
  display: inline-flex;
  align-items: center;
  min-height: 22px;
  padding: 2px 7px;
  border: 1px solid var(--line-dark);
  background: #fff;
  font-size: 12px;
  font-weight: 900;
  white-space: nowrap;
}
.status.red { border-color: rgba(180, 35, 53, 0.3); background: #fff0f2; color: var(--danger); }
.status.amber { border-color: rgba(196, 123, 24, 0.34); background: #fff7e8; color: var(--warn); }
.status.green { border-color: rgba(31, 138, 91, 0.28); background: #edf9f2; color: var(--ok); }
.status.blue { border-color: rgba(33, 108, 158, 0.25); background: #eef7fd; color: var(--blue); }
.status.neutral { background: var(--table); color: var(--ink-soft); }
.copilot-toggle {
  position: fixed;
  top: 50%;
  right: 0;
  z-index: 7;
  width: 22px;
  height: 52px;
  display: grid;
  place-items: center;
  padding: 0;
  border: 1px solid #d7e0ea;
  border-right: 0;
  border-radius: 12px 0 0 12px;
  background: rgba(255, 255, 255, 0.92);
  color: #475569;
  font-size: 22px;
  font-weight: 900;
  transform: translateY(-50%);
}
.copilot {
  grid-area: copilot;
  position: sticky;
  top: 0;
  align-self: start;
  width: 376px;
  height: calc(100vh - 42px);
  overflow: hidden;
  border-left: 1px solid #dfe5ec;
  background: #fff;
}
.mono {
  font-family: var(--mono);
}
@media (max-width: 1180px) {
  .layout-core,
  .layout-core.copilot-expanded {
    height: auto;
    min-height: calc(100vh - 42px);
    grid-template-columns: 1fr;
    grid-template-areas:
      "workspace"
      "copilot"
      "nav";
  }
  .nav-tree,
  .copilot {
    position: static;
    width: auto;
    height: auto;
    max-height: 360px;
  }
  .home-grid,
  .case-grid,
  .dispatch-grid {
    grid-template-columns: 1fr;
    grid-template-areas:
      "calls"
      "transcript"
      "draft";
  }
  .dashboard-strip,
  .business-flow,
  .field-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .reply-grid {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 720px) {
  .topbar,
  .case-toolbar {
    align-items: flex-start;
    flex-direction: column;
    height: auto;
  }
  .brand-strip {
    width: 100%;
    border-right: 0;
  }
  .tabbar {
    overflow-x: auto;
  }
  .dashboard-strip,
  .business-flow,
  .draft-form-grid,
  .field-grid,
  .verification-strip {
    grid-template-columns: 1fr;
  }
  .case-query-bar {
    grid-template-columns: 1fr;
  }
}
/* 工单流转对话框 */
.overlay {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background: rgba(31, 41, 51, 0.52);
}
.dialog {
  width: min(440px, 100%);
  padding: 22px;
  border: 1px solid var(--line-dark);
  background: var(--panel, #fff);
  box-shadow: 0 24px 70px rgba(31, 41, 51, 0.28);
}
.dialog h2 {
  margin: 0 0 8px;
  font-size: 17px;
}
.dialog p {
  margin: 6px 0;
  color: var(--ink-soft);
  font-size: 13px;
  line-height: 1.7;
}
.action-form {
  display: grid;
  gap: 10px;
  margin: 14px 0;
}
.action-form label {
  display: grid;
  gap: 4px;
}
.action-form span {
  font-size: 12px;
  font-weight: 900;
}
.action-form em {
  color: var(--danger);
  font-style: normal;
}
.action-form input,
.action-form textarea {
  width: 100%;
  padding: 6px 8px;
  border: 1px solid var(--line-dark);
  font-size: 13px;
  font-family: inherit;
  box-sizing: border-box;
}
.action-status {
  color: var(--warn);
  font-size: 12px;
}
.actions {
  display: flex;
  gap: 10px;
  margin-top: 16px;
}
.btn {
  flex: 1;
  padding: 8px;
  border: 1px solid var(--line-dark);
  font-size: 13px;
  font-weight: 900;
  cursor: pointer;
}
.btn-confirm {
  border-color: var(--brand-dark);
  background: var(--brand);
  color: #fff;
}
.btn-confirm:disabled {
  opacity: 0.48;
  cursor: not-allowed;
}
.btn-reject {
  border-color: rgba(180, 35, 53, 0.3);
  background: var(--red-soft, #fff0f2);
  color: var(--danger);
}
</style>
