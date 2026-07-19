<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { EvaluationMetrics } from '../../types'
import { evalApi } from '../../api'
import { formatPercent, metricCards } from '../../utils/business'

const metrics = ref<EvaluationMetrics | null>(null)
const loading = ref(false)
const error = ref('')

const cards = computed(() => metricCards(metrics.value))
const agentCount = computed(() => metrics.value?.agents ? Object.keys(metrics.value.agents).length : 0)

onMounted(async () => {
  loading.value = true
  error.value = ''
  try {
    metrics.value = await evalApi.metrics()
  } catch {
    error.value = '评测指标暂不可用'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <section class="metric-panel">
    <div class="panel-head">
      <div>
        <span class="section-title">评测摘要</span>
        <h2>真实链路质量</h2>
      </div>
      <span class="source">{{ metrics?.source || (loading ? '读取中' : '未加载') }}</span>
    </div>

    <div v-if="error" class="metric-empty">{{ error }}</div>
    <div v-else class="metric-grid">
      <div v-for="card in cards" :key="card.label" class="metric-card">
        <span>{{ card.label }}</span>
        <strong>{{ card.value }}</strong>
        <p>{{ card.hint }}</p>
      </div>
    </div>

    <div class="metric-foot">
      <span>样本数：{{ metrics?.evaluatedSamples || metrics?.totalSamples || '暂无' }}</span>
      <span>Agent 维度：{{ agentCount || '暂无' }}</span>
      <span>意图准确率：{{ formatPercent(metrics?.intentAccuracy) }}</span>
    </div>
  </section>
</template>

<style scoped>
.metric-panel {
  padding: 20px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--ink);
  color: #fff;
  box-shadow: var(--shadow);
}
.panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}
.section-title { color: rgba(255, 255, 255, 0.64); }
h2 {
  margin-top: 5px;
  font-size: 20px;
}
.source {
  padding: 4px 8px;
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 999px;
  color: rgba(255, 255, 255, 0.78);
  font-family: var(--mono);
  font-size: 12px;
}
.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}
.metric-card {
  min-width: 0;
  padding: 12px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: var(--radius);
  background: rgba(255, 255, 255, 0.07);
}
.metric-card span {
  display: block;
  color: rgba(255, 255, 255, 0.68);
  font-size: 12px;
  font-weight: 800;
}
.metric-card strong {
  display: block;
  margin-top: 5px;
  font-family: var(--mono);
  font-size: 22px;
}
.metric-card p {
  margin-top: 6px;
  color: rgba(255, 255, 255, 0.68);
  font-size: 12px;
  line-height: 1.5;
}
.metric-foot {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 12px;
  color: rgba(255, 255, 255, 0.7);
  font-size: 12px;
}
.metric-empty {
  padding: 16px;
  border: 1px dashed rgba(255, 255, 255, 0.2);
  border-radius: var(--radius);
  color: rgba(255, 255, 255, 0.75);
}
@media (max-width: 980px) {
  .metric-grid { grid-template-columns: 1fr 1fr; }
}
@media (max-width: 620px) {
  .panel-head { flex-direction: column; }
  .metric-grid { grid-template-columns: 1fr; }
}
</style>
