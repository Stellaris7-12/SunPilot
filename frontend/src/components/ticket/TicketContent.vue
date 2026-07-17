<script setup lang="ts">
defineProps<{ content: string }>()
</script>
<template>
  <div class="card">
    <h4 class="card-title">工单原文</h4>
    <p class="content-text">{{ content }}</p>
  </div>
</template>
<style scoped>
.card { background: var(--panel); border-radius: var(--radius); padding: 20px; box-shadow: var(--shadow); }
.card-title { font-size: 13px; color: var(--muted); margin-bottom: 12px; text-transform: uppercase; letter-spacing: 0.5px; }
.content-text { font-size: 14px; line-height: 1.8; color: var(--ink); white-space: pre-wrap; }
</style>
