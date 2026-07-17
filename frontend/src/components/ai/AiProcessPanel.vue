<script setup lang="ts">
import { computed } from 'vue'
import type { TraceStep } from '../../types'

const props = defineProps<{ traceSteps: TraceStep[]; isProcessing: boolean }>()

const MODULES = [
  { id: 'classifier_agent', label: '分类判定', icon: '🔍' },
  { id: 'intake_agent', label: '接单提取', icon: '📋' },
  { id: 'escalation_agent', label: '升级兜底', icon: '🛡️' },
  { id: 'resolution_agent', label: '业务执行', icon: '🔧' },
  { id: 'notification_agent', label: '通知回单', icon: '💬' },
]

const moduleStatus = computed(() => {
  const completed = props.traceSteps.filter(s => s.status === 'SUCCESS').map(s => s.agentId)
  const running = props.traceSteps.filter(s => s.status === 'RUNNING').map(s => s.agentId)
  return MODULES.map(m => ({
    ...m,
    done: completed.includes(m.id),
    active: running.includes(m.id),
  }))
})
</script>
<template>
  <div class="card">
    <div class="modules">
      <div
        v-for="m in moduleStatus" :key="m.id"
        class="mod" :class="{ done: m.done, active: m.active }"
      >
        <span class="mod-icon">{{ m.done ? '✅' : m.active ? '🔄' : m.icon }}</span>
        <span class="mod-label">{{ m.label }}</span>
      </div>
    </div>
  </div>
</template>
<style scoped>
.card { background: var(--panel); border-radius: var(--radius); padding: 16px 20px; box-shadow: var(--shadow); }
.modules { display: flex; gap: 8px; }
.mod { flex: 1; text-align: center; padding: 10px 6px; border-radius: var(--radius); border: 2px solid var(--line); transition: all 0.3s; }
.mod.done { border-color: var(--green); background: var(--green-soft); }
.mod.active { border-color: var(--blue); background: var(--blue-soft); box-shadow: 0 0 8px rgba(37,99,235,0.2); }
.mod-icon { display: block; font-size: 16px; margin-bottom: 4px; }
.mod-label { font-size: 11px; font-weight: 600; color: var(--muted); }
.mod.done .mod-label { color: var(--green); }
.mod.active .mod-label { color: var(--blue); }
</style>
