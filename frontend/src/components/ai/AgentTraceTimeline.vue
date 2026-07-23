<script setup lang="ts">
import type { TraceStep } from '../../types'

defineProps<{ steps: TraceStep[] }>()

function statusLabel(status: string) {
  const map: Record<string, string> = {
    RUNNING: '运行中',
    SUCCESS: '成功',
    FAILED: '失败',
    SKIPPED: '跳过',
  }
  return map[status] || status
}
</script>

<template>
  <details class="audit-drawer">
    <summary>
      <span>技术审计 / Agent 执行明细</span>
      <strong>{{ steps.length }} 步</strong>
    </summary>
    <div v-if="steps.length === 0" class="empty">在 SunPilot 中启动辅助后，这里会记录底层执行明细。</div>
    <ol v-else class="trace-list">
      <li v-for="(step, index) in steps" :key="`${step.agentId}-${index}`" class="trace-step">
        <span class="dot" :class="`dot--${step.status.toLowerCase()}`" />
        <div>
          <div class="trace-head">
            <strong>{{ step.agent }}</strong>
            <span>{{ statusLabel(step.status) }} / {{ step.duration }}</span>
          </div>
          <p>{{ step.summary }}</p>
        </div>
      </li>
    </ol>
  </details>
</template>

<style scoped>
.audit-drawer {
  border: 1px dashed var(--line-strong);
  border-radius: var(--radius);
  background: rgba(255, 255, 255, 0.72);
}
summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  cursor: pointer;
  color: var(--ink);
  font-size: 13px;
  font-weight: 900;
}
summary strong {
  color: var(--muted);
  font-family: var(--mono);
  font-size: 12px;
}
.empty {
  padding: 0 16px 16px;
  color: var(--muted);
  font-size: 13px;
}
.trace-list {
  list-style: none;
  padding: 0 16px 16px;
}
.trace-step {
  display: grid;
  grid-template-columns: 14px 1fr;
  gap: 12px;
  padding: 12px 0;
  border-top: 1px solid var(--line);
}
.dot {
  width: 10px;
  height: 10px;
  margin-top: 5px;
  border-radius: 999px;
  background: var(--muted);
}
.dot--running { background: var(--blue); box-shadow: 0 0 0 5px rgba(40, 111, 154, 0.12); animation: pulse 1.1s ease-in-out infinite; }
.dot--success { background: var(--green); }
.dot--failed { background: var(--red); }
.dot--skipped { background: var(--muted); }
.trace-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.trace-head strong { font-size: 13px; }
.trace-head span {
  color: var(--muted);
  font-family: var(--mono);
  font-size: 12px;
}
.trace-step p {
  margin-top: 5px;
  color: var(--muted);
  font-size: 12px;
  line-height: 1.6;
}
@keyframes pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(0.8); opacity: 0.6; }
}
@media (max-width: 720px) {
  .trace-head { align-items: flex-start; flex-direction: column; gap: 4px; }
}
</style>
