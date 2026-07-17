<script setup lang="ts">
import { ref, onMounted } from 'vue'
import type { ToolDefinition } from '../../types'
import { toolApi } from '../../api'
const tools = ref<ToolDefinition[]>([])
onMounted(async () => { tools.value = await toolApi.list() })
</script>
<template>
  <div class="card">
    <h4 class="card-title">Tool Registry</h4>
    <div v-for="t in tools" :key="t.name" class="tool-row">
      <div class="tool-name">{{ t.name }}</div>
      <div class="tool-desc">{{ t.displayName }} — {{ t.description }}</div>
      <span class="tool-risk" :class="`r-${t.riskLevel}`">{{ t.riskLevel }}</span>
      <span class="tool-confirm">{{ t.requiresConfirmation ? '需确认' : '自动' }}</span>
    </div>
    <div v-if="tools.length === 0" class="empty">加载中...</div>
  </div>
</template>
<style scoped>
.card { background: var(--panel); border-radius: var(--radius); padding: 20px; box-shadow: var(--shadow); }
.card-title { font-size: 13px; color: var(--muted); margin-bottom: 12px; text-transform: uppercase; letter-spacing: 0.5px; }
.tool-row { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; padding: 10px 0; border-bottom: 1px solid var(--line); font-size: 12px; }
.tool-row:last-child { border-bottom: none; }
.tool-name { font-weight: 700; font-family: monospace; color: var(--ink); }
.tool-desc { flex: 1; color: var(--muted); min-width: 150px; }
.tool-risk { padding: 2px 8px; border-radius: 99px; font-size: 10px; font-weight: 600; }
.r-low { background: var(--green-soft); color: var(--green); }
.r-medium { background: var(--amber-soft); color: var(--amber); }
.r-high { background: var(--red-soft); color: var(--red); }
.tool-confirm { font-size: 10px; color: var(--muted); }
.empty { color: var(--muted); font-size: 12px; text-align: center; padding: 10px 0; }
</style>
