<script setup lang="ts">
defineProps<{
  title: string
  count?: number
  open?: boolean
}>()
</script>

<template>
  <details class="fold-card" :open="open">
    <summary>{{ title }} <strong>{{ count ?? 0 }}</strong></summary>
    <slot />
  </details>
</template>

<style scoped>
.fold-card {
  overflow: hidden;
  border: 1px solid #dbe3eb;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 1px 1px rgba(15, 23, 42, 0.03);
}
.fold-card summary {
  min-height: 36px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 10px;
  color: #334155;
  font-size: 12px;
  font-weight: 900;
  cursor: pointer;
}
.fold-card summary strong {
  color: #64748b;
  font-family: var(--mono);
  font-size: 11px;
}
</style>
