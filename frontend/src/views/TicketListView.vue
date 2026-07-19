<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AppSidebar from '../components/layout/AppSidebar.vue'
import EvaluationSummaryPanel from '../components/metrics/EvaluationSummaryPanel.vue'
import StatusBadge from '../components/shared/StatusBadge.vue'
import { useTicketStore } from '../stores/ticket'
import { riskMeta, scenarioFamily, statusMeta, suggestedAction, workBuckets } from '../utils/business'

const store = useTicketStore()
const router = useRouter()

const buckets = computed(() => workBuckets(store.tickets).filter(bucket => bucket.id !== 'all'))
const urgentTickets = computed(() => store.tickets.filter(ticket =>
  ['pending_info', 'pending_human_confirm', 'pending_human_review', 'escalated', 'failed'].includes(ticket.status)
).slice(0, 6))

onMounted(() => store.fetchTickets())
</script>

<template>
  <div class="workbench-layout">
    <AppSidebar />
    <main class="workbench-main">
      <section class="hero-panel">
        <div>
          <span class="section-title">坐席工作池</span>
          <h1>按状态接管工单，按证据复核回单</h1>
          <p>这里不是 AI 展示页，而是坐席每天处理信用卡工单的入口。先看等待原因，再进入案件处理台。</p>
        </div>
        <button type="button" :disabled="!urgentTickets.length" @click="urgentTickets[0] && router.push(`/tickets/${urgentTickets[0].id}`)">
          处理下一张
        </button>
      </section>

      <section class="bucket-board" aria-label="工作池概览">
        <article v-for="bucket in buckets" :key="bucket.id" class="bucket-card">
          <span>{{ bucket.label }}</span>
          <strong>{{ bucket.count }}</strong>
          <p>{{ bucket.hint }}</p>
        </article>
      </section>

      <section class="queue-panel">
        <div class="panel-head">
          <div>
            <span class="section-title">需要坐席关注</span>
            <h2>当前优先队列</h2>
          </div>
          <span>{{ urgentTickets.length }} 张</span>
        </div>
        <div v-if="urgentTickets.length" class="queue-list">
          <button
            v-for="ticket in urgentTickets"
            :key="ticket.id"
            type="button"
            class="queue-row"
            @click="router.push(`/tickets/${ticket.id}`)"
          >
            <span class="mono">{{ ticket.no }}</span>
            <strong>{{ ticket.title }}</strong>
            <StatusBadge :value="scenarioFamily(ticket).label" :tone="scenarioFamily(ticket).tone" />
            <StatusBadge :value="riskMeta(ticket.riskLevel, ticket.riskLabel).label" :tone="riskMeta(ticket.riskLevel, ticket.riskLabel).tone" />
            <span class="row-action">{{ suggestedAction(ticket) }}</span>
            <StatusBadge :value="statusMeta(ticket.status).label" :tone="statusMeta(ticket.status).tone" />
          </button>
        </div>
        <div v-else class="empty">当前没有需要接管的工单</div>
      </section>

      <EvaluationSummaryPanel />
    </main>
  </div>
</template>

<style scoped>
.workbench-layout {
  min-height: 100vh;
  display: flex;
}
.workbench-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 22px;
  overflow-y: auto;
}
.hero-panel {
  min-height: 180px;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
  padding: 26px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background:
    linear-gradient(90deg, rgba(47, 143, 103, 0.16), transparent 48%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.9), rgba(255, 255, 255, 0.72));
  box-shadow: var(--shadow);
}
h1 {
  max-width: 760px;
  margin-top: 8px;
  font-size: 34px;
  line-height: 1.15;
}
.hero-panel p {
  max-width: 680px;
  margin-top: 10px;
  color: var(--muted);
  font-size: 15px;
  line-height: 1.7;
}
.hero-panel button {
  flex-shrink: 0;
  border: 1px solid var(--ink);
  border-radius: var(--radius);
  background: var(--ink);
  color: #fff;
  padding: 11px 18px;
  cursor: pointer;
  font-weight: 900;
}
.hero-panel button:disabled { opacity: 0.45; cursor: not-allowed; }
.bucket-board {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 10px;
}
.bucket-card {
  min-width: 0;
  padding: 16px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--panel);
  box-shadow: var(--shadow-soft);
}
.bucket-card span {
  color: var(--muted);
  font-size: 12px;
  font-weight: 800;
}
.bucket-card strong {
  display: block;
  margin-top: 5px;
  font-family: var(--mono);
  font-size: 28px;
}
.bucket-card p {
  margin-top: 6px;
  color: var(--muted);
  font-size: 12px;
  line-height: 1.45;
}
.queue-panel {
  padding: 20px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--panel);
  box-shadow: var(--shadow-soft);
}
.panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}
h2 { margin-top: 5px; font-size: 20px; }
.panel-head > span {
  color: var(--muted);
  font-family: var(--mono);
  font-size: 13px;
  font-weight: 900;
}
.queue-list { display: grid; gap: 8px; }
.queue-row {
  display: grid;
  grid-template-columns: 110px minmax(180px, 1fr) auto auto minmax(120px, 0.8fr) auto;
  align-items: center;
  gap: 10px;
  width: 100%;
  min-width: 0;
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--panel-2);
  color: var(--ink);
  cursor: pointer;
  text-align: left;
}
.queue-row:hover { border-color: var(--green); box-shadow: var(--shadow-soft); }
.queue-row > strong {
  min-width: 0;
  overflow: hidden;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.row-action {
  color: var(--ink-2);
  font-size: 12px;
  font-weight: 900;
}
.empty {
  padding: 20px;
  border: 1px dashed var(--line-strong);
  border-radius: var(--radius);
  color: var(--muted);
  text-align: center;
}
@media (max-width: 1180px) {
  .workbench-layout { flex-direction: column; }
  .bucket-board { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .queue-row { grid-template-columns: 1fr; }
}
@media (max-width: 720px) {
  .workbench-main { padding: 14px; }
  .hero-panel { align-items: flex-start; flex-direction: column; }
  h1 { font-size: 26px; }
  .bucket-board { grid-template-columns: 1fr 1fr; }
}
</style>
