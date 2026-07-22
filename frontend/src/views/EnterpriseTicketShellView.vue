<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ConfirmDialog from '../components/ai/ConfirmDialog.vue'
import { evalApi } from '../api'
import { PageActionRunner, createPageTaskPlan } from '../page-agent'
import { useTicketStore } from '../stores/ticket'
import type { CallRecordSample, CreateTicketPayload, EvaluationMetrics, PageBusinessContext, Ticket } from '../types'
import {
  businessSteps,
  bucketMatches,
  type CopilotSuggestion,
  copilotSuggestion,
  enterpriseMenuGroups,
  evidenceItems,
  fieldVerificationItems,
  formatMs,
  formatPercent,
  operationLogs,
  replyWorkspaceSections,
  riskMeta,
  scenarioFamily,
  statusMeta,
  suggestedAction,
  workBuckets,
} from '../utils/business'

const route = useRoute()
const router = useRouter()
const store = useTicketStore()

const activeMenu = ref('all')
const activeBucket = ref('all')
const copilotOpen = ref(true)
const auditOpen = ref(false)
const confirmVisible = ref(false)
const operationError = ref('')
const metrics = ref<EvaluationMetrics | null>(null)
const editableTitle = ref('')
const assignTo = ref('')
const cancelReason = ref('')
const replyTemplate = ref('standard')
const quickQuery = ref('')
const statusFilter = ref('all')
const internalNoteDraft = ref('')
const reviewSummaryDraft = ref('')
const customerQuestionDraft = ref('')
const followUpDraft = ref('')
const replyTouched = ref(false)
const selectedCallId = ref('')
const customTranscript = ref('')
const draftForm = ref<CreateTicketPayload>(emptyTicketDraft())
const draftFieldTouched = ref<Record<string, boolean>>({})
const draftGenerationStatus = ref('')
const pageInstruction = ref('根据这通电话帮我发单')
const pageAgentRunner = new PageActionRunner()
const pageAgentShouldStop = ref(false)
const pendingAutoReply = ref(false)

const ticketId = computed(() => route.params.id as string | undefined)
const ticket = computed(() => store.selectedTicket)
const routeHasTicket = computed(() => Boolean(ticketId.value))

const menuGroups = computed(() => enterpriseMenuGroups(store.tickets, activeMenu.value))
const buckets = computed(() => workBuckets(store.tickets))
const family = computed(() => ticket.value ? scenarioFamily(ticket.value, store.aiResult) : null)
const status = computed(() => ticket.value ? statusMeta(ticket.value.status) : null)
const risk = computed(() => ticket.value ? riskMeta(ticket.value.riskLevel, ticket.value.riskLabel) : null)
const evidence = computed(() => evidenceItems(store.aiResult, store.toolCalls))
const logs = computed(() => operationLogs(ticket.value, store.aiResult, store.traceSteps, store.toolCalls, store.operationLogs))
const flowSteps = computed(() => businessSteps(store.traceSteps, store.aiResult, store.isProcessing))
const verificationItems = computed(() => fieldVerificationItems(store.aiResult))
const replySections = computed(() => replyWorkspaceSections(store.aiResult, ticket.value))
const suggestion = computed<CopilotSuggestion>(() => copilotSuggestion(ticket.value, store.aiResult, store.isProcessing))
const filteredTickets = computed(() => store.tickets.filter(item => {
  const text = `${item.title} ${item.scene} ${item.content}`
  const queryText = quickQuery.value.trim().toLowerCase()
  const quickOk = !queryText || [
    item.no,
    item.customerId,
    item.customerName,
    item.category,
    item.subcategory,
    item.assignee,
    item.title,
  ].some(value => String(value || '').toLowerCase().includes(queryText))
  const statusOk = statusFilter.value === 'all' || item.status === statusFilter.value
  const detailMenuOk = activeMenu.value === 'dining'
    ? /餐饮|满减|DINING/i.test(text)
    : activeMenu.value === 'airport'
      ? /机场|贵宾厅/i.test(text)
      : activeMenu.value === 'points'
        ? /积分|兑换/i.test(text)
        : activeMenu.value === 'phone'
          ? /手机|手机号/i.test(text)
          : activeMenu.value === 'contact'
            ? /联系人/i.test(text)
            : activeMenu.value === 'company'
              ? /商务卡|公司资料/i.test(text)
              : activeMenu.value === 'fraud'
                ? /非本人|盗刷/i.test(text)
                : activeMenu.value === 'chargeback'
                  ? /调单|拒付/i.test(text)
                  : activeMenu.value === 'oversea'
                    ? /境外/i.test(text)
                    : activeMenu.value === 'limit'
                      ? /额度/i.test(text)
                      : activeMenu.value === 'annual-fee'
                        ? /年费/i.test(text)
                        : activeMenu.value === 'repayment'
                          ? /还款|延期/i.test(text)
                          : activeMenu.value === 'credit'
                            ? /征信/i.test(text)
                            : activeMenu.value === 'cross-team'
                              ? /跨部门|协办/i.test(text)
                              : activeMenu.value === 'retry'
                                ? item.status === 'failed'
                                : true
  const detailMenuIds = ['dining', 'airport', 'points', 'phone', 'contact', 'company', 'fraud', 'chargeback', 'oversea', 'limit', 'annual-fee', 'repayment', 'credit', 'cross-team', 'retry']
  const familyOk = activeMenu.value === 'all' || ['info', 'confirm', 'review', 'escalated'].includes(activeMenu.value) || detailMenuIds.includes(activeMenu.value)
    ? true
    : scenarioFamily(item).id === activeMenu.value
  const bucketOk = activeBucket.value === 'all' || bucketMatches(activeBucket.value, item)
  const statusMenuOk = activeMenu.value === 'info'
    ? item.status === 'pending_info'
    : activeMenu.value === 'confirm'
      ? item.status === 'pending_human_confirm'
      : activeMenu.value === 'review'
        ? item.status === 'pending_human_review'
        : activeMenu.value === 'escalated'
          ? ['escalated', 'failed'].includes(item.status)
          : true
  return familyOk && bucketOk && statusMenuOk && detailMenuOk && quickOk && statusOk
}))
const queueTickets = computed(() => filteredTickets.value.slice(0, 12))
const replyStatus = computed(() => store.replyDraft ? '草稿已生成' : '等待生成')
const canClose = computed(() => Boolean(
  ticket.value &&
  ticket.value.status === 'pending_human_review' &&
  store.replyDraft &&
  !store.isProcessing &&
  store.aiResult?.notification?.closureSuggestion?.canClose,
))
const replyWorkspaceStatus = computed(() => {
  if (!store.replyDraft) return '未生成'
  if (ticket.value?.status === 'closed') return '已提交'
  if (canClose.value) return '可结案'
  return replyTouched.value ? '坐席已编辑' : '已填入'
})
const needsHumanConfirm = computed(() => ticket.value?.status === 'pending_human_confirm')
const canCancel = computed(() => Boolean(ticket.value && !['closed', 'cancelled'].includes(ticket.value.status)))
const canReopen = computed(() => Boolean(ticket.value && ['closed', 'cancelled', 'escalated', 'failed', 'pending_info'].includes(ticket.value.status)))
const showConfirmDialog = computed(() => Boolean(ticket.value && (store.workflowPaused || confirmVisible.value)))
const tabTickets = computed(() => {
  const selected = ticket.value ? [ticket.value] : []
  const others = store.tickets.filter(item => item.id !== ticket.value?.id).slice(0, 2)
  return [...selected, ...others]
})
const selectedCall = computed<CallRecordSample | null>(() =>
  store.callRecords.find(item => item.id === selectedCallId.value) || store.callRecords[0] || null
)
const draftRequiredMissing = computed(() => {
  const required: Array<[keyof CreateTicketPayload, string]> = [
    ['title', '标题'],
    ['customerName', '客户姓名'],
    ['phone', '预留手机'],
    ['cardLast4', '卡尾号'],
    ['scene', '业务场景'],
    ['content', '发单内容'],
  ]
  return required.filter(([key]) => !String(draftForm.value[key] || '').trim()).map(([, label]) => label)
})
const canSubmitDraft = computed(() => draftRequiredMissing.value.length === 0)
const pageAgentLogs = computed(() => store.pageActionLogs.slice(0, 10))
const pageAgentBusy = computed(() => ['thinking', 'executing', 'retrying'].includes(store.pageAgentStatus))
const pageAgentStatusLabel = computed(() => {
  const labels = {
    thinking: '思考中',
    executing: '执行中',
    executed: '已执行',
    retrying: '重试中',
    error: '异常',
    done: '完成',
    stopped: '已接管',
  }
  return labels[store.pageAgentStatus]
})

onMounted(async () => {
  await Promise.all([store.fetchTickets(), store.fetchCallRecords()])
  if (!selectedCallId.value && store.callRecords[0]) {
    selectCallRecord(store.callRecords[0].id)
  }
  await loadRouteTicket(ticketId.value)
  try {
    metrics.value = await evalApi.metrics()
  } catch {
    metrics.value = null
  }
})

onBeforeUnmount(() => {
  pageAgentRunner.stop()
})

watch(ticketId, async id => {
  await loadRouteTicket(id)
})

watch(selectedCall, current => {
  if (!current) return
  customTranscript.value = current.transcript
}, { immediate: true })

watch([() => store.aiResult, pageAgentBusy], ([result, busy]) => {
  if (!result || !pendingAutoReply.value || busy) return
  pendingAutoReply.value = false
  runPageAgentTask('继续根据处理建议自动回单')
})

watch(ticket, current => {
  editableTitle.value = current?.title || ''
  assignTo.value = current?.assignee || ''
  cancelReason.value = ''
  replyTouched.value = false
}, { immediate: true })

watch([() => store.aiResult, ticket], () => {
  const sections = replySections.value
  internalNoteDraft.value = sections.find(section => section.id === 'internal')?.body || ''
  reviewSummaryDraft.value = sections.find(section => section.id === 'review')?.body || ''
  customerQuestionDraft.value = sections.find(section => section.id === 'question')?.body || ''
  followUpDraft.value = sections.find(section => section.id === 'followUp')?.body || ''
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
    priority: 'normal',
    channel: '客服热线发单',
    assignee: '坐席 A1027',
    department: '信用卡运营组',
    riskLabel: '低风险',
    riskLevel: 'low',
    content: '',
  }
}

function selectCallRecord(id: string) {
  selectedCallId.value = id
  const record = store.callRecords.find(item => item.id === id)
  if (record) customTranscript.value = record.transcript
}

function markDraftFieldEdited(field: keyof CreateTicketPayload) {
  draftFieldTouched.value[field] = true
}

async function generateDraftFromCall() {
  operationError.value = ''
  draftGenerationStatus.value = '正在调用发单 Agent...'
  try {
    const payload = selectedCall.value && selectedCall.value.transcript === customTranscript.value
      ? { sampleId: selectedCall.value.id, operatorId: 'desk-a1027' }
      : { transcript: customTranscript.value, callMeta: selectedCall.value?.callMeta, operatorId: 'desk-a1027' }
    const result = await store.generateTicketDraft(payload)
    draftForm.value = { ...emptyTicketDraft(), ...result.ticketDraft }
    draftFieldTouched.value = {}
    draftGenerationStatus.value = `已生成草稿：${result.detectedTicketType} / 置信度 ${(result.confidence * 100).toFixed(0)}%`
    pageInstruction.value = '根据这通电话帮我发单'
    return result
  } catch {
    draftGenerationStatus.value = '发单 Agent 调用失败，请检查后端 /api/call-records/generate-ticket-draft。'
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
    const created = await store.createTicket({
      ...draftForm.value,
      id: `call_${Date.now().toString().slice(-8)}`,
      no: `T${new Date().toISOString().slice(0, 10).replace(/-/g, '')}${Date.now().toString().slice(-6)}`,
    })
    await router.push(`/tickets/${created.id}`)
    pendingAutoReply.value = true
    pageInstruction.value = '生成处理建议并自动回单'
  } catch {
    operationError.value = '提交发单失败，请确认工单字段和编号是否有效。'
  }
}

function buildPageBusinessContext(instruction: string): PageBusinessContext {
  const onHome = !routeHasTicket.value
  return {
    scene: onHome ? 'call-intake' : 'ticket-reply',
    instruction,
    callSummary: store.ticketDraftResult?.callSummary,
    ticketDraft: onHome ? draftForm.value : null,
    aiResult: store.aiResult,
    toolEvidenceIds: evidence.value.map(item => item.id),
    riskLevel: onHome ? draftForm.value.riskLevel : (ticket.value?.riskLevel || 'low'),
    ticketStatus: ticket.value?.status,
    availableActions: [
      canSubmitDraft.value ? 'submit_ticket' : '',
      ticket.value && !store.aiResult ? 'process_ticket' : '',
      store.replyDraft && canCancel.value ? 'save_draft' : '',
      canClose.value ? 'close_ticket' : '',
    ].filter(Boolean),
    currentAnchors: [
      'call-intake-workspace',
      'ticket-draft-form',
      'enterprise-ticket-detail',
      'enterprise-reply',
      'sunpilot-fields',
      'sunpilot-evidence',
      'sunpilot-audit',
    ],
    demoAutoClose: /直接结单|自动结案|自动回单|处理当前/.test(instruction),
  }
}

function recordDraftOverwritePolicy(editedFields: string[]) {
  if (!editedFields.length) return
  store.appendPageActionLog({
    id: `draft-policy-${Date.now()}`,
    planId: 'call-intake-policy',
    instruction: pageInstruction.value,
    contextSummary: `通话发单 / 人工已编辑:${editedFields.join(',')}`,
    tool: 'verify',
    target: 'ticket-draft-form',
    inputSummary: editedFields.join(', '),
    status: 'executed',
    result: draftForm.value.riskLevel === 'low'
      ? '检测到人工改动字段；低风险演示策略允许用发单 Agent 草稿覆盖并留下审计。'
      : '检测到人工改动字段；中高风险策略填好页面后停止在人工确认节点。',
    durationMs: 0,
    riskLevel: draftForm.value.riskLevel || 'low',
    stopReason: '',
    createdAt: new Date().toLocaleTimeString('zh-CN', { hour12: false }),
  })
}

async function runPageAgentTask(command = pageInstruction.value) {
  const instruction = command.trim() || '处理当前页面任务'
  pageInstruction.value = instruction
  pageAgentShouldStop.value = false
  operationError.value = ''
  try {
    if (!routeHasTicket.value && /发单|电话|通话/.test(instruction) && !store.ticketDraftResult) {
      store.setPageAgentStatus('executing', '调用发单 Agent 生成草稿')
      await generateDraftFromCall()
    }
    if (!routeHasTicket.value && /发单|电话|通话/.test(instruction) && store.ticketDraftResult) {
      recordDraftOverwritePolicy(Object.keys(draftFieldTouched.value).filter(key => draftFieldTouched.value[key]))
      draftForm.value = { ...emptyTicketDraft(), ...store.ticketDraftResult.ticketDraft }
    }
    if (routeHasTicket.value && !store.aiResult && /处理|回单|结单/.test(instruction)) {
      pendingAutoReply.value = true
    }

    const context = buildPageBusinessContext(instruction)
    const plan = createPageTaskPlan(context)
    await pageAgentRunner.run(plan, context, {
      onLog: entry => store.appendPageActionLog(entry),
      onStatus: (status, goal) => store.setPageAgentStatus(status, goal),
      shouldStop: () => pageAgentShouldStop.value,
    })
  } catch {
    store.setPageAgentStatus('error', instruction)
    operationError.value = 'PageAgent 执行失败，请查看动作轨迹并人工接管。'
  }
}

function stopPageAgent() {
  pageAgentShouldStop.value = true
  pageAgentRunner.stop()
  store.setPageAgentStatus('stopped', '坐席已接管')
}

function selectTicket(id: string) {
  store.selectTicket(id)
  router.push(`/tickets/${id}`)
}

async function loadRouteTicket(id?: string) {
  confirmVisible.value = false
  if (!id) {
    store.resetState()
    return
  }

  const matched = store.tickets.find(item => item.id === id || item.no === id)
  if (!matched) {
    store.selectTicket(id)
    return
  }

  if (id !== matched.id) {
    await router.replace(`/tickets/${matched.id}`)
    return
  }

  await store.loadTicketContext(matched.id)
}

function selectMenu(id: string) {
  activeMenu.value = id
  if (['info', 'confirm', 'review', 'escalated'].includes(id)) {
    activeBucket.value = id
  } else {
    activeBucket.value = 'all'
  }
}

function handleProcess() {
  operationError.value = ''
  if (ticket.value) store.startAiProcess(ticket.value.id)
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

async function handleCreateTicket() {
  operationError.value = ''
  const stamp = Date.now().toString().slice(-6)
  try {
    const created = await store.createTicket({
      id: `desk_${stamp}`,
      no: `T${new Date().toISOString().slice(0, 10).replace(/-/g, '')}${stamp}`,
      title: '新建信用卡工单',
      customerId: `C29${stamp.slice(-3)}`,
      customerName: '待补充客户',
      phone: '138****0000',
      cardLast4: '0000',
      scene: '优惠券补发',
      category: '权益与活动',
      subcategory: '优惠券补发',
      priority: 'normal',
      channel: '坐席新建',
      assignee: '坐席 A1027',
      department: '信用卡权益组',
      riskLabel: '低风险',
      riskLevel: 'low',
      content: '坐席新建工单，请补充客户诉求后启动智能处理。',
    })
    await router.push(`/tickets/${created.id}`)
  } catch {
    operationError.value = '新建工单失败，请检查工单编号是否重复。'
  }
}

async function handleEditTicket() {
  if (!ticket.value || !editableTitle.value.trim()) return
  operationError.value = ''
  try {
    await store.updateTicket(ticket.value.id, { title: editableTitle.value.trim(), operator: 'desk-a1027' })
  } catch {
    operationError.value = '编辑工单失败，请确认当前状态是否允许修改。'
  }
}

async function handleAssignTicket() {
  if (!ticket.value || !assignTo.value.trim()) return
  operationError.value = ''
  try {
    await store.assignTicket(ticket.value.id, assignTo.value.trim(), ticket.value.department, 'desk-a1027')
  } catch {
    operationError.value = '指派失败，请确认当前状态是否允许指派。'
  }
}

async function handleSaveDraft() {
  if (!ticket.value || !store.replyDraft.trim()) return
  operationError.value = ''
  try {
    await store.saveReplyDraft(ticket.value.id, store.replyDraft, 'desk-a1027')
  } catch {
    operationError.value = '保存草稿失败，请刷新后重试。'
  }
}

async function handleCancelTicket() {
  if (!ticket.value || !cancelReason.value.trim()) return
  operationError.value = ''
  try {
    await store.cancelTicket(ticket.value.id, cancelReason.value.trim(), 'desk-a1027')
  } catch {
    operationError.value = '作废失败，请确认当前状态是否允许作废。'
  }
}

async function handleReopenTicket() {
  if (!ticket.value) return
  operationError.value = ''
  try {
    await store.reopenTicket(ticket.value.id, '坐席重新打开工单', 'desk-a1027')
  } catch {
    operationError.value = '重开失败，请确认当前状态是否允许重开。'
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

function scrollToId(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function fillReplyDraft() {
  const draft = store.aiResult?.notification?.standardReply?.body || store.aiResult?.replyDraft
  if (draft) {
    applyReplyText(draft, false)
    scrollToId('enterprise-reply')
  }
}

function applyReplyText(text: string, markTouched = true) {
  if (!text.trim()) return
  if (store.replyDraft.trim() && replyTouched.value && store.replyDraft.trim() !== text.trim()) {
    store.replyDraft = `${store.replyDraft.trim()}\n\n${text.trim()}`
  } else {
    store.replyDraft = text
  }
  replyTouched.value = markTouched
}

function applyTemplate() {
  const ids = evidence.value.map(item => item.id).join('、') || '待生成'
  const scene = family.value?.label || ticket.value?.scene || '信用卡工单'
  const templates: Record<string, string> = {
    standard: `您好，关于您反馈的${scene}问题，我行已完成核验处理。处理依据编号：${ids}。请您按回单说明查看处理结果，如仍有疑问可继续联系我行客服。`,
    benefit: `您好，您反馈的权益/优惠券问题已完成活动资格与发放状态核验。证据编号：${ids}。如符合补发条件，券将在规则时限内到账，请在信用卡 App 对应权益入口查看。`,
    dispute: `您好，您反馈的交易问题已完成初步流水核查。证据编号：${ids}。如需进入调单/争议处理，请按材料提示补充交易凭证，我行将转人工团队继续跟进。`,
  }
  applyReplyText(templates[replyTemplate.value] || templates.standard)
}

function insertEvidenceIntoReply() {
  const ids = evidence.value.map(item => item.id).filter(Boolean)
  if (!ids.length) return
  const line = `处理依据/证据编号：${ids.join('、')}`
  insertReplyLine(line)
}

function insertEvidenceText(id: string) {
  insertReplyLine(`处理依据/证据编号：${id}`)
}

async function copyReplyDraft() {
  if (!store.replyDraft.trim()) return
  try {
    await navigator.clipboard?.writeText(store.replyDraft)
    operationError.value = '回单已复制。'
  } catch {
    operationError.value = '复制失败，请手动选择回单内容。'
  }
}

function insertReplyLine(line: string) {
  store.replyDraft = store.replyDraft.trim() ? `${store.replyDraft.trim()}\n${line}` : line
  replyTouched.value = true
  scrollToId('enterprise-reply')
}

function markReplyEdited() {
  replyTouched.value = true
}

function runCopilotAction(action: CopilotSuggestion['actions'][number]['id']) {
  if (action === 'process') handleProcess()
  if (action === 'fill_reply') fillReplyDraft()
  if (action === 'locate_evidence') scrollToId('sunpilot-evidence')
  if (action === 'locate_missing') scrollToId('sunpilot-fields')
  if (action === 'open_audit') {
    auditOpen.value = true
    scrollToId('sunpilot-audit')
  }
  if (action === 'prepare_review') scrollToId('enterprise-reply')
  if (action === 'prepare_confirm') openHumanConfirm()
}

function syncAuditOpen(event: Event) {
  const target = event.target
  auditOpen.value = target instanceof HTMLDetailsElement ? target.open : auditOpen.value
}

function statusClass(tone?: string) {
  return `status ${tone || 'neutral'}`
}

function ticketSourceLabel(item?: Ticket | null) {
  if (!item) return '-'
  return item.content.includes('客服') || item.content.includes('电话') ? '人工客服发单' : '工单文本导入'
}
</script>

<template>
  <div class="enterprise-shell">
    <header class="topbar">
      <button class="brand-strip" type="button" @click="router.push('/tickets')">
        <span class="bank-seal">CC</span>
        信用卡客服工单系统
      </button>
      <div class="top-actions">
        <span>坐席：A1027 李青</span>
        <span class="mono">2026-07-20</span>
        <RouterLink to="/legacy/tickets">旧版工作台</RouterLink>
      </div>
    </header>

    <div class="layout-core" :class="{ 'copilot-expanded': copilotOpen }">
      <aside class="nav-tree">
        <div class="tree-head">业务菜单</div>
        <div v-for="group in menuGroups" :key="group.id" class="tree-group">
          <span class="tree-title">{{ group.label }}</span>
          <button
            v-for="item in group.items"
            :key="`${group.id}-${item.id}`"
            class="tree-item"
            :class="{ active: item.active || activeMenu === item.id, sub: item.sub }"
            type="button"
            @click="selectMenu(item.id)"
          >
            <span>{{ item.label }}</span>
            <strong>{{ item.count }}</strong>
          </button>
        </div>
      </aside>

      <main class="workspace">
        <nav class="tabbar" aria-label="打开的工单标签">
          <button class="tab" :class="{ active: !routeHasTicket }" type="button" @click="router.push('/tickets')">工作首页</button>
          <button
            v-for="tab in tabTickets"
            :key="tab.id"
            class="tab"
            :class="{ active: tab.id === ticket?.id }"
            type="button"
            @click="selectTicket(tab.id)"
          >
            {{ tab.no }}
          </button>
        </nav>

        <section v-if="!routeHasTicket" class="home-view">
          <div class="case-toolbar home-toolbar">
            <div>
              <h1>二线工单处理首页</h1>
              <div class="toolbar-meta">
                <span>来源：人工客服发单后续处理</span>
                <span>Agent：低耦合辅助接入</span>
                <span class="status blue">智能服务已连接</span>
                <span v-if="operationError" class="status red">{{ operationError }}</span>
              </div>
            </div>
            <button class="btn-primary" type="button" :disabled="!queueTickets.length" @click="queueTickets[0] && selectTicket(queueTickets[0].id)">
              处理下一张
            </button>
            <button class="btn-plain" type="button" @click="handleCreateTicket">新建工单</button>
          </div>

          <section id="call-intake-workspace" class="sys-panel call-intake-workspace" data-page-agent-target="call-intake-workspace">
            <div class="sys-title">通话发单工作区 <small>发单 Agent 生成草稿，PageAgent 可见填单提交</small></div>
            <div class="call-intake-grid">
              <section class="call-list-pane">
                <header>
                  <strong>通话记录</strong>
                  <span>{{ store.callRecords.length }} 条样本</span>
                </header>
                <button
                  v-for="record in store.callRecords.slice(0, 8)"
                  :key="record.id"
                  class="call-record-item"
                  :class="{ active: selectedCallId === record.id }"
                  type="button"
                  @click="selectCallRecord(record.id)"
                >
                  <span class="mono">{{ record.id }}</span>
                  <strong>{{ record.callMeta.customerName || '未知客户' }} / {{ record.scenario }}</strong>
                  <small>{{ record.callMeta.customerId }} · {{ record.riskLevel }}</small>
                </button>
              </section>

              <section id="call-transcript-panel" class="call-transcript-pane" data-page-agent-target="call-transcript-panel">
                <header>
                  <strong>通话全文</strong>
                  <span>{{ selectedCall?.callMeta.agent || '坐席 A1027' }}</span>
                </header>
                <textarea v-model="customTranscript" class="transcript-box" data-page-agent-target="call-transcript" />
                <div class="call-actions">
                  <button class="btn-primary" type="button" :disabled="!customTranscript.trim()" @click="generateDraftFromCall">生成发单草稿</button>
                  <button class="btn-plain" type="button" :disabled="pageAgentBusy" @click="runPageAgentTask('根据这通电话帮我发单')">PageAgent 可见发单</button>
                </div>
                <p class="system-note">{{ draftGenerationStatus || store.ticketDraftResult?.callSummary || '选择通话后可生成摘要、字段来源和标准工单草稿。' }}</p>
              </section>

              <section id="ticket-draft-form" class="ticket-draft-form" data-page-agent-target="ticket-draft-form">
                <header>
                  <strong>标准工单草稿</strong>
                  <span :class="statusClass(draftRequiredMissing.length ? 'amber' : 'green')">{{ draftRequiredMissing.length ? `缺 ${draftRequiredMissing.length} 项` : '可提交' }}</span>
                </header>
                <div class="draft-form-grid">
                  <label>
                    <span>标题</span>
                    <input v-model="draftForm.title" data-page-agent-target="draft-title" type="text" @input="markDraftFieldEdited('title')" />
                  </label>
                  <label>
                    <span>客户号</span>
                    <input v-model="draftForm.customerId" data-page-agent-target="draft-customerId" type="text" @input="markDraftFieldEdited('customerId')" />
                  </label>
                  <label>
                    <span>客户姓名</span>
                    <input v-model="draftForm.customerName" data-page-agent-target="draft-customerName" type="text" @input="markDraftFieldEdited('customerName')" />
                  </label>
                  <label>
                    <span>预留手机</span>
                    <input v-model="draftForm.phone" data-page-agent-target="draft-phone" type="text" @input="markDraftFieldEdited('phone')" />
                  </label>
                  <label>
                    <span>卡尾号</span>
                    <input v-model="draftForm.cardLast4" data-page-agent-target="draft-cardLast4" type="text" @input="markDraftFieldEdited('cardLast4')" />
                  </label>
                  <label>
                    <span>业务场景</span>
                    <input v-model="draftForm.scene" data-page-agent-target="draft-scene" type="text" @input="markDraftFieldEdited('scene')" />
                  </label>
                  <label>
                    <span>业务大类</span>
                    <input v-model="draftForm.category" data-page-agent-target="draft-category" type="text" @input="markDraftFieldEdited('category')" />
                  </label>
                  <label>
                    <span>业务小类</span>
                    <input v-model="draftForm.subcategory" data-page-agent-target="draft-subcategory" type="text" @input="markDraftFieldEdited('subcategory')" />
                  </label>
                  <label>
                    <span>优先级</span>
                    <select v-model="draftForm.priority" data-page-agent-target="draft-priority" @change="markDraftFieldEdited('priority')">
                      <option value="low">低</option>
                      <option value="normal">普通</option>
                      <option value="urgent">加急</option>
                      <option value="critical">紧急</option>
                    </select>
                  </label>
                  <label>
                    <span>风险标签</span>
                    <input v-model="draftForm.riskLabel" data-page-agent-target="draft-riskLabel" type="text" @input="markDraftFieldEdited('riskLabel')" />
                  </label>
                  <label>
                    <span>风险等级</span>
                    <select v-model="draftForm.riskLevel" data-page-agent-target="draft-riskLevel" @change="markDraftFieldEdited('riskLevel')">
                      <option value="low">low</option>
                      <option value="medium">medium</option>
                      <option value="high">high</option>
                    </select>
                  </label>
                  <label class="full">
                    <span>发单内容</span>
                    <textarea v-model="draftForm.content" data-page-agent-target="draft-content" class="draft-content-box" @input="markDraftFieldEdited('content')" />
                  </label>
                </div>
                <div class="field-source-strip">
                  <span v-for="field in store.ticketDraftResult?.keyFields || []" :key="field.name">
                    {{ field.label }}：{{ field.value }} / {{ field.source }}
                  </span>
                  <span v-if="!store.ticketDraftResult">字段来源将在生成草稿后展示。</span>
                </div>
                <div class="call-actions">
                  <button id="draft-submit" class="btn-primary" data-page-agent-target="draft-submit" type="button" :disabled="!canSubmitDraft" @click="handleSubmitDraft">一键提交工单</button>
                  <span v-if="draftRequiredMissing.length" class="status amber">待补充：{{ draftRequiredMissing.join('、') }}</span>
                </div>
              </section>
            </div>
          </section>

          <section class="bucket-strip" aria-label="状态筛选">
            <button
              v-for="bucket in buckets"
              :key="bucket.id"
              type="button"
              :class="{ active: activeBucket === bucket.id }"
              @click="activeBucket = bucket.id"
            >
              <span>{{ bucket.label }}</span>
              <strong>{{ bucket.count }}</strong>
              <small>{{ bucket.hint }}</small>
            </button>
          </section>

          <section class="case-query-bar" aria-label="业务查询条件">
            <label>
              <span>快速查询</span>
              <input v-model="quickQuery" type="search" placeholder="工单号 / 客户号 / 姓名 / 分类 / 处理人" />
            </label>
            <label>
              <span>状态</span>
              <select v-model="statusFilter">
                <option value="all">全部状态</option>
                <option value="open">待处理</option>
                <option value="pending_info">待客户补充</option>
                <option value="pending_human_confirm">待人工确认</option>
                <option value="pending_human_review">待回单复核</option>
                <option value="escalated">已升级</option>
                <option value="failed">处理失败</option>
                <option value="closed">已结案</option>
              </select>
            </label>
            <button class="btn-plain" type="button" @click="quickQuery = ''; statusFilter = 'all'">重置查询</button>
          </section>

          <section class="sys-panel">
            <div class="sys-title">当前优先队列 <small>按状态和业务菜单筛选</small></div>
            <table class="compact-table queue-table">
              <thead>
                <tr>
                  <th>工单编号</th>
                  <th>客户号</th>
                  <th>客户姓名</th>
                  <th>分类</th>
                  <th>优先级</th>
                  <th>状态</th>
                  <th>处理人</th>
                  <th>到期时间</th>
                  <th>最近处理记录</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in queueTickets" :key="item.id" @click="selectTicket(item.id)">
                  <td class="mono">{{ item.no }}</td>
                  <td class="mono">{{ item.customerId }}</td>
                  <td>{{ item.customerName }}</td>
                  <td><span :class="statusClass(scenarioFamily(item).tone)">{{ item.subcategory || scenarioFamily(item).label }}</span></td>
                  <td><span :class="statusClass(riskMeta(item.riskLevel, item.riskLabel).tone)">{{ item.priority }}</span></td>
                  <td><span :class="statusClass(statusMeta(item.status).tone)">{{ statusMeta(item.status).label }}</span></td>
                  <td>{{ item.assignee }}</td>
                  <td>{{ item.dueAt || '-' }}</td>
                  <td>{{ suggestedAction(item) }}</td>
                </tr>
                <tr v-if="!queueTickets.length">
                  <td colspan="9" class="empty-cell">当前筛选下没有待处理工单。</td>
                </tr>
              </tbody>
            </table>
          </section>

          <section class="case-grid home-grid">
            <section class="sys-panel">
              <div class="sys-title">真实链路测评摘要 <small>40 条标注样本</small></div>
              <div class="metric-grid">
                <div>
                  <label>状态/预期结果匹配率</label>
                  <strong>{{ formatPercent(metrics?.closedLoopSuccessRate) }}</strong>
                </div>
                <div>
                  <label>业务能力匹配率</label>
                  <strong>{{ formatPercent(metrics?.toolCorrectness) }}</strong>
                </div>
                <div>
                  <label>字段完整率</label>
                  <strong>{{ formatPercent(metrics?.fieldCompleteness) }}</strong>
                </div>
                <div>
                  <label>平均处理耗时</label>
                  <strong>{{ formatMs(metrics?.avgProcessingMs) }}</strong>
                </div>
              </div>
              <p class="system-note">这里的闭环指标表示状态/预期结果匹配，不代表真实生产客户结案率。</p>
            </section>

            <section class="sys-panel">
              <div class="sys-title">生产约束 <small>人工发单后处理边界</small></div>
              <ul class="constraint-list">
                <li>高风险、投诉、盗刷、征信异议必须人工接管。</li>
                <li>敏感资料变更必须人工确认后执行。</li>
                <li>工具失败不能包装为成功，缺字段必须追问。</li>
                <li>回单必须复核，结案必须单独点击主系统按钮。</li>
              </ul>
            </section>
          </section>
        </section>

        <section v-else-if="ticket" id="enterprise-ticket-detail" class="detail-view" data-page-agent-target="enterprise-ticket-detail">
          <div class="case-toolbar">
            <div>
              <h1>{{ ticket.title }}</h1>
              <div class="toolbar-meta">
                <span class="mono">{{ ticket.no }}</span>
                <span>客户：{{ ticket.customerName }}</span>
                <span>来源：{{ ticketSourceLabel(ticket) }}</span>
                <span v-if="risk" :class="statusClass(risk.tone)">{{ risk.label }}</span>
                <span v-if="status" :class="statusClass(status.tone)">{{ status.label }}</span>
                <span v-if="operationError" class="status red">{{ operationError }}</span>
              </div>
            </div>
            <div class="toolbar-actions">
              <button class="btn-plain" type="button" :disabled="!store.replyDraft" @click="scrollToId('enterprise-reply')">查看草稿</button>
              <button class="btn-plain" type="button" :disabled="!store.aiResult?.missingFields?.length" @click="scrollToId('sunpilot-fields')">查看补充项</button>
              <button class="btn-primary" type="button" v-if="needsHumanConfirm" @click="openHumanConfirm">进入人工确认</button>
              <button id="page-agent-close-ticket" class="btn-primary" data-page-agent-target="page-agent-close-ticket" type="button" :disabled="!canClose" @click="handleClose">复核并结案</button>
            </div>
          </div>

          <section class="business-actions">
            <label>
              <span>标题</span>
              <input v-model="editableTitle" type="text" />
              <button class="btn-plain" type="button" :disabled="!canCancel" @click="handleEditTicket">保存</button>
            </label>
            <label>
              <span>指派</span>
              <input v-model="assignTo" type="text" />
              <button class="btn-plain" type="button" :disabled="!canCancel" @click="handleAssignTicket">指派</button>
            </label>
            <button id="page-agent-save-draft" class="btn-plain" data-page-agent-target="page-agent-save-draft" type="button" :disabled="!store.replyDraft || !canCancel" @click="handleSaveDraft">保存草稿</button>
            <label>
              <span>作废原因</span>
              <input v-model="cancelReason" type="text" />
              <button class="btn-plain danger" type="button" :disabled="!canCancel || !cancelReason.trim()" @click="handleCancelTicket">作废</button>
            </label>
            <button class="btn-plain" type="button" :disabled="!canReopen" @click="handleReopenTicket">重开</button>
          </section>

          <section class="case-grid">
            <section class="sys-panel">
              <div class="sys-title">基本信息 <small>原系统字段</small></div>
              <div class="field-grid">
                <div class="field"><label>工单编号</label><strong class="mono">{{ ticket.no }}</strong></div>
                <div class="field"><label>当前状态</label><strong>{{ status?.label }}</strong></div>
                <div class="field"><label>业务场景</label><strong>{{ family?.label }}</strong></div>
                <div class="field"><label>紧急程度</label><strong>{{ ticket.riskLevel === 'high' ? '紧急' : ticket.riskLevel === 'medium' ? '普通加急' : '普通' }}</strong></div>
                <div class="field"><label>创建时间</label><strong>{{ ticket.createdAt }}</strong></div>
                <div class="field"><label>当前处理人</label><strong>坐席 A1027</strong></div>
                <div class="field"><label>下一责任人</label><strong>{{ store.aiResult ? suggestion.title : '坐席处理' }}</strong></div>
                <div class="field"><label>SLA 剩余</label><strong>{{ ticket.riskLevel === 'high' ? '1 小时 30 分' : '5 小时 20 分' }}</strong></div>
              </div>
            </section>

            <section class="sys-panel">
              <div class="sys-title">客户与卡片信息 <small>工单上下文派生</small></div>
              <div class="field-grid two">
                <div class="field"><label>客户姓名</label><strong>{{ ticket.customerName }}</strong></div>
                <div class="field"><label>客户号</label><strong class="mono">{{ ticket.customerId }}</strong></div>
                <div class="field"><label>预留手机</label><strong class="mono">{{ ticket.phone }}</strong></div>
                <div class="field"><label>卡号后四位</label><strong class="mono">{{ ticket.cardLast4 }}</strong></div>
              </div>
              <table class="compact-table">
                <thead><tr><th>卡产品</th><th>卡状态</th><th>权益状态</th><th>备注</th></tr></thead>
                <tbody>
                  <tr>
                    <td>银联白金信用卡</td>
                    <td>正常</td>
                    <td>{{ family?.id === 'benefit-reissue' ? '活动达标' : '待核验' }}</td>
                    <td>{{ family?.deskFocus }}</td>
                  </tr>
                </tbody>
              </table>
            </section>

            <section class="sys-panel full-row">
              <div class="sys-title">发单内容 <small>人工客服转办后的原始工单描述</small></div>
              <div class="case-text">{{ ticket.content }}</div>
            </section>

            <section class="sys-panel">
              <div class="sys-title">关联交易/权益/申请 <small>业务系统只展示必要上下文</small></div>
              <table class="compact-table">
                <thead><tr><th>业务域</th><th>当前结论</th><th>下一步</th></tr></thead>
                <tbody>
                  <tr>
                    <td>{{ family?.label }}</td>
                    <td>{{ store.aiResult?.toolResponse?.businessResult || family?.deskFocus || '等待核验' }}</td>
                    <td>{{ suggestion.title }}</td>
                  </tr>
                  <tr>
                    <td>状态流转</td>
                    <td>{{ status?.description }}</td>
                    <td>{{ store.aiResult ? '查看右侧 SunPilot 流转卡片' : '先生成处理建议' }}</td>
                  </tr>
                </tbody>
              </table>
            </section>

            <section class="sys-panel">
              <div class="sys-title">处理依据/信息核验 <small>业务语言摘要</small></div>
              <div class="verification-strip" v-if="verificationItems.length">
                <button
                  v-for="item in verificationItems.slice(0, 4)"
                  :key="item.id"
                  type="button"
                  :class="`verification-chip ${item.status}`"
                  @click="scrollToId('sunpilot-fields')"
                >
                  <span>{{ item.label }}</span>
                  <strong>{{ item.value }}</strong>
                  <small>{{ item.source }}</small>
                </button>
              </div>
              <div v-else class="empty-panel">启动处理后展示客户、卡片、交易、权益系统的核验结果。</div>
            </section>

            <section id="enterprise-reply" class="sys-panel full-row reply-workspace">
              <div class="sys-title">回单工作区 <small>客户回单、内部备注、复核摘要和证据附件分窗口处理</small></div>
              <div class="reply-command-row">
                <label>
                  <span>模板</span>
                  <select v-model="replyTemplate">
                    <option value="standard">标准处理结果</option>
                    <option value="benefit">权益/优惠券补发</option>
                    <option value="dispute">交易争议/调单</option>
                  </select>
                </label>
                <button class="btn-plain" type="button" @click="applyTemplate">套用模板</button>
                <button class="btn-plain" type="button" :disabled="!store.aiResult" @click="fillReplyDraft">填入 SunPilot 建议</button>
                <button class="btn-plain" type="button" :disabled="!evidence.length" @click="insertEvidenceIntoReply">插入证据编号</button>
                <button class="btn-plain" type="button" :disabled="!store.replyDraft" @click="copyReplyDraft">复制回单</button>
                <button class="btn-plain" type="button" :disabled="!store.replyDraft || !canCancel" @click="handleSaveDraft">保存草稿</button>
                <button class="btn-primary" type="button" :disabled="!canClose" @click="handleClose">提交复核并结案</button>
                <span :class="statusClass(canClose ? 'green' : 'amber')">{{ replyWorkspaceStatus }}</span>
              </div>

              <div class="reply-grid">
                <section class="reply-pane customer-pane">
                  <header><strong>客户回单</strong><span>{{ replyStatus }}</span></header>
                  <textarea
                    v-model="store.replyDraft"
                    class="reply-box"
                    data-page-agent-target="page-agent-reply-draft"
                    placeholder="客户回单将在这里生成，坐席复核后再提交。"
                    @input="markReplyEdited"
                  />
                </section>

                <section class="reply-pane">
                  <header><strong>内部处理意见</strong><span>{{ replySections.find(section => section.id === 'internal')?.status }}</span></header>
                  <textarea v-model="internalNoteDraft" class="reply-small-box" placeholder="内部备注用于复核岗和后续处理人。" />
                  <button class="btn-plain" type="button" :disabled="!internalNoteDraft" @click="applyReplyText(internalNoteDraft)">写入客户回单</button>
                </section>

                <section class="reply-pane">
                  <header><strong>复核摘要</strong><span>{{ replySections.find(section => section.id === 'review')?.status }}</span></header>
                  <textarea v-model="reviewSummaryDraft" class="reply-small-box" placeholder="复核摘要展示风险结论、证据和下一步。" />
                  <button class="btn-plain" type="button" :disabled="!reviewSummaryDraft" @click="applyReplyText(reviewSummaryDraft)">写入客户回单</button>
                </section>

                <section class="reply-pane">
                  <header><strong>客户追问</strong><span>{{ replySections.find(section => section.id === 'question')?.status }}</span></header>
                  <textarea v-model="customerQuestionDraft" class="reply-small-box" placeholder="缺失字段追问话术。" />
                  <button class="btn-plain" type="button" :disabled="!customerQuestionDraft" @click="applyReplyText(customerQuestionDraft)">生成客户追问</button>
                </section>

                <section class="reply-pane">
                  <header><strong>跟进计划</strong><span>{{ replySections.find(section => section.id === 'followUp')?.status }}</span></header>
                  <textarea v-model="followUpDraft" class="reply-small-box" placeholder="回访、时效和下一责任人。" />
                  <button class="btn-plain" type="button" :disabled="!followUpDraft" @click="applyReplyText(followUpDraft)">写入跟进说明</button>
                </section>

                <section class="reply-pane evidence-pane">
                  <header><strong>证据附件</strong><span>{{ evidence.length ? '可插入' : '暂无证据' }}</span></header>
                  <button
                    v-for="item in evidence"
                    :key="item.id"
                    class="evidence-token"
                    type="button"
                    @click="insertEvidenceText(item.id)"
                  >
                    <span class="mono">{{ item.id }}</span>
                    <small>{{ item.summary }}</small>
                  </button>
                  <div v-if="!evidence.length" class="empty-panel">启动处理后可插入工具证据编号。</div>
                </section>
              </div>
            </section>
          </section>
        </section>

        <section v-else class="detail-empty">
          <strong>未找到工单</strong>
          <button class="btn-primary" type="button" @click="router.push('/tickets')">返回工作首页</button>
        </section>
      </main>

      <button class="copilot-toggle" type="button" @click="copilotOpen = !copilotOpen">
        SunPilot {{ copilotOpen ? '隐藏' : '展开' }}
      </button>

      <aside v-if="copilotOpen" class="copilot">
        <div class="copilot-head"><strong>SunPilot PageAgent</strong><span>受控 GUI 执行层</span></div>
        <details class="copilot-section page-agent-console" open>
          <summary><span>PageAgent 控制台</span><strong>{{ pageAgentStatusLabel }}</strong></summary>
          <div class="copilot-body">
            <label class="agent-command">
              <span>自然语言任务</span>
              <textarea v-model="pageInstruction" data-page-agent-target="page-agent-command" />
            </label>
            <div class="page-agent-state">
              <span>当前目标</span>
              <strong>{{ store.pageAgentGoal || '等待任务' }}</strong>
              <small>工具白名单：observe / scroll / highlight / input / click / wait / verify / stop</small>
            </div>
            <div class="copilot-actions">
              <button class="btn-primary" type="button" :disabled="pageAgentBusy" @click="runPageAgentTask()">执行任务</button>
              <button class="btn-plain" type="button" :disabled="pageAgentBusy" @click="runPageAgentTask('根据这通电话帮我发单')">通话发单</button>
              <button id="page-agent-process" class="btn-plain" data-page-agent-target="page-agent-process" type="button" :disabled="store.isProcessing || !ticket" @click="handleProcess">生成处理建议</button>
              <button class="btn-plain" type="button" :disabled="pageAgentBusy" @click="runPageAgentTask('处理当前工单并自动回单')">自动回单</button>
              <button class="btn-plain danger" type="button" :disabled="!pageAgentBusy" @click="stopPageAgent">停止/接管</button>
            </div>
            <ol class="page-action-log">
              <li v-for="entry in pageAgentLogs" :key="entry.id" :class="entry.status">
                <span>{{ entry.createdAt }} · {{ entry.status }} · {{ entry.tool }}</span>
                <strong>{{ entry.target }}</strong>
                <p>{{ entry.result }}</p>
                <small>{{ entry.contextSummary }} / {{ entry.stopReason || 'ok' }} / {{ entry.durationMs }}ms</small>
              </li>
              <li v-if="!pageAgentLogs.length" class="empty-log">
                <span>EMPTY</span>
                <strong>执行 PageAgent 任务后展示页面动作轨迹。</strong>
              </li>
            </ol>
          </div>
        </details>

        <details class="copilot-section" open>
          <summary><span>当前建议</span><strong>{{ suggestion.title }}</strong></summary>
          <div class="copilot-body">
            <div class="suggestion">
              <strong>{{ suggestion.title }}</strong>
              <p>{{ suggestion.summary }}</p>
            </div>
            <div class="copilot-actions">
              <button
                v-for="action in suggestion.actions"
                :key="action.id"
                type="button"
                :class="{ 'btn-primary': action.id === 'process' }"
                :disabled="action.disabled"
                :title="action.reason"
                @click="runCopilotAction(action.id)"
              >
                {{ action.label }}
              </button>
            </div>
          </div>
        </details>

        <details id="sunpilot-flow" class="copilot-section" data-page-agent-target="sunpilot-flow" open>
          <summary><span>状态流转</span><strong>{{ flowSteps.filter(step => step.status === 'done').length }}/{{ flowSteps.length }}</strong></summary>
          <div class="copilot-body">
            <ol class="flow-list">
              <li
                v-for="step in flowSteps"
                :key="step.id"
                :class="`flow-step ${step.status}`"
                @click="step.id === 'execute' ? scrollToId('sunpilot-evidence') : step.id === 'reply' ? scrollToId('enterprise-reply') : scrollToId('sunpilot-fields')"
              >
                <span>{{ step.label }}</span>
                <strong>{{ step.status === 'done' ? '已完成' : step.status === 'running' ? '处理中' : step.status === 'blocked' ? '已拦截' : '等待' }}</strong>
                <small>{{ step.description }}</small>
              </li>
            </ol>
          </div>
        </details>

        <details id="sunpilot-fields" class="copilot-section">
          <summary><span>字段补全/信息核验</span><strong>{{ verificationItems.length || 0 }} 项</strong></summary>
          <div class="copilot-body">
            <table class="compact-table">
              <thead><tr><th>项目</th><th>结果</th><th>来源</th><th>证据</th></tr></thead>
              <tbody>
                <tr v-for="item in verificationItems" :key="item.id">
                  <td>{{ item.label }}</td>
                  <td><span :class="`status ${item.status === 'missing' || item.status === 'conflict' ? 'amber' : item.status === 'review' ? 'red' : 'green'}`">{{ item.value }}</span></td>
                  <td>{{ item.source }}</td>
                  <td class="mono">{{ item.evidenceId }}</td>
                </tr>
                <tr v-if="!verificationItems.length">
                  <td colspan="4" class="empty-cell">尚未生成核验结果。</td>
                </tr>
              </tbody>
            </table>
          </div>
        </details>

        <details id="sunpilot-evidence" class="copilot-section">
          <summary><span>证据链</span><strong>{{ evidence.length || 0 }} 条</strong></summary>
          <div class="copilot-body">
            <table class="compact-table">
              <thead><tr><th>证据编号</th><th>来源</th><th>摘要</th></tr></thead>
              <tbody>
                <tr v-for="item in evidence" :key="item.id" @click="insertEvidenceIntoReply">
                  <td class="mono">{{ item.id }}</td>
                  <td>{{ item.source }}</td>
                  <td>{{ item.summary }}</td>
                </tr>
                <tr v-if="!evidence.length">
                  <td colspan="3" class="empty-cell">暂无证据编号。</td>
                </tr>
              </tbody>
            </table>
          </div>
        </details>

        <details class="copilot-section">
          <summary><span>处理日志</span><strong>{{ logs.length }} 条</strong></summary>
          <div class="copilot-body">
            <ol class="log-list">
              <li v-for="log in logs" :key="log.id">
                <span>{{ log.time }} · {{ log.operator }}</span>
                <strong>{{ log.actionType }}</strong>
                <p>{{ log.content }}</p>
                <small class="mono">{{ log.transition || '状态未变更' }} / {{ log.evidenceId }} / {{ log.nextOwner }}</small>
              </li>
            </ol>
          </div>
        </details>

        <details id="sunpilot-audit" class="copilot-section" :open="auditOpen" @toggle="syncAuditOpen">
          <summary><span>系统审计/技术明细</span><strong>{{ store.traceSteps.length }} 步</strong></summary>
          <div class="copilot-body">
            <table class="compact-table audit-table">
              <tbody>
                <tr><th>链路</th><td>REST / SSE</td></tr>
                <tr><th>工具</th><td class="mono">{{ store.aiResult?.toolName || '暂无' }}</td></tr>
                <tr><th>请求摘要</th><td class="mono">{{ store.aiResult?.toolRequest ? JSON.stringify(store.aiResult.toolRequest) : '暂无' }}</td></tr>
              </tbody>
            </table>
            <ol class="timeline">
              <li v-for="(step, index) in store.traceSteps" :key="`${step.agentId}-${index}`">
                <span class="mono">{{ step.agentId }}</span>
                <strong>{{ step.summary }} / {{ step.status }} / {{ step.duration }}</strong>
              </li>
              <li v-if="!store.traceSteps.length"><span class="mono">EMPTY</span><strong>启动智能处理后记录底层执行明细。</strong></li>
            </ol>
          </div>
        </details>

        <details class="copilot-section">
          <summary><span>生产约束</span><strong>只辅助</strong></summary>
          <div class="copilot-body">
            <p class="case-text compact">SunPilot 只辅助定位、填草稿和解释原因，不直接保存、结案、转派或覆盖主系统状态。敏感资料变更、交易争议和投诉升级必须人工确认或接管。</p>
          </div>
        </details>
      </aside>
    </div>

    <ConfirmDialog
      v-if="showConfirmDialog && ticket"
      @confirm="handleHumanConfirm(true)"
      @reject="handleHumanConfirm(false)"
    />
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
.top-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 10px;
  color: var(--ink-soft);
  font-size: 12px;
}
.layout-core {
  min-height: calc(100vh - 42px);
  display: grid;
  grid-template-columns: 264px minmax(0, 1fr) 0;
  transition: grid-template-columns 180ms ease;
}
.layout-core.copilot-expanded {
  grid-template-columns: 264px minmax(0, 1fr) 356px;
}
.nav-tree {
  min-width: 0;
  border-right: 1px solid var(--line-dark);
  background: #fbfcfd;
  overflow: auto;
}
.tree-head,
.sys-title {
  min-height: 31px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 6px 10px;
  border-bottom: 1px solid var(--line);
  background: var(--section);
  color: var(--ink);
  font-size: 13px;
  font-weight: 900;
}
.tree-group {
  padding: 8px;
  border-bottom: 1px solid var(--line);
}
.tree-title {
  display: block;
  margin: 2px 6px 7px;
  color: var(--muted);
  font-size: 12px;
  font-weight: 900;
}
.tree-item {
  width: 100%;
  display: flex;
  justify-content: space-between;
  gap: 8px;
  min-height: 28px;
  margin: 2px 0;
  padding: 6px 8px;
  border: 1px solid transparent;
  background: transparent;
  text-align: left;
  font-size: 12px;
}
.tree-item.sub {
  padding-left: 18px;
  color: var(--ink-soft);
}
.tree-item.active {
  border-color: rgba(205, 44, 66, 0.32);
  border-left: 4px solid var(--brand);
  background: #fff5f6;
  color: var(--brand);
  font-weight: 900;
}
.workspace {
  min-width: 0;
  overflow: auto;
  background: var(--page);
}
.tabbar {
  height: 34px;
  display: flex;
  align-items: flex-end;
  gap: 2px;
  padding-left: 8px;
  border-bottom: 1px solid var(--line-dark);
  background: #f7f9fb;
}
.tab {
  min-width: 118px;
  min-height: 29px;
  padding: 5px 10px;
  border: 1px solid var(--line);
  border-bottom: 0;
  background: #fff;
  color: var(--ink-soft);
  font-size: 12px;
}
.tab.active {
  border-top: 3px solid var(--brand);
  color: var(--brand);
  font-weight: 900;
}
.case-toolbar {
  min-height: 42px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 7px 10px;
  border-bottom: 1px solid var(--line);
  background: #fff;
}
.case-toolbar h1 {
  margin: 0;
  font-size: 16px;
  line-height: 1.3;
}
.toolbar-meta,
.toolbar-actions,
.reply-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  color: var(--ink-soft);
  font-size: 12px;
}
.toolbar-actions {
  justify-content: flex-end;
}
.btn-primary,
.btn-plain {
  min-height: 28px;
  padding: 5px 10px;
  font-size: 12px;
  font-weight: 900;
}
.btn-primary {
  border-color: var(--brand-dark);
  background: var(--brand);
  color: #fff;
}
.btn-plain {
  background: #fff;
}
.btn-plain.danger {
  border-color: #c4263c;
  color: #b31f34;
}
.business-actions {
  display: grid;
  grid-template-columns: minmax(220px, 1.1fr) minmax(180px, 0.8fr) auto minmax(220px, 1fr) auto;
  gap: 8px;
  align-items: center;
  padding: 8px 10px;
  border-bottom: 1px solid var(--line);
  background: #fff;
}
.business-actions label {
  min-width: 0;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 6px;
  align-items: center;
  color: var(--ink-soft);
  font-size: 12px;
  font-weight: 900;
}
.business-actions input {
  min-width: 0;
  height: 28px;
  padding: 4px 7px;
  border: 1px solid var(--line-dark);
  background: #fff;
  color: var(--ink);
  font-size: 12px;
}
.call-intake-workspace {
  margin: 0 8px 8px;
}
.call-intake-grid {
  display: grid;
  grid-template-columns: minmax(180px, 220px) minmax(0, 1fr);
  grid-template-areas:
    "calls transcript"
    "calls draft";
  gap: 8px;
  padding: 8px;
}
.call-list-pane {
  grid-area: calls;
}
.call-transcript-pane {
  grid-area: transcript;
}
.ticket-draft-form {
  grid-area: draft;
}
.call-list-pane,
.call-transcript-pane,
.ticket-draft-form {
  min-width: 0;
  border: 1px solid var(--line);
  background: var(--panel-2);
}
.call-list-pane header,
.call-transcript-pane header,
.ticket-draft-form header {
  min-height: 34px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 10px;
  border-bottom: 1px solid var(--line);
  font-size: 12px;
}
.call-list-pane header span,
.call-transcript-pane header span,
.ticket-draft-form header span {
  color: var(--ink-soft);
}
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
  cursor: pointer;
}
.call-record-item.active {
  background: #eef7f4;
  box-shadow: inset 3px 0 0 var(--green);
}
.call-record-item strong {
  font-size: 12px;
  overflow-wrap: anywhere;
}
.call-record-item small {
  color: var(--ink-soft);
  font-size: 11px;
}
.transcript-box,
.draft-content-box,
.agent-command textarea {
  width: 100%;
  min-height: 150px;
  resize: vertical;
  border: 0;
  border-bottom: 1px solid var(--line);
  background: #fff;
  color: var(--ink);
  padding: 10px;
  line-height: 1.55;
  font-size: 12px;
}
.draft-content-box {
  min-height: 86px;
  border: 1px solid var(--line);
  border-radius: 6px;
}
.call-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  padding: 9px 10px;
}
.draft-form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
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
.agent-command span {
  color: var(--ink-soft);
  font-size: 11px;
  font-weight: 800;
}
.draft-form-grid input,
.draft-form-grid select {
  min-width: 0;
  height: 30px;
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 0 8px;
  background: #fff;
  color: var(--ink);
}
.field-source-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 0 10px 9px;
}
.field-source-strip span {
  padding: 4px 7px;
  border: 1px solid var(--line);
  background: #fff;
  color: var(--ink-2);
  font-size: 11px;
}
.home-view,
.detail-view {
  min-width: 0;
}
.bucket-strip {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 1px;
  margin: 8px;
  border: 1px solid var(--line);
  background: var(--line);
}
.bucket-strip button {
  display: grid;
  gap: 3px;
  min-width: 0;
  min-height: 68px;
  padding: 8px;
  border: 0;
  background: #fff;
  text-align: left;
}
.bucket-strip button.active {
  box-shadow: inset 0 3px 0 var(--brand);
  color: var(--brand);
}
.bucket-strip strong {
  font-family: var(--mono);
  font-size: 20px;
}
.bucket-strip small {
  color: var(--muted);
  font-size: 12px;
}
.case-query-bar {
  display: grid;
  grid-template-columns: minmax(260px, 1fr) minmax(180px, 220px) auto;
  gap: 8px;
  align-items: end;
  margin: 0 8px 8px;
  padding: 8px;
  border: 1px solid var(--line-dark);
  background: #fff;
}
.case-query-bar label {
  min-width: 0;
  display: grid;
  gap: 4px;
  color: var(--ink-soft);
  font-size: 12px;
  font-weight: 900;
}
.case-query-bar input,
.case-query-bar select {
  min-width: 0;
  height: 30px;
  padding: 4px 7px;
  border: 1px solid var(--line-dark);
  background: #fff;
  color: var(--ink);
  font-size: 12px;
}
.case-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(320px, 0.85fr);
  gap: 8px;
  padding: 8px;
}
.home-grid {
  grid-template-columns: minmax(0, 1fr) minmax(320px, 0.8fr);
}
.full-row {
  grid-column: 1 / -1;
}
.sys-panel {
  min-width: 0;
  border: 1px solid var(--line-dark);
  background: #fff;
}
.sys-title small {
  color: var(--ink-soft);
  font-size: 12px;
  font-weight: 500;
}
.field-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
}
.field-grid.two {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
.field {
  min-width: 0;
  min-height: 54px;
  padding: 8px 10px;
  border-right: 1px solid var(--line);
  border-bottom: 1px solid var(--line);
}
.field label,
.metric-grid label {
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
.queue-table tbody tr {
  cursor: pointer;
}
.queue-table tbody tr:hover {
  background: #fff5f6;
}
.case-text {
  min-height: 112px;
  padding: 10px;
  color: var(--ink);
  font-size: 13px;
  line-height: 1.75;
}
.case-text.compact {
  min-height: 0;
}
.reply-box {
  width: calc(100% - 16px);
  min-height: 120px;
  margin: 8px;
  padding: 10px;
  border: 1px solid var(--line-dark);
  background: #fff;
  color: var(--ink);
  font-size: 13px;
  line-height: 1.7;
  resize: vertical;
}
.reply-actions {
  justify-content: space-between;
  padding: 0 8px 8px;
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
.verification-chip span,
.verification-chip small {
  color: var(--muted);
  font-size: 12px;
  font-weight: 800;
}
.verification-chip strong {
  overflow-wrap: anywhere;
  font-size: 13px;
}
.verification-chip.enriched {
  box-shadow: inset 3px 0 0 var(--blue);
}
.verification-chip.verified {
  box-shadow: inset 3px 0 0 var(--green);
}
.verification-chip.missing,
.verification-chip.conflict,
.verification-chip.review {
  box-shadow: inset 3px 0 0 var(--amber);
}
.empty-panel {
  padding: 18px 12px;
  color: var(--muted);
  font-size: 12px;
  line-height: 1.6;
}
.reply-workspace {
  background: #fff;
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
  grid-template-columns: minmax(0, 1.2fr) minmax(250px, 0.8fr) minmax(250px, 0.8fr);
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
  color: var(--ink);
  font-size: 13px;
}
.reply-pane header span {
  color: var(--muted);
  font-size: 12px;
  font-weight: 800;
}
.customer-pane {
  grid-row: span 2;
}
.reply-pane .reply-box {
  width: 100%;
  min-height: 260px;
  margin: 0;
}
.reply-small-box {
  width: 100%;
  min-height: 96px;
  padding: 9px;
  border: 1px solid var(--line-dark);
  background: var(--panel-2);
  color: var(--ink);
  font-size: 12px;
  line-height: 1.65;
  resize: vertical;
}
.evidence-pane {
  max-height: 260px;
  overflow: auto;
}
.evidence-token {
  min-width: 0;
  display: grid;
  gap: 4px;
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
.status.red {
  border-color: rgba(180, 35, 53, 0.3);
  background: #fff0f2;
  color: var(--danger);
}
.status.amber {
  border-color: rgba(196, 123, 24, 0.34);
  background: #fff7e8;
  color: var(--warn);
}
.status.green {
  border-color: rgba(31, 138, 91, 0.28);
  background: #edf9f2;
  color: var(--ok);
}
.status.blue {
  border-color: rgba(33, 108, 158, 0.25);
  background: #eef7fd;
  color: var(--blue);
}
.status.neutral {
  background: var(--table);
  color: var(--ink-soft);
}
.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 1px;
  background: var(--line);
}
.metric-grid > div {
  min-width: 0;
  padding: 12px;
  background: #fff;
}
.metric-grid strong {
  font-family: var(--mono);
  font-size: 22px;
}
.system-note {
  padding: 10px;
  color: var(--ink-soft);
  font-size: 12px;
  line-height: 1.6;
}
.constraint-list {
  margin: 0;
  padding: 10px 26px 12px;
  color: var(--ink);
  font-size: 13px;
  line-height: 1.9;
}
.audit-bottom {
  margin: 0 8px 8px;
  border: 1px dashed var(--line-dark);
  background: #fff;
}
.audit-bottom summary {
  display: flex;
  justify-content: space-between;
  padding: 8px 10px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 900;
}
.timeline {
  margin: 0;
  padding: 0 10px 10px;
  list-style: none;
}
.timeline li {
  display: grid;
  grid-template-columns: 150px 1fr;
  gap: 8px;
  padding: 7px 0;
  border-top: 1px solid var(--line);
  color: var(--ink-soft);
  font-size: 12px;
  line-height: 1.45;
}
.copilot-toggle {
  position: fixed;
  top: 50px;
  right: 18px;
  z-index: 5;
  min-height: 34px;
  padding: 0 12px;
  border: 1px solid var(--brand);
  background: var(--brand);
  color: #fff;
  font-size: 13px;
  font-weight: 900;
}
.copilot {
  position: sticky;
  top: 0;
  z-index: 2;
  align-self: start;
  width: 356px;
  height: calc(100vh - 42px);
  overflow: auto;
  border-left: 1px solid rgba(205, 44, 66, 0.32);
  background: #fff;
  box-shadow: -12px 0 28px rgba(31, 41, 51, 0.08);
}
.copilot-head {
  min-height: 42px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 10px;
  border-bottom: 1px solid var(--line);
  background: var(--brand);
  color: #fff;
}
.copilot-head span {
  color: rgba(255, 255, 255, 0.82);
  font-size: 12px;
}
.copilot-section {
  border-bottom: 1px solid var(--line);
}
.copilot-section summary {
  min-height: 34px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 10px;
  background: var(--section);
  cursor: pointer;
  font-size: 13px;
  font-weight: 900;
}
.copilot-section summary strong {
  color: var(--ink-soft);
  font-size: 12px;
  text-align: right;
}
.copilot-body {
  padding: 10px;
}
.suggestion {
  margin-bottom: 8px;
  border: 1px solid var(--line);
  background: #fff;
}
.suggestion strong {
  display: block;
  padding: 8px 9px;
  border-left: 4px solid var(--brand);
  font-size: 13px;
}
.suggestion p {
  margin: 0;
  padding: 0 9px 8px;
  color: var(--ink-soft);
  font-size: 12px;
  line-height: 1.6;
}
.copilot-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
}
.copilot-actions button {
  padding: 6px 8px;
  font-size: 12px;
  font-weight: 800;
}
.agent-command {
  display: grid;
  gap: 5px;
}
.agent-command textarea {
  min-height: 62px;
  border: 1px solid var(--line);
  border-radius: 6px;
}
.page-agent-state {
  display: grid;
  gap: 5px;
  margin-top: 8px;
  padding: 9px;
  border: 1px solid var(--line);
  background: #fff;
}
.page-agent-state span,
.page-agent-state small {
  color: var(--ink-soft);
  font-size: 11px;
}
.page-action-log {
  display: grid;
  gap: 7px;
  max-height: 260px;
  overflow: auto;
  margin-top: 10px;
  padding: 0;
  list-style: none;
}
.page-action-log li {
  display: grid;
  gap: 4px;
  padding: 8px;
  border-left: 3px solid var(--line-dark);
  background: #fff;
}
.page-action-log li.executed,
.page-action-log li.done {
  border-left-color: var(--green);
}
.page-action-log li.error {
  border-left-color: #c4263c;
}
.page-action-log li.stopped {
  border-left-color: #c48622;
}
.page-action-log span,
.page-action-log small {
  color: var(--ink-soft);
  font-size: 11px;
}
.page-action-log strong {
  font-family: var(--mono);
  font-size: 12px;
}
.page-action-log p {
  color: var(--ink-2);
  font-size: 12px;
  line-height: 1.45;
}
.empty-log {
  opacity: 0.72;
}
.flow-list,
.log-list {
  margin: 0;
  padding: 0;
  list-style: none;
}
.flow-step {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 3px 8px;
  padding: 9px 0 9px 18px;
  border-bottom: 1px solid var(--line);
  cursor: pointer;
}
.flow-step::before {
  content: "";
  position: absolute;
  left: 2px;
  top: 13px;
  width: 9px;
  height: 9px;
  border: 2px solid var(--line-dark);
  background: #fff;
}
.flow-step.done::before {
  border-color: var(--green);
  background: var(--green);
}
.flow-step.running::before {
  border-color: var(--blue);
  background: var(--blue);
}
.flow-step.blocked::before {
  border-color: var(--red);
  background: var(--red);
}
.flow-step span,
.flow-step strong {
  font-size: 12px;
}
.flow-step small {
  grid-column: 1 / -1;
  color: var(--ink-soft);
  font-size: 12px;
  line-height: 1.45;
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
.log-list p {
  color: var(--ink-soft);
  font-size: 12px;
  line-height: 1.55;
}
.audit-table {
  margin-bottom: 10px;
}
.empty-cell,
.detail-empty {
  color: var(--muted);
  text-align: center;
}
.detail-empty {
  display: grid;
  place-content: center;
  gap: 12px;
  min-height: 420px;
}
.mono {
  font-family: var(--mono);
}
@media (max-width: 1180px) {
  .layout-core,
  .layout-core.copilot-expanded {
    grid-template-columns: 1fr;
  }
  .nav-tree,
  .copilot {
    position: static;
    width: auto;
    height: auto;
    max-height: 340px;
    border-right: 0;
    border-bottom: 1px solid var(--line-dark);
  }
  .case-grid,
  .home-grid {
    grid-template-columns: 1fr;
  }
  .call-intake-grid {
    grid-template-columns: 1fr;
    grid-template-areas:
      "calls"
      "transcript"
      "draft";
  }
  .reply-grid {
    grid-template-columns: 1fr;
  }
  .case-query-bar {
    grid-template-columns: 1fr;
  }
  .bucket-strip {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
  .field-grid,
  .field-grid.two,
  .metric-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .copilot-toggle {
    position: static;
    margin: 8px;
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
  .top-actions {
    flex-wrap: wrap;
    padding: 8px 10px;
  }
  .tabbar {
    overflow-x: auto;
  }
  .case-grid,
  .home-grid {
    padding: 6px;
  }
  .draft-form-grid {
    grid-template-columns: 1fr;
  }
  .bucket-strip,
  .verification-strip,
  .field-grid,
  .field-grid.two,
  .metric-grid {
    grid-template-columns: 1fr;
  }
  .timeline li {
    grid-template-columns: 1fr;
  }
}
</style>
