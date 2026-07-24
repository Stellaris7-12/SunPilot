<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import AgentPanel from '../page-agent/panel/AgentPanel.vue'
import { useTicketStore } from '../stores/ticket'
import type { CallRecordSample, CreateTicketPayload, WorkflowField } from '../types'

type CommonField = WorkflowField & {
  name: keyof CreateTicketPayload
  required?: boolean
}

const router = useRouter()
const store = useTicketStore()

const copilotOpen = ref(true)
const selectedCallId = ref('')
const customTranscript = ref('')
const operationError = ref('')
const draftGenerationStatus = ref('')
const draftFieldTouched = ref<Record<string, boolean>>({})
const draftForm = ref<CreateTicketPayload>(emptyTicketDraft())

const selectedCall = computed<CallRecordSample | null>(() =>
  store.callRecords.find(item => item.id === selectedCallId.value) || store.callRecords[0] || null
)
const scenarioConfig = computed(() => {
  const scene = draftForm.value.scene || selectedCall.value?.scenario || ''
  return store.workflowConfig?.scenarios?.[scene] || null
})
const scenarioFields = computed<WorkflowField[]>(() => scenarioConfig.value?.specificFields || [])
const draftRequiredMissing = computed(() =>
  commonFields.filter(field => field.required && !String(draftForm.value[field.name] || '').trim()).map(field => field.label)
)
const canSubmitDraft = computed(() => draftRequiredMissing.value.length === 0)

const commonFields: CommonField[] = [
  { name: 'customerName', label: '客户姓名', type: 'text', required: true },
  { name: 'customerId', label: '客户号', type: 'text' },
  { name: 'phone', label: '手机号', type: 'text', required: true },
  { name: 'riskLabel', label: '预警等级', type: 'text' },
  { name: 'content', label: '发单内容', type: 'textarea', required: true },
  { name: 'subcategory', label: '具体内容', type: 'text' },
  { name: 'needReply', label: '是否需要回复', type: 'select', options: ['是', '否'] },
  { name: 'deadline', label: '规定回件日期', type: 'text' },
  { name: 'title', label: '标题', type: 'text', required: true },
  { name: 'cardLast4', label: '卡尾号', type: 'text', required: true },
  { name: 'scene', label: '业务场景', type: 'text', required: true },
  { name: 'category', label: '业务类型', type: 'text' },
]

onMounted(async () => {
  operationError.value = ''
  const loadErrors: string[] = []
  const [callsResult, workflowResult] = await Promise.allSettled([
    store.fetchCallRecords(),
    store.fetchWorkflowConfig(),
  ])
  if (callsResult.status === 'rejected') loadErrors.push('通话记录')
  if (workflowResult.status === 'rejected') loadErrors.push('表单配置')
  if (!selectedCallId.value && store.callRecords[0]) selectCallRecord(store.callRecords[0].id)
  if (loadErrors.length) {
    operationError.value = `数据加载失败：${loadErrors.join('、')}。请确认后端 /api 服务可访问，或刷新页面重试。`
  }
})

watch(selectedCall, current => {
  if (!current) return
  customTranscript.value = current.transcript
  if (!store.ticketDraftResult) {
    draftForm.value = {
      ...emptyTicketDraft(),
      scene: current.scenario,
      customerId: current.callMeta.customerId || '',
      customerName: current.callMeta.customerName || '',
      phone: current.callMeta.phone || '',
      cardLast4: current.callMeta.cardLast4 || '',
      riskLevel: current.riskLevel,
      riskLabel: current.riskLevel === 'high' ? '高风险' : current.riskLevel === 'medium' ? '中风险' : '低风险',
    }
  }
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

function selectCallRecord(id: string) {
  selectedCallId.value = id
  store.ticketDraftResult = null
  const record = store.callRecords.find(item => item.id === id)
  if (record) customTranscript.value = record.transcript
}

function markDraftFieldEdited(field: string) {
  draftFieldTouched.value[field] = true
}

function draftFieldValue(field: CommonField) {
  const value = draftForm.value[field.name]
  if (field.name === 'needReply') return value === false ? '否' : '是'
  return String(value ?? '')
}

function updateDraftField(field: CommonField, value: string) {
  if (field.name === 'needReply') {
    draftForm.value.needReply = value !== '否'
  } else {
    draftForm.value = { ...draftForm.value, [field.name]: value }
  }
  markDraftFieldEdited(String(field.name))
}

function specificFieldValue(name: string) {
  return String((draftForm.value.extJson || {})[name] ?? '')
}

function updateSpecificField(name: string, value: string) {
  draftForm.value.extJson = { ...(draftForm.value.extJson || {}), [name]: value }
  markDraftFieldEdited(name)
  if (name === 'receiveUnit') draftForm.value.receiveUnit = value
  if (name === 'bizSubType') {
    draftForm.value.bizSubType = value
    draftForm.value.subcategory = draftForm.value.subcategory || value
  }
}

async function generateDraftFromCall() {
  operationError.value = ''
  draftGenerationStatus.value = '正在调用发单 Agent...'
  try {
    const payload = selectedCall.value && selectedCall.value.transcript === customTranscript.value
      ? { sampleId: selectedCall.value.id, operatorId: 'desk-a1027' }
      : { transcript: customTranscript.value, callMeta: selectedCall.value?.callMeta, operatorId: 'desk-a1027' }
    const result = await store.generateTicketDraft(payload)
    draftForm.value = { ...emptyTicketDraft(), ...result.ticketDraft, extJson: result.ticketDraft.extJson || {} }
    draftFieldTouched.value = {}
    draftGenerationStatus.value = `已生成草稿：${result.detectedScenario} / 置信度 ${(result.confidence * 100).toFixed(0)}%`
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
    const stamp = Date.now().toString().slice(-8)
    const created = await store.createTicket({
      ...draftForm.value,
      id: `call_${stamp}`,
      no: `${draftForm.value.orderPrefix || 'T'}${new Date().toISOString().slice(0, 10).replace(/-/g, '')}${Date.now().toString().slice(-6)}`,
      dueAt: draftForm.value.dueAt || draftForm.value.deadline,
    })
    await router.push(`/tickets/${created.id}`)
  } catch {
    operationError.value = '提交发单失败，请确认工单字段和编号是否有效。'
  }
}

function statusClass(tone?: string) {
  return `status ${tone || 'neutral'}`
}
</script>

<template>
  <div class="enterprise-shell dispatch-shell">
    <header class="topbar">
      <button class="brand-strip" type="button" @click="router.push('/dispatch')">
        <span class="bank-seal">CC</span>
        信用卡客服工单系统
      </button>
      <div class="top-actions">
        <span>坐席：A1027 李青</span>
        <RouterLink to="/tickets">处理首页</RouterLink>
        <RouterLink to="/legacy/tickets">旧版工作台</RouterLink>
      </div>
    </header>

    <div class="layout-core" :class="{ 'copilot-expanded': copilotOpen }">
      <main class="workspace dispatch-workspace">
        <div class="case-toolbar home-toolbar">
          <div>
            <h1>通话发单工作台</h1>
            <div class="toolbar-meta">
              <span>发单 Agent：通话记录 → 标准工单</span>
              <span v-if="scenarioConfig" class="status blue">前缀 {{ scenarioConfig.orderPrefix }}xxxx</span>
              <span v-if="operationError" class="status red">{{ operationError }}</span>
            </div>
          </div>
          <button class="btn-primary" type="button" @click="generateDraftFromCall">生成草稿</button>
        </div>

        <section id="call-intake-workspace" class="sys-panel call-intake-workspace" data-page-agent-target="call-intake-workspace">
          <div class="sys-title">通话发单 <small>按业务场景动态切换字段</small></div>
          <div class="call-intake-grid">
            <section class="call-list-pane">
              <header>
                <strong>通话记录</strong>
                <span>{{ store.callRecords.length }} 条样本</span>
              </header>
              <button
                v-for="record in store.callRecords"
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
              <p class="system-note">{{ draftGenerationStatus || store.ticketDraftResult?.callSummary || '选择通话后，可用 SunPilot 或顶部按钮生成标准工单草稿。' }}</p>
            </section>

            <section id="ticket-draft-form" class="ticket-draft-form" data-page-agent-target="ticket-draft-form">
              <header>
                <strong>标准工单草稿</strong>
                <span :class="statusClass(draftRequiredMissing.length ? 'amber' : 'green')">{{ draftRequiredMissing.length ? `缺 ${draftRequiredMissing.length} 项` : '可提交' }}</span>
              </header>
              <div class="draft-section-title">通用字段</div>
              <div class="draft-form-grid">
                <label v-for="field in commonFields" :key="field.name" :class="{ full: field.type === 'textarea' }">
                  <span>{{ field.label }}</span>
                  <select
                    v-if="field.type === 'select'"
                    :value="draftFieldValue(field)"
                    :data-page-agent-target="`dispatch-${field.name}`"
                    @change="updateDraftField(field, ($event.target as HTMLSelectElement).value)"
                  >
                    <option v-for="option in field.options" :key="option" :value="option">{{ option }}</option>
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

              <div class="draft-section-title">场景特有字段 <small>{{ draftForm.scene || selectedCall?.scenario || '待识别' }}</small></div>
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
                <div v-if="!scenarioFields.length" class="empty-panel">生成草稿或选择五类 FITS 通话样本后展示场景特有字段。</div>
              </div>

              <div class="field-source-strip">
                <span v-for="field in store.ticketDraftResult?.keyFields || []" :key="field.name">
                  {{ field.label }}：{{ field.value }} / {{ field.source }}
                </span>
                <span v-if="!store.ticketDraftResult">字段来源将在生成草稿后展示。</span>
              </div>
              <div class="call-actions">
                <button id="dispatch-submit" class="btn-primary" data-page-agent-target="dispatch-submit" type="button" :disabled="!canSubmitDraft" @click="handleSubmitDraft">一键提交工单</button>
                <span v-if="draftRequiredMissing.length" class="status amber">待补充：{{ draftRequiredMissing.join('、') }}</span>
              </div>
            </section>
          </div>
        </section>
      </main>

      <button
        class="copilot-toggle"
        type="button"
        data-page-agent-not-interactive="true"
        data-sunpilot-panel="true"
        :aria-label="copilotOpen ? '隐藏 SunPilot' : '展开 SunPilot'"
        :title="copilotOpen ? '隐藏 SunPilot' : '展开 SunPilot'"
        @click="copilotOpen = !copilotOpen"
      >
        {{ copilotOpen ? '›' : '‹' }}
      </button>

      <aside v-if="copilotOpen" class="copilot" data-page-agent-not-interactive="true" data-sunpilot-panel="true">
        <AgentPanel
          @generate-draft="generateDraftFromCall"
          @submit-draft="handleSubmitDraft"
        />
      </aside>
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
.toolbar-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  padding: 0 10px;
  color: var(--ink-soft);
  font-size: 12px;
}
.layout-core {
  min-height: calc(100vh - 42px);
  display: grid;
  grid-template-columns: minmax(0, 1fr) 0;
  grid-template-areas: "workspace copilot";
  transition: grid-template-columns 180ms ease;
}
.layout-core.copilot-expanded {
  grid-template-columns: minmax(0, 1fr) 356px;
}
.workspace {
  grid-area: workspace;
  min-width: 0;
  overflow: auto;
}
.case-toolbar {
  min-height: 50px;
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
  font-size: 12px;
  font-weight: 900;
}
.btn-primary {
  border-color: var(--brand-dark);
  background: var(--brand);
  color: #fff;
}
.sys-panel {
  min-width: 0;
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
.call-intake-workspace {
  margin: 8px;
}
.call-intake-grid {
  display: grid;
  grid-template-columns: minmax(190px, 250px) minmax(0, 1fr);
  grid-template-areas:
    "calls transcript"
    "calls draft";
  gap: 8px;
  padding: 8px;
}
.call-list-pane {
  grid-area: calls;
  max-height: calc(100vh - 118px);
  overflow: auto;
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
.call-record-item strong {
  font-size: 12px;
  overflow-wrap: anywhere;
}
.call-record-item small {
  color: var(--ink-soft);
  font-size: 11px;
}
.transcript-box,
.draft-content-box {
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
.draft-form-grid span {
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
.field-source-strip,
.call-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 0 10px 9px;
}
.call-actions {
  align-items: center;
  padding-top: 4px;
}
.field-source-strip span {
  padding: 4px 7px;
  border: 1px solid var(--line);
  background: #fff;
  color: var(--ink-2);
  font-size: 11px;
}
.system-note,
.empty-panel {
  padding: 10px;
  color: var(--ink-soft);
  font-size: 12px;
  line-height: 1.6;
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
  min-width: 0;
  border-left: 1px solid var(--line-dark);
  background: #f8fafc;
  overflow: auto;
}
@media (max-width: 1100px) {
  .layout-core,
  .layout-core.copilot-expanded {
    grid-template-columns: 1fr;
    grid-template-areas:
      "workspace"
      "copilot";
  }
  .call-intake-grid {
    grid-template-columns: 1fr;
    grid-template-areas:
      "calls"
      "transcript"
      "draft";
  }
  .draft-form-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 720px) {
  .draft-form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
