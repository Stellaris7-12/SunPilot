<script setup lang="ts">
interface SunPilotQuickAction {
  label: string
  disabled?: boolean
}

defineProps<{
  actions: SunPilotQuickAction[]
  busy?: boolean
}>()

const emit = defineEmits<{
  select: [index: number]
}>()
</script>

<template>
  <section class="quick-card">
    <div class="card-title">快捷操作</div>
    <div class="quick-row">
      <button
        v-for="(action, index) in actions"
        :key="action.label"
        class="quick-btn"
        type="button"
        :disabled="busy || action.disabled"
        @click="emit('select', index)"
      >
        {{ action.label }}
      </button>
    </div>
  </section>
</template>

<style scoped>
.quick-card {
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
.quick-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.quick-btn {
  min-height: 26px;
  padding: 0 9px;
  border: 1px solid #d8e0e8;
  border-radius: 999px;
  background: #f8fafc;
  color: #344154;
  font-size: 12px;
  font-weight: 800;
}
.quick-btn:hover:not(:disabled) {
  border-color: #0e7490;
  background: #ecfeff;
}
.quick-btn:disabled {
  color: #a3adba;
  background: #f7f8fa;
  cursor: not-allowed;
}
</style>
