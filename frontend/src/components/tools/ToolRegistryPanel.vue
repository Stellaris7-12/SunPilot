<script setup lang="ts">
import { onMounted, ref } from 'vue'
import type { ToolDefinition } from '../../types'
import { toolApi } from '../../api'
import StatusBadge from '../shared/StatusBadge.vue'

const tools = ref<ToolDefinition[]>([])
const loading = ref(false)

onMounted(async () => {
  loading.value = true
  try {
    tools.value = await toolApi.list()
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <section class="tool-panel">
    <div class="card-head">
      <span class="section-title">业务工具目录</span>
      <span>{{ loading ? '加载中' : `${tools.length} 个能力` }}</span>
    </div>
    <div v-if="tools.length" class="tool-list">
      <article v-for="tool in tools" :key="tool.name" class="tool-row">
        <div class="tool-main">
          <strong class="mono">{{ tool.name }}</strong>
          <p>{{ tool.displayName }} / {{ tool.description }}</p>
        </div>
        <div class="tool-meta">
          <StatusBadge :value="tool.riskLevel" :tone="tool.riskLevel === 'high' ? 'red' : tool.riskLevel === 'medium' ? 'amber' : 'green'" />
          <span>{{ tool.requiresConfirmation ? '需人工确认' : '可自动执行' }}</span>
        </div>
      </article>
    </div>
    <div v-else class="empty">{{ loading ? '正在读取工具目录' : '暂无可用工具' }}</div>
  </section>
</template>

<style scoped>
.tool-panel {
  padding: 18px;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  box-shadow: var(--shadow-soft);
}
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.card-head span:last-child {
  color: var(--muted);
  font-size: 12px;
  font-weight: 800;
}
.tool-list { display: grid; gap: 8px; }
.tool-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--panel-2);
}
.tool-main { min-width: 0; }
.tool-main strong {
  display: block;
  overflow-wrap: anywhere;
  font-size: 13px;
}
.tool-main p {
  margin-top: 4px;
  color: var(--muted);
  font-size: 12px;
  line-height: 1.55;
}
.tool-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}
.tool-meta span:last-child {
  color: var(--muted);
  font-size: 12px;
  font-weight: 800;
}
.empty {
  padding: 18px;
  border: 1px dashed var(--line-strong);
  border-radius: var(--radius);
  color: var(--muted);
  text-align: center;
  font-size: 13px;
}
@media (max-width: 760px) {
  .tool-row { grid-template-columns: 1fr; }
  .tool-meta { flex-wrap: wrap; }
}
</style>
