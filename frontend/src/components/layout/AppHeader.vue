<script setup lang="ts">
defineProps<{ title: string; processing: boolean }>()
defineEmits<{ process: []; reset: [] }>()
</script>
<template>
  <header class="header">
    <h2 class="header-title">{{ title || '选择工单' }}</h2>
    <div class="header-actions">
      <button class="btn btn-ghost" @click="$emit('reset')">重置</button>
      <button class="btn btn-primary" :disabled="processing" @click="$emit('process')">
        {{ processing ? '处理中...' : 'AI智能处理' }}
      </button>
    </div>
  </header>
</template>
<style scoped>
.header { display: flex; justify-content: space-between; align-items: center; padding: 16px 24px; background: var(--panel); border-bottom: 1px solid var(--line); }
.header-title { font-size: 16px; font-weight: 700; }
.header-actions { display: flex; gap: 8px; }
.btn { padding: 8px 20px; border-radius: var(--radius); border: none; cursor: pointer; font-size: 13px; font-weight: 600; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-ghost { background: transparent; border: 1px solid var(--line); color: var(--ink); }
.btn-ghost:hover { background: var(--paper); }
.btn-primary { background: var(--green); color: #fff; }
.btn-primary:hover:not(:disabled) { filter: brightness(1.1); }
</style>
