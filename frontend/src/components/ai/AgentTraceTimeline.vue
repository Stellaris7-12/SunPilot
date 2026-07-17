<script setup lang="ts">
import type { TraceStep } from '../../types'
defineProps<{ steps: TraceStep[] }>()
</script>
<template>
  <div class="card">
    <h4 class="card-title">Agent Trace</h4>
    <div v-if="steps.length === 0" class="empty">点击 AI智能处理 开始</div>
    <ol class="trace-list">
      <li v-for="(s, i) in steps" :key="i" class="trace-step">
        <span class="dot" :class="`dot--${s.status.toLowerCase()}`" />
        <div>
          <strong>{{ s.agent }}</strong>
          <p>{{ s.summary }}</p>
          <span class="dur">{{ s.duration }}</span>
        </div>
      </li>
    </ol>
  </div>
</template>
<style scoped>
.card { background: var(--panel); border-radius: var(--radius); padding: 20px; box-shadow: var(--shadow); }
.card-title { font-size: 13px; color: var(--muted); margin-bottom: 12px; text-transform: uppercase; letter-spacing: 0.5px; }
.empty { color: var(--muted); font-size: 13px; text-align: center; padding: 20px 0; }
.trace-list { list-style: none; padding: 0; }
.trace-step { display: flex; gap: 12px; padding: 10px 0; border-bottom: 1px solid var(--line); align-items: flex-start; }
.trace-step:last-child { border-bottom: none; }
.dot { width: 10px; height: 10px; border-radius: 50%; margin-top: 4px; flex-shrink: 0; }
.dot--running { background: var(--amber); box-shadow: 0 0 6px var(--amber); animation: pulse 1s infinite; }
.dot--success { background: var(--green); }
.dot--failed { background: var(--red); }
.dot--skipped { background: var(--muted); }
.trace-step strong { font-size: 13px; }
.trace-step p { font-size: 12px; color: var(--muted); margin: 2px 0; }
.dur { font-size: 11px; color: var(--muted); font-family: monospace; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
</style>
