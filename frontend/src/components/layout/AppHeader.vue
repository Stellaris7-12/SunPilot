<script setup lang="ts">
import type { Ticket } from '../../types'
import { scenarioFamily, statusMeta } from '../../utils/business'
import StatusBadge from '../shared/StatusBadge.vue'

defineProps<{ ticket: Ticket | null }>()
</script>

<template>
  <header class="header">
    <div class="case-title">
      <span class="eyebrow">坐席案件处理台</span>
      <h1>{{ ticket?.title || '选择一个工单开始处理' }}</h1>
      <div v-if="ticket" class="case-meta">
        <span class="mono">{{ ticket.no }}</span>
        <StatusBadge :value="scenarioFamily(ticket).label" :tone="scenarioFamily(ticket).tone" />
        <StatusBadge :value="statusMeta(ticket.status).label" :tone="statusMeta(ticket.status).tone" />
      </div>
    </div>
  </header>
</template>

<style scoped>
.header {
  min-height: 92px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 18px;
  padding: 18px 24px;
  background: rgba(255, 255, 255, 0.9);
  border-bottom: 1px solid var(--line);
  backdrop-filter: blur(16px);
}
.case-title { min-width: 0; }
.eyebrow {
  display: block;
  margin-bottom: 6px;
  color: var(--muted);
  font-size: 12px;
  font-weight: 800;
}
h1 {
  max-width: 900px;
  overflow: hidden;
  color: var(--ink);
  font-size: 20px;
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.case-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
  color: var(--muted);
  font-size: 12px;
}
@media (max-width: 760px) {
  .header { align-items: flex-start; flex-direction: column; }
  h1 { white-space: normal; }
}
</style>
