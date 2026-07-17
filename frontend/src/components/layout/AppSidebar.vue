<script setup lang="ts">
import { useTicketStore } from '../../stores/ticket'
import { useRouter } from 'vue-router'
import StatusBadge from '../shared/StatusBadge.vue'

const store = useTicketStore()
const router = useRouter()

function onSelect(id: string) {
  store.selectTicket(id)
  router.push(`/tickets/${id}`)
}
</script>
<template>
  <aside class="sidebar">
    <div class="brand">
      <span class="brand-badge">AI</span>
      <div><strong>Credit Card Ops</strong><br><small>智能回单助手</small></div>
    </div>
    <div class="queue">
      <div class="queue-item"><span class="q-num g">{{ store.openCount }}</span>待处理</div>
      <div class="queue-item"><span class="q-num">{{ store.closedCount }}</span>已结单</div>
    </div>
    <div class="ticket-list">
      <div
        v-for="t in store.tickets" :key="t.id"
        class="ticket-item"
        :class="{ active: store.selectedTicketId === t.id }"
        @click="onSelect(t.id)"
      >
        <div class="t-item-top">
          <span class="t-no">{{ t.no }}</span>
          <StatusBadge :value="t.status === 'closed' ? '已结单' : '待处理'" />
        </div>
        <div class="t-title">{{ t.title }}</div>
        <div class="t-meta">{{ t.customerName }} · {{ t.scene }}</div>
      </div>
    </div>
  </aside>
</template>
<style scoped>
.sidebar { width: 280px; min-height: 100vh; background: var(--panel); border-right: 1px solid var(--line); display: flex; flex-direction: column; }
.brand { display: flex; align-items: center; gap: 12px; padding: 20px; border-bottom: 1px solid var(--line); }
.brand-badge { background: var(--green); color: #fff; padding: 6px 12px; border-radius: 8px; font-weight: 800; font-size: 16px; }
.queue { display: flex; gap: 0; padding: 12px 20px; border-bottom: 1px solid var(--line); }
.queue-item { flex: 1; text-align: center; font-size: 12px; color: var(--muted); }
.q-num { display: block; font-size: 22px; font-weight: 700; color: var(--ink); }
.q-num.g { color: var(--green); }
.ticket-list { flex: 1; overflow-y: auto; padding: 8px; }
.ticket-item { padding: 12px; border-radius: var(--radius); cursor: pointer; margin-bottom: 4px; border: 1px solid transparent; }
.ticket-item:hover { background: var(--paper); }
.ticket-item.active { border-color: var(--green); background: var(--green-soft); }
.t-item-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
.t-no { font-size: 12px; color: var(--muted); font-family: monospace; }
.t-title { font-size: 13px; font-weight: 600; margin-bottom: 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.t-meta { font-size: 11px; color: var(--muted); }
</style>
