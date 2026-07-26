<script setup lang="ts">
import { computed } from 'vue'
import type { EvaluationMetrics } from '../../types'

const props = defineProps<{
  metrics: EvaluationMetrics | null
}>()

function pct(value?: number) {
  if (value === undefined || value === null || Number.isNaN(value)) return '-'
  const ratio = value > 1 ? value : value * 100
  return `${ratio.toFixed(1)}%`
}

function seconds(value?: number) {
  if (!value) return '-'
  if (value >= 60) return `${(value / 60).toFixed(1)} 分钟`
  return `${value.toFixed(0)} 秒`
}

const cards = computed(() => {
  const m = props.metrics
  return [
    { label: '意图识别准确率', value: pct(m?.intentAccuracy), hint: '工单自动分类' },
    { label: '字段完整率', value: pct(m?.fieldCompleteness), hint: '信息抽取补齐' },
    { label: '工具调用正确率', value: pct(m?.toolCorrectness), hint: '外部系统核验' },
    { label: '闭环成功率', value: pct(m?.closedLoopSuccessRate), hint: '可自动闭环' },
    { label: '平均节省工时', value: seconds(m?.avgTimeSavedSeconds), hint: '较人工处理' },
    { label: '评测样本', value: m?.totalSamples ?? m?.evaluatedSamples ?? '-', hint: '已评测通话' },
  ]
})
</script>

<template>
  <div class="metrics-dashboard">
    <div v-if="!metrics" class="empty-panel">暂无评测指标，等待评测服务返回。</div>
    <div v-else class="metrics-grid">
      <article v-for="card in cards" :key="card.label" class="metric-card">
        <span>{{ card.label }}</span>
        <strong>{{ card.value }}</strong>
        <small>{{ card.hint }}</small>
      </article>
    </div>
  </div>
</template>

<style scoped>
.metrics-dashboard {
  padding: 8px;
}
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 1px;
  background: var(--line);
  border: 1px solid var(--line);
}
.metric-card {
  min-height: 74px;
  display: grid;
  gap: 3px;
  padding: 9px;
  background: #fff;
}
.metric-card span {
  font-size: 12px;
  font-weight: 900;
}
.metric-card strong {
  font-family: var(--mono);
  font-size: 22px;
  color: var(--brand);
}
.metric-card small {
  color: var(--muted);
  font-size: 12px;
}
.empty-panel {
  padding: 16px;
  color: var(--muted);
  font-size: 13px;
  text-align: center;
}
</style>
