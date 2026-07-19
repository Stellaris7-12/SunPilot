<script setup lang="ts">
defineProps<{ content: string }>()
</script>

<template>
  <section class="content-card">
    <div class="card-head">
      <span class="section-title">客户诉求原文</span>
      <span class="source-tag">通话/工单文本</span>
    </div>
    <p class="content-text">{{ content }}</p>
  </section>
</template>

<style scoped>
.content-card {
  padding: 20px;
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
.source-tag {
  flex-shrink: 0;
  color: var(--muted);
  font-size: 12px;
  font-weight: 800;
}
.content-text {
  color: var(--ink-2);
  font-size: 14px;
  line-height: 1.9;
  white-space: pre-wrap;
}
</style>
