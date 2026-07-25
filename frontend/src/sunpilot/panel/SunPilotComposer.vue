<script setup lang="ts">
defineProps<{
  modelValue: string
  placeholder: string
  mode: 'qa' | 'task'
  busy?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
  'update:mode': [value: 'qa' | 'task']
  submit: []
  openSettings: []
}>()

function handleKeydown(event: KeyboardEvent) {
  if (event.isComposing) return
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    emit('submit')
  }
}
</script>

<template>
  <div class="input-shell">
    <textarea
      class="agent-input"
      :value="modelValue"
      :placeholder="placeholder"
      data-page-agent-target="page-agent-command"
      @input="emit('update:modelValue', ($event.target as HTMLTextAreaElement).value)"
      @keydown="handleKeydown"
    />
    <div class="composer-tools">
      <div class="mode-switch" aria-label="SunPilot 输入模式">
        <button type="button" :class="{ active: mode === 'qa' }" :disabled="busy" @click="emit('update:mode', 'qa')">询问</button>
        <button type="button" :class="{ active: mode === 'task' }" :disabled="busy" @click="emit('update:mode', 'task')">办理</button>
      </div>
      <div class="composer-spacer"></div>
      <button class="key-chip" type="button" title="连接设置" @click="emit('openSettings')">设置</button>
      <button class="send-btn" type="button" :disabled="!modelValue.trim() || busy" @click="emit('submit')">↑</button>
    </div>
  </div>
</template>

<style scoped>
.input-shell {
  display: grid;
  gap: 8px;
  padding: 12px;
  border: 1px solid #d7dde6;
  border-radius: 18px;
  background: #f3f5f7;
}
.agent-input {
  min-height: 76px;
  max-height: 120px;
  resize: vertical;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--ink);
  font-size: 13px;
  line-height: 1.5;
}
.agent-input::placeholder {
  color: #99a4b2;
}
.composer-tools {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}
.mode-switch {
  min-height: 30px;
  display: inline-grid;
  grid-template-columns: 1fr 1fr;
  gap: 2px;
  padding: 2px;
  border: 1px solid #d7dde6;
  border-radius: 999px;
  background: #e8edf3;
}
.mode-switch button,
.key-chip {
  min-height: 26px;
  padding: 0 9px;
  border: 0;
  border-radius: 999px;
  color: #5d6878;
  font-size: 12px;
  font-weight: 900;
}
.mode-switch button {
  min-width: 44px;
  background: transparent;
}
.mode-switch button.active {
  background: #fff;
  color: #0e7490;
  box-shadow: 0 1px 4px rgba(15, 23, 42, 0.12);
}
.composer-spacer {
  flex: 1 1 auto;
  min-width: 8px;
}
.key-chip {
  min-width: 44px;
  background: #e5e7eb;
  color: #475569;
}
.send-btn {
  width: 34px;
  min-width: 34px;
  height: 34px;
  min-height: 34px;
  border: 0;
  border-radius: 999px;
  background: #d1d5db;
  color: #fff;
  font-size: 21px;
  line-height: 1;
  font-weight: 900;
}
.send-btn:disabled {
  background: #e5e7eb;
  color: #9ca3af;
  cursor: not-allowed;
}
</style>
