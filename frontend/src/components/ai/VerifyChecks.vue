<script setup lang="ts">
import type { VerifyCheck } from '../../types'
defineProps<{ checks: VerifyCheck[] }>()
const iconMap: Record<string, string> = { '通过': '✅', '待确认': '⚠️', '需复核': '🔶', '已拦截': '🛑' }
</script>
<template>
  <div class="section">
    <h5>审核校验</h5>
    <div v-for="c in checks" :key="c.label" class="check-row">
      <span class="check-icon">{{ iconMap[c.status] || '❓' }}</span>
      <span class="check-label">{{ c.label }}</span>
      <span class="check-status" :class="`s-${c.status}`">{{ c.status }}</span>
    </div>
  </div>
</template>
<style scoped>
.section { margin-bottom: 14px; }
.section h5 { font-size: 12px; color: var(--muted); margin-bottom: 8px; text-transform: uppercase; }
.check-row { display: flex; align-items: center; gap: 8px; padding: 6px 0; font-size: 13px; }
.check-icon { font-size: 14px; }
.check-label { flex: 1; }
.check-status { font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 99px; }
.s-通过 { background: var(--green-soft); color: var(--green); }
.s-待确认 { background: var(--amber-soft); color: var(--amber); }
.s-需复核 { background: var(--amber-soft); color: var(--amber); }
.s-已拦截 { background: var(--red-soft); color: var(--red); }
</style>
