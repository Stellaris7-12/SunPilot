<script setup lang="ts">
import type { Ticket } from '../../types'
import { scenarioFamily, statusMeta } from '../../utils/business'
import StatusBadge from '../shared/StatusBadge.vue'

defineProps<{ ticket: Ticket | null; processing: boolean }>()
defineEmits<{ process: []; reset: [] }>()
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
    <div class="header-actions">
      <button class="btn btn-ghost" type="button" @click="$emit('reset')">清空当前建议</button>
      <button class="btn btn-primary" type="button" :disabled="processing || !ticket" @click="$emit('process')">
        <span aria-hidden="true">▶</span>
        {{ processing ? '处理中' : '启动 AI 辅助' }}
      </button>
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
.header-actions { display: flex; gap: 10px; flex-shrink: 0; }
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-width: 126px;
  border-radius: var(--radius);
  border: 1px solid var(--line);
  padding: 9px 14px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 800;
}
.btn:disabled { opacity: 0.48; cursor: not-allowed; }
.btn-ghost { background: var(--panel); color: var(--ink); }
.btn-ghost:hover:not(:disabled) { border-color: var(--line-strong); background: var(--paper-warm); }
.btn-primary { background: var(--ink); color: #fff; border-color: var(--ink); }
.btn-primary:hover:not(:disabled) { background: var(--green); border-color: var(--green); }
@media (max-width: 760px) {
  .header { align-items: flex-start; flex-direction: column; }
  h1 { white-space: normal; }
  .header-actions { width: 100%; }
  .btn { flex: 1; min-width: 0; }
}
</style>
