<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { bindTicketPageAgentBridge } from '../bridge'
import { createTicketPageAgent, type AgentActivity, type AgentStatus, type HistoricalEvent } from '..'
import { useTicketStore } from '../../stores/ticket'

type MessageTone = 'neutral' | 'accent' | 'success' | 'warning' | 'danger'
type MessageKind = 'task' | 'activity' | 'observation' | 'history' | 'result'

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
const modelMenuOpen = ref(false)
const modelPicker = ref<HTMLElement | null>(null)
let unbindBridge: (() => void) | null = null

const modeLabel = computed(() => route.params.id ? '工单回单' : '通话发单')
const placeholder = computed(() => route.params.id ? '例如：处理当前工单并准备回单' : '例如：根据这通电话帮我发单')
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
const quickActions = computed(() => {
  if (!route.params.id) {
    return ['根据这通电话帮我发单', '填入发单草稿并提交', '定位通话全文']
  }
  return ['处理当前工单并准备回单', '填入回单草稿', '定位证据和审计', '滚动到复核区']
})
const configSummary = computed(() => {
  if (!llmConfig.value) return '配置读取中'
  const keyLabel = llmConfig.value.apiKeyConfigured ? `Key ${llmConfig.value.apiKeyPreview || '已配置'}` : 'Key 未配置'
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
const selectedModelOption = computed(() => modelOptions.value.find(model => model.value === selectedModel.value))
const selectedModelShortLabel = computed(() => selectedModelOption.value?.shortLabel || selectedModel.value)
const isAgentRunning = computed(() => running.value || status.value === 'running')

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
    pushMessage({ kind: 'activity', title: '思考中', body: '正在观察页面并规划下一步。', tone: 'accent' })
    return
  }
  if (activity.type === 'executing') {
    pushMessage({
      kind: 'activity',
      title: `执行 ${activity.tool}`,
      body: summarizeInput(activity.input),
      tone: 'neutral',
    })
    return
  }
  if (activity.type === 'executed') {
    pushMessage({
      kind: 'activity',
      title: `${activity.tool} 已完成`,
      body: activity.output,
      tone: 'success',
      meta: [`${activity.duration}ms`],
    })
    return
  }
  if (activity.type === 'retrying') {
    pushMessage({
      kind: 'activity',
      title: 'LLM 重试',
      body: `第 ${activity.attempt}/${activity.maxAttempts} 次重试。`,
      tone: 'warning',
    })
    return
  }
  pushMessage({ kind: 'activity', title: '执行异常', body: activity.message, tone: 'danger' })
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
  settingsStatus.value = '模型保存中...'
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
    const message = error instanceof Error ? error.message : '模型保存失败'
    settingsStatus.value = `模型保存失败：${message}`
  } finally {
    savingSettings.value = false
  }
}

async function selectModel(model: ModelOption) {
  if (savingSettings.value || isAgentRunning.value) return
  modelMenuOpen.value = false
  if (model.value === selectedModel.value) return
  selectedModel.value = model.value
  await saveSelectedModel()
}

function toggleModelMenu() {
  if (savingSettings.value || isAgentRunning.value) return
  modelMenuOpen.value = !modelMenuOpen.value
}

function handleDocumentClick(event: MouseEvent) {
  const target = event.target
  if (!(target instanceof Node)) return
  if (!modelPicker.value?.contains(target)) modelMenuOpen.value = false
}

function appendLatestHistory(history: HistoricalEvent[]) {
  const latest = history.at(-1)
  if (!latest) return
  if (latest.type === 'observation') {
    pushMessage({ kind: 'observation', title: '后端 observation', body: latest.content, tone: 'accent' })
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
  running.value = true
  input.value = ''
  if (task === suggestedCommand.value) suggestedCommand.value = ''
  store.setPageAgentStatus('thinking', task)
  pushMessage({ kind: 'task', title: '坐席任务', body: task, tone: 'neutral', meta: [modeLabel.value] })

  try {
    const result = await agent.execute(task)
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
    running.value = false
  }
}

async function stopAgent() {
  await agent.stop()
  running.value = false
  status.value = agent.status
  store.setPageAgentStatus('stopped', '坐席已接管')
  pushMessage({ kind: 'result', title: '已接管', body: '当前 SunPilot 任务已停止。', tone: 'warning' })
}

function submit() {
  void runTask()
}

function handleKeydown(event: KeyboardEvent) {
  if (event.isComposing) return
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    submit()
  }
}

function runQuickAction(command: string) {
  void runTask(command)
}

function setSuggestedCommand(kind: string) {
  const commands: Record<string, string> = {
    draft: '根据刚收到的发单Agent草稿，填入发单表单并提交标准工单。',
    ai_result: '根据刚收到的后端AI处理结果，填入回单编辑器，定位证据链，并滚动到复核区。',
    paused: '根据刚收到的高风险或人工确认信息，定位风险原因和人工确认区域，然后停止等待坐席处理。',
  }
  suggestedCommand.value = commands[kind] || ''
}

onMounted(() => {
  void loadLlmConfig()
  document.addEventListener('click', handleDocumentClick)
  messages.value = [{
    id: messageId('welcome'),
    kind: 'result',
    title: 'SunPilot ready',
    body: route.params.id ? '输入任务后，我会观察当前工单页面并执行回单、证据定位或复核准备。' : '选择通话样本后，可以让我生成草稿、填表并提交标准工单。',
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
      pushMessage({ kind: 'observation', title: '业务信息流', body: content, tone: kind === 'paused' ? 'warning' : 'accent' })
      setSuggestedCommand(kind)
    },
  })
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleDocumentClick)
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
        <span>LLM</span>
        <strong>{{ configSummary }}</strong>
      </div>
      <label class="settings-field">
        <span>API Key</span>
        <input v-model="apiKeyInput" :disabled="savingSettings" type="password" placeholder="留空则继续使用后端当前 Key" autocomplete="off" />
      </label>
      <div class="settings-actions">
        <button class="mini-btn" type="button" :disabled="savingSettings" @click="loadLlmConfig">刷新</button>
        <button class="save-config-btn" type="button" :disabled="savingSettings || !selectedModel" @click="saveLlmConfig">保存配置</button>
      </div>
      <p v-if="settingsStatus" class="settings-status">{{ settingsStatus }}</p>
    </section>

    <section ref="thread" class="agent-thread" aria-label="SunPilot 对话流">
      <article v-for="message in messages" :key="message.id" class="agent-message" :class="[message.kind, message.tone]">
        <div class="message-head">
          <strong>{{ message.title }}</strong>
          <span>{{ message.kind }}</span>
        </div>
        <p>{{ message.body }}</p>
        <div v-if="message.meta?.length" class="meta-row">
          <span v-for="item in message.meta" :key="item">{{ item }}</span>
        </div>
      </article>
    </section>

    <footer class="agent-composer">
      <div v-if="suggestedCommand" class="manual-suggestion">
        <span>收到业务信息，等待坐席唤起</span>
        <button type="button" :disabled="isAgentRunning" @click="runQuickAction(suggestedCommand)">执行建议</button>
      </div>
      <div class="quick-row">
        <button v-for="command in quickActions" :key="command" class="quick-btn" type="button" :disabled="isAgentRunning" @click="runQuickAction(command)">
          {{ command }}
        </button>
      </div>
      <div class="input-shell">
        <textarea v-model="input" class="agent-input" :placeholder="placeholder" data-page-agent-target="page-agent-command" @keydown="handleKeydown" />
        <div class="composer-tools">
          <div class="composer-spacer"></div>
          <button class="key-chip" type="button" title="配置 API Key" @click="settingsOpen = !settingsOpen">
            Key
          </button>
          <div ref="modelPicker" class="model-picker">
            <button
              class="model-pill"
              type="button"
              :disabled="savingSettings || isAgentRunning"
              :aria-expanded="modelMenuOpen"
              aria-haspopup="listbox"
              title="选择模型"
              @click.stop="toggleModelMenu"
            >
              {{ selectedModelShortLabel }}
              <span>⌄</span>
            </button>
            <div v-if="modelMenuOpen" class="model-menu" role="listbox">
              <button
                v-for="model in modelOptions"
                :key="model.value"
                class="model-option"
                :class="{ active: model.value === selectedModel }"
                type="button"
                role="option"
                :aria-selected="model.value === selectedModel"
                @click.stop="selectModel(model)"
              >
                <span>
                  <strong>{{ model.label }}</strong>
                  <small v-if="model.hint">{{ model.hint }}</small>
                </span>
                <em>{{ model.shortLabel }}</em>
              </button>
            </div>
          </div>
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
.agent-thread {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
  padding: 14px 12px;
  background: #f6f8fb;
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
  display: grid;
  gap: 8px;
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
  gap: 6px;
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
.model-picker {
  position: relative;
  flex: 0 0 auto;
}
.model-pill {
  min-height: 34px;
  max-width: 106px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0 10px 0 12px;
  border: 0;
  border-radius: 999px;
  background: #e5e7eb;
  color: #1f2937;
  font-size: 12px;
  font-weight: 900;
  white-space: nowrap;
}
.model-pill span {
  color: #64748b;
  font-size: 12px;
}
.model-pill:disabled {
  color: #9ca3af;
  cursor: not-allowed;
}
.model-menu {
  position: absolute;
  right: 0;
  bottom: 40px;
  z-index: 10;
  width: min(288px, calc(100vw - 28px));
  max-height: 292px;
  overflow-y: auto;
  padding: 6px;
  border: 1px solid #d5dde7;
  border-radius: 10px;
  background: #fff;
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.14);
}
.model-option {
  width: 100%;
  min-height: 38px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 7px 8px;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: #172033;
  text-align: left;
}
.model-option:hover,
.model-option.active {
  background: #eef6fb;
}
.model-option > span {
  min-width: 0;
  display: grid;
  gap: 2px;
}
.model-option strong {
  min-width: 0;
  font-family: var(--mono);
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.model-option small {
  color: #64748b;
  font-size: 11px;
  font-weight: 800;
}
.model-option em {
  flex: 0 0 auto;
  padding: 2px 6px;
  border-radius: 999px;
  background: #f1f5f9;
  color: #475569;
  font-style: normal;
  font-size: 10px;
  font-weight: 900;
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
