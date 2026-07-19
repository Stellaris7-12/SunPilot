<script setup lang="ts">
import type { VerifyCheck } from '../../types'

defineProps<{ checks: VerifyCheck[] }>()

function tone(status: string) {
  if (status === '通过') return 'ok'
  if (status === '已拦截') return 'stop'
  return 'warn'
}
</script>

<template>
  <section class="guard-card">
    <div class="section-head">
      <h3>风险与兜底检查</h3>
      <span>Escalation 业务摘要</span>
    </div>
    <div class="check-list">
      <div v-for="check in checks" :key="check.label" class="check-row" :class="`check-row--${tone(check.status)}`">
        <span class="check-marker" aria-hidden="true" />
        <span class="check-label">{{ check.label }}</span>
        <strong>{{ check.status }}</strong>
      </div>
    </div>
  </section>
</template>

<style scoped>
.guard-card {
  margin-top: 18px;
  padding-top: 18px;
  border-top: 1px solid var(--line);
}
.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}
h3 { font-size: 15px; }
.section-head span {
  color: var(--muted);
  font-size: 12px;
  font-weight: 800;
}
.check-list { display: grid; gap: 8px; }
.check-row {
  display: grid;
  grid-template-columns: 14px 1fr auto;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--panel-2);
}
.check-marker {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: var(--muted);
}
.check-label {
  min-width: 0;
  color: var(--ink-2);
  font-size: 13px;
  overflow-wrap: anywhere;
}
.check-row strong {
  padding: 3px 8px;
  border-radius: 999px;
  font-size: 12px;
}
.check-row--ok .check-marker, .check-row--ok strong { background: var(--green-soft); color: var(--green); }
.check-row--warn .check-marker, .check-row--warn strong { background: var(--amber-soft); color: var(--amber); }
.check-row--stop .check-marker, .check-row--stop strong { background: var(--red-soft); color: var(--red); }
</style>
