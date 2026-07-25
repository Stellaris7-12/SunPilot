<script setup lang="ts">
defineProps<{
  steps: Array<{
    label: string
    status: string
  }>
}>()
</script>

<template>
  <section class="flow-card">
    <div class="card-title">业务流</div>
    <ol class="pilot-flow">
      <li v-for="step in steps" :key="step.label">
        <span>{{ step.label }}</span>
        <strong>{{ step.status }}</strong>
      </li>
    </ol>
  </section>
</template>

<style scoped>
.flow-card {
  display: grid;
  gap: 8px;
  padding: 10px;
  border: 1px solid #dbe3eb;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 1px 1px rgba(15, 23, 42, 0.03);
}
.card-title {
  color: #64748b;
  font-size: 12px;
  font-weight: 900;
}
.pilot-flow {
  display: grid;
  margin: 0;
  padding: 0;
  list-style: none;
}
.pilot-flow li {
  min-height: 32px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
  padding: 7px 0 7px 16px;
  border-top: 1px solid #edf1f5;
  position: relative;
}
.pilot-flow li:first-child {
  border-top: 0;
}
.pilot-flow li::before {
  content: "";
  position: absolute;
  left: 2px;
  top: 13px;
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: #0e7490;
}
.pilot-flow span {
  min-width: 0;
  color: #334155;
  font-size: 12px;
  font-weight: 900;
  overflow-wrap: anywhere;
}
.pilot-flow strong {
  color: #64748b;
  font-size: 11px;
  white-space: nowrap;
}
</style>
