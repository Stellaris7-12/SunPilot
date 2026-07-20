<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useTicketStore } from '../../stores/ticket'
import { bucketMatches, scenarioFamily, statusMeta, suggestedAction, workBuckets } from '../../utils/business'
import StatusBadge from '../shared/StatusBadge.vue'

const store = useTicketStore()
const router = useRouter()
const route = useRoute()
const activeBucket = ref('all')
const familyFilter = ref('all')

const legacyMode = computed(() => route.path.startsWith('/legacy'))
const listPath = computed(() => legacyMode.value ? '/legacy/tickets' : '/tickets')

const buckets = computed(() => workBuckets(store.tickets))
const families = computed(() => {
  const seen = new Map<string, string>()
  store.tickets.forEach(ticket => {
    const family = scenarioFamily(ticket)
    seen.set(family.id, family.label)
  })
  return [{ id: 'all', label: '全部场景' }, ...Array.from(seen, ([id, label]) => ({ id, label }))]
})
const filteredTickets = computed(() => store.tickets.filter(ticket => {
  const bucketOk = bucketMatches(activeBucket.value, ticket)
  const familyOk = familyFilter.value === 'all' || scenarioFamily(ticket).id === familyFilter.value
  return bucketOk && familyOk
}))
const handoffCount = computed(() => store.tickets.filter(ticket =>
  ['pending_info', 'pending_human_confirm', 'pending_human_review', 'escalated', 'failed'].includes(ticket.status)
).length)

function onSelect(id: string) {
  store.selectTicket(id)
  router.push(`${listPath.value}/${id}`)
}
</script>

<template>
  <aside class="sidebar">
    <RouterLink class="brand" :to="listPath">
      <span class="brand-mark">TA</span>
      <span>
        <strong>TicketAgent</strong>
        <small>信用卡坐席工作台</small>
      </span>
    </RouterLink>

    <div class="shift-panel">
      <div>
        <span class="shift-label">当前待接管</span>
        <strong>{{ handoffCount }}</strong>
      </div>
      <div>
        <span class="shift-label">已结案</span>
        <strong>{{ store.closedCount }}</strong>
      </div>
    </div>

    <div class="bucket-list" aria-label="工单状态筛选">
      <button
        v-for="bucket in buckets"
        :key="bucket.id"
        type="button"
        class="bucket"
        :class="{ active: activeBucket === bucket.id }"
        :title="bucket.hint"
        @click="activeBucket = bucket.id"
      >
        <span>{{ bucket.label }}</span>
        <strong>{{ bucket.count }}</strong>
      </button>
    </div>

    <label class="filter-label">
      场景族
      <select v-model="familyFilter">
        <option v-for="family in families" :key="family.id" :value="family.id">
          {{ family.label }}
        </option>
      </select>
    </label>

    <div class="ticket-list">
      <button
        v-for="ticket in filteredTickets"
        :key="ticket.id"
        type="button"
        class="ticket-item"
        :class="{ active: store.selectedTicketId === ticket.id }"
        @click="onSelect(ticket.id)"
      >
        <span class="ticket-top">
          <span class="ticket-no mono">{{ ticket.no }}</span>
          <StatusBadge :value="statusMeta(ticket.status).label" :tone="statusMeta(ticket.status).tone" />
        </span>
        <strong class="ticket-title">{{ ticket.title }}</strong>
        <span class="ticket-meta">
          <span>{{ ticket.customerName }}</span>
          <span>{{ scenarioFamily(ticket).label }}</span>
        </span>
        <span class="next-action">{{ suggestedAction(ticket) }}</span>
      </button>
      <div v-if="filteredTickets.length === 0" class="empty">当前筛选下没有待办工单</div>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: 320px;
  min-height: 100vh;
  background: rgba(255, 255, 255, 0.96);
  border-right: 1px solid var(--line);
  display: flex;
  flex-direction: column;
}
.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 18px;
  color: inherit;
  text-decoration: none;
  border-bottom: 1px solid var(--line);
}
.brand-mark {
  width: 38px;
  height: 38px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--brand);
  background: var(--brand);
  color: #fff;
  font-weight: 900;
}
.brand strong { display: block; font-size: 15px; letter-spacing: 0; }
.brand small { display: block; margin-top: 2px; color: var(--muted); font-size: 12px; }
.shift-panel {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--line);
}
.shift-panel > div {
  min-width: 0;
  padding: 10px;
  border: 1px solid var(--line);
  background: var(--panel-2);
}
.shift-label { display: block; color: var(--muted); font-size: 12px; }
.shift-panel strong { display: block; margin-top: 3px; font-size: 24px; line-height: 1; }
.bucket-list {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  padding: 14px 16px 8px;
}
.bucket {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 10px;
  border: 1px solid var(--line);
  background: var(--panel);
  color: var(--ink);
}
.bucket span { font-size: 12px; font-weight: 700; }
.bucket strong { font-size: 13px; font-family: var(--mono); }
.bucket.active { border-color: var(--brand); background: #fff5f6; color: var(--brand); }
.filter-label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 0 16px 12px;
  color: var(--muted);
  font-size: 12px;
  font-weight: 800;
}
select {
  width: 100%;
  min-height: 32px;
  border: 1px solid var(--line);
  background: var(--panel);
  color: var(--ink);
  padding: 0 10px;
}
.ticket-list { flex: 1; overflow-y: auto; padding: 0 10px 14px; }
.ticket-item {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 8px;
  padding: 12px;
  border: 1px solid transparent;
  background: transparent;
  color: var(--ink);
  text-align: left;
}
.ticket-item:hover { background: var(--panel-2); border-color: var(--line); }
.ticket-item.active { background: #fff5f6; border-color: var(--brand); box-shadow: inset 4px 0 0 var(--brand); }
.ticket-top, .ticket-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.ticket-no { color: var(--muted); font-size: 12px; }
.ticket-title {
  display: -webkit-box;
  overflow: hidden;
  color: var(--ink);
  font-size: 13px;
  line-height: 1.45;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.ticket-meta {
  color: var(--muted);
  font-size: 12px;
}
.next-action {
  color: var(--ink-2);
  font-size: 12px;
  font-weight: 800;
}
.empty {
  margin: 16px 8px;
  padding: 18px;
  border: 1px dashed var(--line-strong);
  color: var(--muted);
  text-align: center;
  font-size: 13px;
}
@media (max-width: 980px) {
  .sidebar { width: 100%; min-height: auto; max-height: 48vh; border-right: none; border-bottom: 1px solid var(--line); }
  .ticket-list { max-height: 220px; }
}
</style>
