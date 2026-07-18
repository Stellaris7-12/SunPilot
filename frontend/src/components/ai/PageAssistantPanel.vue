<script setup lang="ts">
import { computed } from 'vue'
import type { AiProcessResult, Ticket } from '../../types'

const props = defineProps<{
  ticket: Ticket
  result: AiProcessResult | null
}>()

const emit = defineEmits<{
  fillReply: []
  checkTicket: []
  locateTools: []
  scrollReview: []
}>()

function hasMissingFields() {
  return Boolean(props.result?.missingFields?.length)
}

const hasReplyDraft = computed(() =>
  Boolean(props.result?.notification?.standardReply?.body || props.result?.replyDraft)
)
</script>

<template>
  <div class="card page-assistant">
    <div class="assistant-head">
      <h4 class="card-title">页面助手</h4>
      <span class="scope">当前工单页</span>
    </div>
    <div class="quick-state">
      <span :class="`risk r-${ticket.riskLevel}`">{{ ticket.riskLabel }}</span>
      <span v-if="hasMissingFields()" class="state warn">缺字段</span>
      <span v-else class="state">字段检查</span>
    </div>
    <div class="actions">
      <button type="button" :disabled="!hasReplyDraft" @click="emit('fillReply')">填入回单</button>
      <button type="button" :disabled="!result" @click="emit('checkTicket')">检查风险</button>
      <button type="button" @click="emit('locateTools')">定位工具</button>
      <button type="button" :disabled="!result" @click="emit('scrollReview')">审核区域</button>
    </div>
  </div>
</template>

<style scoped>
.card { background: var(--panel); border-radius: var(--radius); padding: 16px; box-shadow: var(--shadow); }
.assistant-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 12px; }
.card-title { font-size: 13px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; }
.scope { font-size: 11px; color: var(--muted); }
.quick-state { display: flex; gap: 8px; margin-bottom: 12px; }
.risk, .state { border-radius: 999px; padding: 3px 8px; font-size: 11px; font-weight: 600; background: var(--paper); color: var(--muted); }
.r-low { background: var(--green-soft); color: var(--green); }
.r-medium { background: var(--amber-soft); color: var(--amber); }
.r-high, .warn { background: var(--red-soft); color: var(--red); }
.actions { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
button { border: 1px solid var(--line); border-radius: 6px; background: var(--panel); color: var(--ink); padding: 8px 10px; font-size: 12px; cursor: pointer; min-height: 34px; }
button:hover:not(:disabled) { border-color: var(--blue); color: var(--blue); }
button:disabled { cursor: not-allowed; color: var(--muted); background: var(--paper); }
</style>
