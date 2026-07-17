<script setup lang="ts">
import { computed } from 'vue'
import type { AiProcessResult } from '../../types'
import VerifyChecks from './VerifyChecks.vue'

const props = defineProps<{ result: AiProcessResult }>()

const toolResponse = computed(() => props.result.toolResponse || {})
const hasToolAudit = computed(() => Boolean(props.result.toolName || props.result.toolEvidence))
const formattedRequest = computed(() => JSON.stringify(props.result.toolRequest || {}, null, 2))

function valueOf(key: string) {
  const value = toolResponse.value[key]
  if (value === undefined || value === null || value === '') return '无'
  if (typeof value === 'boolean') return value ? '是' : '否'
  return String(value)
}
</script>
<template>
  <div class="card">
    <h4 class="card-title">AI 处理结果</h4>
    <div v-if="result.intent" class="section">
      <div class="intent-row">
        <span class="label">分类结果</span>
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
      <h5>接单字段</h5>
      <div class="fields-table">
        <div v-for="f in result.fields" :key="f.name" class="field-row">
          <span class="f-label">{{ f.label }}</span>
          <span class="f-value">{{ f.value }}</span>
        </div>
      </div>
    </div>
    <div v-if="hasToolAudit" id="tool-audit" class="section">
      <h5>业务执行审计</h5>
      <div class="audit-grid">
        <div>
          <span class="audit-label">工具</span>
          <strong class="mono">{{ result.toolName || '未调用' }}</strong>
        </div>
        <div>
          <span class="audit-label">动作</span>
          <strong>{{ valueOf('action') }}</strong>
        </div>
        <div>
          <span class="audit-label">证据编号</span>
          <strong class="evidence-id">{{ valueOf('evidenceId') }}</strong>
        </div>
        <div>
          <span class="audit-label">是否需人工</span>
          <strong>{{ valueOf('requiresHuman') }}</strong>
        </div>
      </div>
      <p v-if="result.toolEvidence" class="evidence">{{ result.toolEvidence }}</p>
      <div class="audit-block">
        <span class="audit-label">关键入参</span>
        <pre>{{ formattedRequest }}</pre>
      </div>
      <div class="audit-block">
        <span class="audit-label">业务结果</span>
        <p>{{ valueOf('businessResult') }}</p>
      </div>
      <div class="audit-block">
        <span class="audit-label">下一步建议</span>
        <p>{{ valueOf('nextStep') }}</p>
      </div>
      <div v-if="valueOf('failureReason') !== '无'" class="audit-block failed">
        <span class="audit-label">失败原因</span>
        <p>{{ valueOf('failureReason') }}</p>
      </div>
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
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; }
.fields-table { border: 1px solid var(--line); border-radius: 6px; overflow: hidden; }
.field-row { display: flex; border-bottom: 1px solid var(--line); font-size: 13px; }
.field-row:last-child { border-bottom: none; }
.f-label { width: 100px; padding: 8px 12px; background: var(--paper); color: var(--muted); flex-shrink: 0; }
.f-value { flex: 1; padding: 8px 12px; min-width: 0; overflow-wrap: anywhere; }
.evidence { font-size: 13px; color: var(--ink); background: var(--paper); padding: 10px; border-radius: 6px; margin-bottom: 10px; }
.audit-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 10px; }
.audit-grid > div, .audit-block { border: 1px solid var(--line); border-radius: 6px; padding: 9px 10px; background: var(--paper); min-width: 0; }
.audit-label { display: block; color: var(--muted); font-size: 11px; margin-bottom: 4px; }
.audit-grid strong { display: block; font-size: 13px; overflow-wrap: anywhere; }
.evidence-id { color: var(--blue); }
.audit-block { margin-top: 8px; font-size: 13px; }
.audit-block p { line-height: 1.5; overflow-wrap: anywhere; }
.audit-block pre { white-space: pre-wrap; overflow-wrap: anywhere; font-size: 12px; line-height: 1.4; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
.failed { border-color: var(--red-soft); background: #fff7f7; }
@media (max-width: 720px) {
  .audit-grid { grid-template-columns: 1fr; }
}
</style>
