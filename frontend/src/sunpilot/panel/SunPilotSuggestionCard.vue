<script setup lang="ts">
defineProps<{
  title: string
  body: string
  warning?: boolean
}>()
</script>

<template>
  <article class="summary-card" :class="{ warning }">
    <span>当前建议</span>
    <strong>{{ title }}</strong>
    <p>{{ body }}</p>
  </article>
</template>

<style scoped>
.summary-card {
  display: grid;
  gap: 6px;
  padding: 12px;
  border: 1px solid #dbe3eb;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 1px 1px rgba(15, 23, 42, 0.03);
}
.summary-card.warning {
  border-color: #fde68a;
  background: #fffbeb;
}
.summary-card span {
  color: #64748b;
  font-size: 12px;
  font-weight: 900;
}
.summary-card strong {
  color: #142033;
  font-size: 15px;
}
.summary-card p {
  margin: 0;
  color: #64748b;
  font-size: 12px;
  line-height: 1.55;
}
</style>
