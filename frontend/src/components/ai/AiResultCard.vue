<script setup lang="ts">
import { computed } from 'vue'
import type { AiProcessResult } from '../../types'
import { evidenceIds } from '../../utils/business'
import VerifyChecks from './VerifyChecks.vue'

const props = defineProps<{ result: AiProcessResult }>()

const toolResponse = computed(() => props.result.toolResponse || {})
const hasToolAudit = computed(() => Boolean(props.result.toolName || evidenceIds(props.result).length || props.result.toolEvidence))
const formattedRequest = computed(() => JSON.stringify(props.result.toolRequest || {}, null, 2))
const ids = computed(() => evidenceIds(props.result))

function valueOf(key: string) {
  const value = toolResponse.value[key]
  if (value === undefined || value === null || value === '') return '暂无'
  if (typeof value === 'boolean') return value ? '是' : '否'
  return String(value)
}
</script>

<template>
  <section class="result-card">
    <div class="card-head">
      <span class="section-title">处理记录</span>
      <span v-if="result.intent" class="confidence">分诊置信度 {{ (result.intent.confidence * 100).toFixed(0) }}%</span>
    </div>

    <div class="summary-grid">
      <div>
        <label>业务场景</label>
        <strong>{{ result.intent?.label || '待分诊' }}</strong>
      </div>
      <div>
        <label>处理路径</label>
        <strong class="mono">{{ result.workflowName || '待生成' }}</strong>
      </div>
      <div>
        <label>风险判断</label>
        <strong>{{ result.riskDecision || '待核验' }}</strong>
      </div>
      <div>
        <label>是否需人工</label>
        <strong>{{ result.requiresHumanReview ? '需要' : '按规则复核' }}</strong>
      </div>
    </div>

    <div v-if="result.fields.length || result.missingFields.length" class="section">
      <div class="section-head">
        <h3>关键字段</h3>
        <span>{{ result.missingFields.length ? '有字段待补齐' : '字段已提取' }}</span>
      </div>
      <div class="fields-table">
        <div v-for="field in result.fields" :key="field.name" class="field-row">
          <span>{{ field.label }}</span>
          <strong>{{ field.value || '暂无' }}</strong>
        </div>
        <div v-for="name in result.missingFields" :key="name" class="field-row missing">
          <span>{{ name }}</span>
          <strong>待客户或坐席补充</strong>
        </div>
      </div>
    </div>

    <div v-if="hasToolAudit" id="tool-audit" class="section evidence-ledger">
      <div class="section-head">
        <h3>工具与证据</h3>
        <span>{{ result.toolName || '未调用工具' }}</span>
      </div>
      <div class="ledger-grid">
        <div>
          <label>业务能力</label>
          <strong class="mono">{{ result.toolName || '人工协办' }}</strong>
        </div>
        <div>
          <label>执行动作</label>
          <strong>{{ valueOf('action') }}</strong>
        </div>
        <div>
          <label>证据编号</label>
          <strong class="mono evidence-id">{{ ids.length ? ids.join(' / ') : valueOf('evidenceId') }}</strong>
        </div>
        <div>
          <label>是否转人工</label>
          <strong>{{ valueOf('requiresHuman') }}</strong>
        </div>
      </div>
      <p v-if="result.toolEvidence" class="evidence-text">{{ result.toolEvidence }}</p>
      <div class="business-result">
        <label>业务结果</label>
        <p>{{ valueOf('businessResult') }}</p>
      </div>
      <div class="business-result">
        <label>下一步建议</label>
        <p>{{ valueOf('nextStep') }}</p>
      </div>
      <div v-if="valueOf('failureReason') !== '暂无'" class="business-result failed">
        <label>失败原因</label>
        <p>{{ valueOf('failureReason') }}</p>
      </div>
      <details class="request-json">
        <summary>查看关键入参</summary>
        <pre>{{ formattedRequest }}</pre>
      </details>
    </div>

    <VerifyChecks v-if="result.verifyChecks.length" :checks="result.verifyChecks" />
  </section>
</template>

<style scoped>
.result-card {
  padding: 20px;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  box-shadow: var(--shadow-soft);
}
.card-head, .section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.confidence, .section-head span {
  color: var(--muted);
  font-size: 12px;
  font-weight: 800;
}
.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 1px;
  margin-top: 14px;
  overflow: hidden;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--line);
}
.summary-grid > div {
  min-width: 0;
  padding: 13px;
  background: var(--panel-2);
}
label {
  display: block;
  margin-bottom: 5px;
  color: var(--muted);
  font-size: 12px;
  font-weight: 800;
}
strong { overflow-wrap: anywhere; font-size: 14px; }
.section {
  margin-top: 18px;
  padding-top: 18px;
  border-top: 1px solid var(--line);
}
h3 { font-size: 15px; }
.fields-table {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin-top: 12px;
}
.field-row {
  min-width: 0;
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--panel-2);
}
.field-row span {
  display: block;
  margin-bottom: 5px;
  color: var(--muted);
  font-size: 12px;
  font-weight: 800;
}
.field-row.missing {
  border-color: rgba(196, 134, 34, 0.28);
  background: var(--amber-soft);
}
.ledger-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-top: 12px;
}
.ledger-grid > div, .business-result {
  min-width: 0;
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--panel-2);
}
.evidence-id { color: var(--green); }
.evidence-text {
  margin-top: 10px;
  padding: 12px;
  border-left: 4px solid var(--green);
  background: var(--green-soft);
  color: var(--ink-2);
  font-size: 13px;
  line-height: 1.65;
}
.business-result {
  margin-top: 10px;
}
.business-result p {
  color: var(--ink-2);
  font-size: 13px;
  line-height: 1.6;
  overflow-wrap: anywhere;
}
.business-result.failed {
  border-color: rgba(196, 78, 78, 0.26);
  background: var(--red-soft);
}
.request-json {
  margin-top: 10px;
  border: 1px dashed var(--line-strong);
  border-radius: var(--radius);
  background: var(--panel-2);
}
summary {
  padding: 10px 12px;
  cursor: pointer;
  color: var(--muted);
  font-size: 12px;
  font-weight: 800;
}
pre {
  overflow-x: auto;
  padding: 0 12px 12px;
  font-family: var(--mono);
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
}
@media (max-width: 1050px) {
  .summary-grid, .fields-table, .ledger-grid { grid-template-columns: 1fr; }
}
</style>
