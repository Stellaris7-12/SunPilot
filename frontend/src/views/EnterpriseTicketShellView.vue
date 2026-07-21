<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ConfirmDialog from '../components/ai/ConfirmDialog.vue'
import { evalApi } from '../api'
import { useTicketStore } from '../stores/ticket'
import type { EvaluationMetrics, Ticket } from '../types'
import {
  bucketMatches,
  type CopilotSuggestion,
  copilotSuggestion,
  enterpriseMenuGroups,
  evidenceItems,
  formatMs,
  formatPercent,
  operationLogs,
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

const ticketId = computed(() => route.params.id as string | undefined)
const ticket = computed(() => store.selectedTicket)
const routeHasTicket = computed(() => Boolean(ticketId.value))

const menuGroups = computed(() => enterpriseMenuGroups(store.tickets, activeMenu.value))
const buckets = computed(() => workBuckets(store.tickets))
const family = computed(() => ticket.value ? scenarioFamily(ticket.value, store.aiResult) : null)
const status = computed(() => ticket.value ? statusMeta(ticket.value.status) : null)
const risk = computed(() => ticket.value ? riskMeta(ticket.value.riskLevel, ticket.value.riskLabel) : null)
const evidence = computed(() => evidenceItems(store.aiResult, store.toolCalls))
const logs = computed(() => operationLogs(ticket.value, store.aiResult, store.traceSteps, store.toolCalls))
const suggestion = computed<CopilotSuggestion>(() => copilotSuggestion(ticket.value, store.aiResult, store.isProcessing))
const filteredTickets = computed(() => store.tickets.filter(item => {
  const text = `${item.title} ${item.scene} ${item.content}`
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
  return familyOk && bucketOk && statusMenuOk && detailMenuOk
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
const needsHumanConfirm = computed(() => ticket.value?.status === 'pending_human_confirm')
const showConfirmDialog = computed(() => Boolean(ticket.value && (store.workflowPaused || confirmVisible.value)))
const tabTickets = computed(() => {
  const selected = ticket.value ? [ticket.value] : []
  const others = store.tickets.filter(item => item.id !== ticket.value?.id).slice(0, 2)
  return [...selected, ...others]
})

onMounted(async () => {
  await store.fetchTickets()
  await loadRouteTicket(ticketId.value)
  try {
    metrics.value = await evalApi.metrics()
  } catch {
    metrics.value = null
  }
})

watch(ticketId, async id => {
  await loadRouteTicket(id)
})

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
    store.replyDraft = draft
    scrollToId('enterprise-reply')
  }
}

function runCopilotAction(action: CopilotSuggestion['actions'][number]['id']) {
  if (action === 'process') handleProcess()
  if (action === 'fill_reply') fillReplyDraft()
  if (action === 'locate_evidence') scrollToId('enterprise-evidence')
  if (action === 'locate_missing') scrollToId('enterprise-fields')
  if (action === 'open_audit') {
    auditOpen.value = true
    scrollToId('enterprise-audit')
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
                <span class="status blue">REST/SSE 服务化</span>
              </div>
            </div>
            <button class="btn-primary" type="button" :disabled="!queueTickets.length" @click="queueTickets[0] && selectTicket(queueTickets[0].id)">
              处理下一张
            </button>
          </div>

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

          <section class="sys-panel">
            <div class="sys-title">当前优先队列 <small>按状态和业务菜单筛选</small></div>
            <table class="compact-table queue-table">
              <thead>
                <tr>
                  <th>工单编号</th>
                  <th>标题</th>
                  <th>客户</th>
                  <th>场景</th>
                  <th>风险</th>
                  <th>状态</th>
                  <th>建议动作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in queueTickets" :key="item.id" @click="selectTicket(item.id)">
                  <td class="mono">{{ item.no }}</td>
                  <td>{{ item.title }}</td>
                  <td>{{ item.customerName }}</td>
                  <td><span :class="statusClass(scenarioFamily(item).tone)">{{ scenarioFamily(item).label }}</span></td>
                  <td><span :class="statusClass(riskMeta(item.riskLevel, item.riskLabel).tone)">{{ riskMeta(item.riskLevel, item.riskLabel).label }}</span></td>
                  <td><span :class="statusClass(statusMeta(item.status).tone)">{{ statusMeta(item.status).label }}</span></td>
                  <td>{{ suggestedAction(item) }}</td>
                </tr>
                <tr v-if="!queueTickets.length">
                  <td colspan="7" class="empty-cell">当前筛选下没有待处理工单。</td>
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
                  <label>工具命中率</label>
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

        <section v-else-if="ticket" class="detail-view">
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
              <button class="btn-plain" type="button" :disabled="!store.aiResult?.missingFields?.length" @click="scrollToId('enterprise-fields')">查看补充项</button>
              <button class="btn-primary" type="button" v-if="needsHumanConfirm" @click="openHumanConfirm">进入人工确认</button>
              <button class="btn-primary" type="button" :disabled="!canClose" @click="handleClose">复核并结案</button>
            </div>
          </div>

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

            <section id="enterprise-fields" class="sys-panel">
              <div class="sys-title">字段与风险核验 <small>Agent 读取当前工单上下文</small></div>
              <table class="compact-table">
                <thead><tr><th>字段</th><th>值</th><th>状态</th></tr></thead>
                <tbody>
                  <tr v-for="field in store.aiResult?.fields || []" :key="field.name">
                    <td>{{ field.label || field.name }}</td>
                    <td>{{ field.value }}</td>
                    <td><span class="status green">已提取</span></td>
                  </tr>
                  <tr v-for="field in store.aiResult?.missingFields || []" :key="field">
                    <td>{{ field }}</td>
                    <td>-</td>
                    <td><span class="status amber">待补充</span></td>
                  </tr>
                  <tr v-if="!store.aiResult">
                    <td colspan="3" class="empty-cell">尚未启动智能处理。</td>
                  </tr>
                </tbody>
              </table>
            </section>

            <section id="enterprise-evidence" class="sys-panel">
              <div class="sys-title">证据链 <small>工具审计与业务证据</small></div>
              <table class="compact-table">
                <thead><tr><th>来源</th><th>证据编号</th><th>摘要</th></tr></thead>
                <tbody>
                  <tr v-for="item in evidence" :key="item.id">
                    <td class="mono">{{ item.source }}</td>
                    <td class="mono">{{ item.id }}</td>
                    <td>{{ item.summary }}</td>
                  </tr>
                  <tr v-if="!evidence.length">
                    <td colspan="3" class="empty-cell">暂无证据编号，非工具型或未处理工单可能为空。</td>
                  </tr>
                </tbody>
              </table>
            </section>

            <section class="sys-panel">
              <div class="sys-title">处理日志 <small>原系统日志 + Agent 摘要</small></div>
              <table class="compact-table log-table">
                <thead><tr><th>时间</th><th>操作人</th><th>动作</th><th>内容</th><th>证据</th></tr></thead>
                <tbody>
                  <tr v-for="log in logs" :key="log.id">
                    <td>{{ log.time }}</td>
                    <td>{{ log.operator }}</td>
                    <td>{{ log.actionType }}</td>
                    <td>{{ log.content }}</td>
                    <td class="mono">{{ log.evidenceId }}</td>
                  </tr>
                </tbody>
              </table>
            </section>

            <section id="enterprise-reply" class="sys-panel">
              <div class="sys-title">回单内容 <small>坐席确认后写入原系统</small></div>
              <textarea
                v-model="store.replyDraft"
                class="reply-box"
                placeholder="客户回单将在这里生成，坐席复核后再提交。"
              />
              <div class="reply-actions">
                <span>{{ replyStatus }}</span>
                <button class="btn-primary" type="button" :disabled="!canClose" @click="handleClose">复核并结案</button>
              </div>
            </section>

            <details id="enterprise-audit" class="audit-bottom full-row" :open="auditOpen" @toggle="syncAuditOpen">
              <summary>
                <span>技术审计 / Agent 执行明细</span>
                <strong>{{ store.traceSteps.length }} 步</strong>
              </summary>
              <ol class="timeline">
                <li v-for="(step, index) in store.traceSteps" :key="`${step.agentId}-${index}`">
                  <span class="mono">{{ step.agentId }}</span>
                  <strong>{{ step.summary }} / {{ step.status }} / {{ step.duration }}</strong>
                </li>
                <li v-if="!store.traceSteps.length"><span class="mono">EMPTY</span><strong>启动智能处理后记录底层执行明细。</strong></li>
              </ol>
            </details>
          </section>
        </section>

        <section v-else class="detail-empty">
          <strong>未找到工单</strong>
          <button class="btn-primary" type="button" @click="router.push('/tickets')">返回工作首页</button>
        </section>
      </main>

      <button class="copilot-toggle" type="button" @click="copilotOpen = !copilotOpen">
        Agent Copilot {{ copilotOpen ? '隐藏' : '展开' }}
      </button>

      <aside v-if="copilotOpen" class="copilot">
        <div class="copilot-head"><strong>Agent Copilot</strong><span>低耦合侧边栏</span></div>
        <section class="copilot-section">
          <h2>当前建议</h2>
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
        </section>

        <section class="copilot-section">
          <h2>证据与缺失</h2>
          <div class="copilot-body">
            <table class="compact-table">
              <tbody>
                <tr><th>工具</th><td class="mono">{{ store.aiResult?.toolName || '暂无' }}</td></tr>
                <tr><th>证据</th><td class="mono">{{ evidence.map(item => item.id).join(' / ') || '暂无' }}</td></tr>
                <tr><th>缺失字段</th><td>{{ store.aiResult?.missingFields?.join('、') || '无' }}</td></tr>
              </tbody>
            </table>
          </div>
        </section>

        <section class="copilot-section">
          <h2>生产约束</h2>
          <div class="copilot-body">
            <p class="case-text compact">Copilot 只辅助定位、填草稿和解释原因，不直接保存、结案、转派或覆盖主系统状态。敏感资料变更、交易争议和投诉升级必须人工确认或接管。</p>
          </div>
        </section>
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
.copilot-section h2 {
  margin: 0;
  padding: 8px 10px;
  background: var(--section);
  font-size: 13px;
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
  .bucket-strip,
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
