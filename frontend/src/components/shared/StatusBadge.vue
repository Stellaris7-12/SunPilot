<script setup lang="ts">
defineProps<{ value: string; size?: 'sm' | 'md' }>()
</script>
<template>
  <span class="badge" :class="[`badge--${size || 'sm'}`]" :data-status="value">
    {{ value }}
  </span>
</template>
<style scoped>
.badge { display: inline-block; padding: 2px 10px; border-radius: 99px; font-size: 12px; font-weight: 600; white-space: nowrap; }
.badge--md { padding: 4px 14px; font-size: 13px; }
.badge[data-status="低风险"], .badge[data-status="low"], .badge[data-status="通过"], .badge[data-status="已结单"], .badge[data-status="closed"] { background: var(--green-soft); color: var(--green); }
.badge[data-status="中风险"], .badge[data-status="medium"], .badge[data-status="中低风险"], .badge[data-status="待确认"], .badge[data-status="待复核"], .badge[data-status="需复核"] { background: var(--amber-soft); color: var(--amber); }
.badge[data-status="高风险"], .badge[data-status="high"], .badge[data-status="已拦截"] { background: var(--red-soft); color: var(--red); }
.badge[data-status="待处理"], .badge[data-status="open"], .badge[data-status="in_progress"] { background: var(--blue-soft); color: var(--blue); }
</style>
