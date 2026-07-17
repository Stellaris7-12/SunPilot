<script setup lang="ts">
import type { Ticket } from '../../types'
import StatusBadge from '../shared/StatusBadge.vue'
defineProps<{ ticket: Ticket }>()
</script>
<template>
  <div class="card">
    <div class="info-grid">
      <div class="info-item"><label>工单号</label><span class="mono">{{ ticket.no }}</span></div>
      <div class="info-item"><label>客户</label><span>{{ ticket.customerName }}</span></div>
      <div class="info-item"><label>手机号</label><span>{{ ticket.phone }}</span></div>
      <div class="info-item"><label>卡号后4位</label><span class="mono">{{ ticket.cardLast4 }}</span></div>
      <div class="info-item"><label>业务场景</label><StatusBadge :value="ticket.scene" /></div>
      <div class="info-item"><label>风险等级</label><StatusBadge :value="ticket.riskLabel" /></div>
      <div class="info-item"><label>创建时间</label><span>{{ ticket.createdAt }}</span></div>
      <div class="info-item"><label>状态</label><StatusBadge :value="ticket.status === 'closed' ? '已结单' : ticket.status === 'pending_human_review' ? '待复核' : '待处理'" /></div>
    </div>
  </div>
</template>
<style scoped>
.card { background: var(--panel); border-radius: var(--radius); padding: 20px; box-shadow: var(--shadow); }
.info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.info-item { display: flex; flex-direction: column; gap: 4px; }
.info-item label { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; }
.info-item span { font-size: 14px; font-weight: 500; }
.mono { font-family: monospace; }
</style>
