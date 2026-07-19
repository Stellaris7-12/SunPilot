<script setup lang="ts">
import { computed } from 'vue'
import type { AiProcessResult, TraceStep } from '../../types'
import { businessSteps } from '../../utils/business'

const props = defineProps<{ traceSteps: TraceStep[]; isProcessing: boolean; result?: AiProcessResult | null }>()

const steps = computed(() => businessSteps(props.traceSteps, props.result, props.isProcessing))
</script>

<template>
  <section class="process-card">
    <div class="card-head">
      <span class="section-title">业务处理链</span>
      <span class="run-state">{{ isProcessing ? '实时处理中' : result ? '已生成建议' : '待启动' }}</span>
    </div>
    <div class="step-strip">
      <div v-for="step in steps" :key="step.id" class="step" :class="`step--${step.status}`">
        <span class="step-dot" aria-hidden="true" />
        <div>
          <strong>{{ step.label }}</strong>
          <p>{{ step.description }}</p>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.process-card {
  padding: 18px;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  box-shadow: var(--shadow-soft);
}
.card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}
.run-state {
  color: var(--muted);
  font-size: 12px;
  font-weight: 800;
}
.step-strip {
  display: grid;
  grid-template-columns: repeat(5, minmax(120px, 1fr));
  gap: 8px;
}
.step {
  min-width: 0;
  min-height: 112px;
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--panel-2);
  position: relative;
}
.step::after {
  content: "";
  position: absolute;
  top: 21px;
  right: -9px;
  width: 9px;
  height: 1px;
  background: var(--line-strong);
}
.step:last-child::after { display: none; }
.step-dot {
  display: block;
  width: 12px;
  height: 12px;
  margin-bottom: 12px;
  border: 2px solid var(--line-strong);
  border-radius: 999px;
  background: var(--panel);
}
.step strong {
  display: block;
  font-size: 13px;
  line-height: 1.35;
}
.step p {
  margin-top: 6px;
  color: var(--muted);
  font-size: 12px;
  line-height: 1.55;
}
.step--done { border-color: rgba(47, 143, 103, 0.3); background: var(--green-soft); }
.step--done .step-dot { border-color: var(--green); background: var(--green); }
.step--running { border-color: rgba(40, 111, 154, 0.32); background: var(--blue-soft); }
.step--running .step-dot { border-color: var(--blue); box-shadow: 0 0 0 5px rgba(40, 111, 154, 0.14); animation: pulse 1.1s ease-in-out infinite; }
.step--blocked { border-color: rgba(196, 78, 78, 0.32); background: var(--red-soft); }
.step--blocked .step-dot { border-color: var(--red); background: var(--red); }
@keyframes pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(0.82); opacity: 0.6; }
}
@media (max-width: 1100px) {
  .step-strip { grid-template-columns: 1fr; }
  .step { min-height: auto; }
  .step::after { display: none; }
}
</style>
