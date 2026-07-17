<script setup lang="ts">
import type { AiProcessResult } from '../../types'
import VerifyChecks from './VerifyChecks.vue'
defineProps<{ result: AiProcessResult }>()
</script>
<template>
  <div class="card">
    <h4 class="card-title">AI 处理结果</h4>
    <div v-if="result.intent" class="section">
      <div class="intent-row">
        <span class="label">识别意图</span>
        <span class="value">{{ result.intent.label }}</span>
        <span class="conf">{{ (result.intent.confidence * 100).toFixed(0) }}%</span>
      </div>
      <div class="intent-row">
        <span class="label">处理链路</span>
        <span class="value mono">{{ result.workflowName }}</span>
      </div>
      <div class="intent-row">
        <span class="label">风险判断</span>
        <span class="value">{{ result.riskDecision }}</span>
      </div>
    </div>
    <div v-if="result.fields.length" class="section">
      <h5>抽取字段</h5>
      <div class="fields-table">
        <div v-for="f in result.fields" :key="f.name" class="field-row">
          <span class="f-label">{{ f.label }}</span>
          <span class="f-value">{{ f.value }}</span>
        </div>
      </div>
    </div>
    <div v-if="result.toolEvidence" class="section">
      <h5>工具调用</h5>
      <p class="evidence">{{ result.toolEvidence }}</p>
    </div>
    <VerifyChecks v-if="result.verifyChecks.length" :checks="result.verifyChecks" />
  </div>
</template>
<style scoped>
.card { background: var(--panel); border-radius: var(--radius); padding: 20px; box-shadow: var(--shadow); }
.card-title { font-size: 13px; color: var(--muted); margin-bottom: 14px; text-transform: uppercase; letter-spacing: 0.5px; }
.section { margin-bottom: 14px; }
.section h5 { font-size: 12px; color: var(--muted); margin-bottom: 8px; text-transform: uppercase; }
.intent-row { display: flex; gap: 8px; padding: 4px 0; font-size: 13px; }
.intent-row .label { color: var(--muted); min-width: 60px; }
.intent-row .value { font-weight: 500; }
.conf { color: var(--green); font-weight: 700; }
.mono { font-family: monospace; font-size: 12px; }
.fields-table { border: 1px solid var(--line); border-radius: 6px; overflow: hidden; }
.field-row { display: flex; border-bottom: 1px solid var(--line); font-size: 13px; }
.field-row:last-child { border-bottom: none; }
.f-label { width: 100px; padding: 8px 12px; background: var(--paper); color: var(--muted); flex-shrink: 0; }
.f-value { flex: 1; padding: 8px 12px; }
.evidence { font-size: 13px; color: var(--ink); background: var(--paper); padding: 10px; border-radius: 6px; }
</style>
