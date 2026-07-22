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

const route = useRoute()
const store = useTicketStore()
const agent = createTicketPageAgent()

const input = ref('')
const messages = ref<PanelMessage[]>([])
const thread = ref<HTMLElement | null>(null)
const running = ref(false)
const status = ref<AgentStatus>(agent.status)
const lastAutoSignature = ref('')
let unbindBridge: (() => void) | null = null

const modeLabel = computed(() => route.params.id ? '工单回单' : '通话发单')
const placeholder = computed(() => route.params.id ? '例如：处理当前工单并自动回单' : '例如：根据这通电话帮我发单')
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
  return ['处理当前工单并自动回单', '填入回单草稿', '定位证据和审计', '滚动到复核区']
})

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
  if (!task || running.value) return
  running.value = true
  input.value = ''
  store.setPageAgentStatus('thinking', task)
  pushMessage({ kind: 'task', title: '坐席任务', body: task, tone: 'neutral', meta: [modeLabel.value] })

  try {
    const result = await agent.execute(task)
    pushMessage({
      kind: 'result',
      title: result.success ? '执行完成' : '执行未完成',
      body: result.data || (result.success ? 'PageAgent 已完成本轮任务。' : 'PageAgent 未能完成本轮任务。'),
      tone: result.success ? 'success' : 'warning',
    })
  } catch (error) {
    const message = error instanceof Error ? error.message : 'PageAgent 执行失败'
    store.setPageAgentStatus('error', task)
    pushMessage({ kind: 'result', title: '执行失败', body: message, tone: 'danger' })
  } finally {
    running.value = false
  }
}

function scheduleAutoRun(command: string, signature: string) {
  if (signature === lastAutoSignature.value) return
  lastAutoSignature.value = signature
  window.setTimeout(() => {
    if (agent.status === 'running' || running.value) return
    void runTask(command)
  }, 350)
}

async function stopAgent() {
  await agent.stop()
  status.value = agent.status
  store.setPageAgentStatus('stopped', '坐席已接管')
  pushMessage({ kind: 'result', title: '已接管', body: '当前 PageAgent 任务已停止。', tone: 'warning' })
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

onMounted(() => {
  messages.value = [{
    id: messageId('welcome'),
    kind: 'result',
    title: 'PageAgent ready',
    body: route.params.id ? '输入任务后，我会观察当前工单页面并执行回单、证据定位或复核准备。' : '选择通话样本后，可以让我生成草稿、填表并提交标准工单。',
    tone: 'neutral',
    meta: [modeLabel.value],
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
      if (kind === 'draft') {
        scheduleAutoRun('根据刚收到的发单Agent草稿，填入发单表单并提交标准工单。', `${kind}:${content}`)
      }
      if (kind === 'ai_result') {
        scheduleAutoRun('根据刚收到的后端AI处理结果，填入回单编辑器，定位证据链，并滚动到复核区。', `${kind}:${content}`)
      }
      if (kind === 'paused') {
        scheduleAutoRun('根据刚收到的高风险或人工确认信息，定位风险原因和人工确认区域，然后停止等待坐席处理。', `${kind}:${content}`)
      }
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
  <aside class="ticket-page-agent">
    <header class="agent-head">
      <div class="agent-brand">
        <span class="agent-mark">PA</span>
        <div>
          <strong>PageAgent</strong>
          <small>{{ modeLabel }}</small>
        </div>
      </div>
      <div class="agent-state">
        <span :class="`state-dot ${statusTone}`"></span>
        <span>{{ statusLabel }}</span>
        <button class="mini-btn" type="button" :disabled="!running" @click="stopAgent">接管</button>
      </div>
    </header>

    <section ref="thread" class="agent-thread" aria-label="PageAgent 对话流">
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
      <div class="quick-row">
        <button v-for="command in quickActions" :key="command" class="quick-btn" type="button" :disabled="running" @click="runQuickAction(command)">
          {{ command }}
        </button>
      </div>
      <label class="input-shell">
        <textarea v-model="input" class="agent-input" :placeholder="placeholder" data-page-agent-target="page-agent-command" @keydown="handleKeydown" />
        <button class="send-btn" type="button" :disabled="!input.trim() || running" @click="submit">发送</button>
      </label>
    </footer>
  </aside>
</template>

<style scoped>
.ticket-page-agent {
  display: flex;
  flex-direction: column;
  min-width: 0;
  height: 100%;
  background: #fff;
}
.agent-head {
  min-height: 48px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 8px 12px;
  border-bottom: 1px solid #e6ebf1;
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
  color: var(--ink);
  font-size: 14px;
}
.agent-brand small,
.agent-state {
  color: var(--ink-soft);
  font-size: 12px;
}
.agent-mark {
  width: 28px;
  height: 28px;
  display: grid;
  place-items: center;
  border: 1px solid #a7d8cf;
  border-radius: 8px;
  background: #ecfdf8;
  color: #0f766e;
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
.state-dot.ready { background: #0f766e; }
.state-dot.running {
  background: #f59e0b;
  box-shadow: 0 0 0 4px rgba(245, 158, 11, 0.14);
}
.state-dot.warning { background: #c8861a; }
.state-dot.danger { background: #d64545; }
.mini-btn {
  min-height: 26px;
  padding: 0 9px;
  border: 1px solid #d7dde5;
  border-radius: 7px;
  background: #fff;
  color: var(--ink);
  font-size: 12px;
  font-weight: 800;
}
.mini-btn:disabled {
  color: #a3adba;
  cursor: not-allowed;
}
.agent-thread {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
  padding: 18px 14px;
  background: #f7f9fb;
}
.agent-message {
  max-width: 100%;
  display: grid;
  gap: 7px;
  padding: 10px 11px;
  border: 1px solid #e1e7ee;
  border-radius: 8px;
  background: #fff;
  color: var(--ink);
}
.agent-message.task {
  width: fit-content;
  max-width: 88%;
  margin-left: auto;
  border-color: #a7d8cf;
  background: #eefaf7;
}
.agent-message.accent {
  border-color: #b8ddd7;
  background: #f1fbf8;
}
.agent-message.success {
  border-color: #b8dfc3;
  background: #f2fbf5;
}
.agent-message.warning {
  border-color: #ead5a8;
  background: #fff9ed;
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
  border-top: 1px solid #e4e9ef;
  background: #fff;
}
.quick-btn {
  min-height: 26px;
  padding: 0 9px;
  border: 1px solid #d8e0e8;
  border-radius: 8px;
  background: #fff;
  color: #344154;
  font-size: 12px;
  font-weight: 800;
}
.quick-btn:hover:not(:disabled) {
  border-color: #0f766e;
  background: #f0fbf8;
}
.quick-btn:disabled {
  color: #a3adba;
  background: #f7f8fa;
  cursor: not-allowed;
}
.input-shell {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  align-items: end;
  padding: 8px;
  border: 1px solid #cfd8e3;
  border-radius: 8px;
  background: #fff;
}
.agent-input {
  min-height: 58px;
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
.send-btn {
  min-width: 56px;
  min-height: 34px;
  border: 1px solid #0f766e;
  border-radius: 8px;
  background: #0f766e;
  color: #fff;
  font-size: 13px;
  font-weight: 900;
}
.send-btn:disabled {
  border-color: #d4dbe4;
  background: #eef1f5;
  color: #9aa6b4;
  cursor: not-allowed;
}
</style>
