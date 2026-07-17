<script setup lang="ts">
import { computed } from 'vue'
const props = defineProps<{ draft: string; disabled: boolean }>()
const emit = defineEmits<{ 'update:draft': [value: string]; close: [value: string] }>()
const model = computed({ get: () => props.draft, set: (v) => emit('update:draft', v) })
</script>
<template>
  <div class="card">
    <h4 class="card-title">回单草稿</h4>
    <textarea v-model="model" rows="6" class="editor" placeholder="AI 回单草稿将出现在这里..." />
    <button class="btn btn-close" :disabled="disabled || !draft" @click="emit('close', draft)">
      人工复核并结单
    </button>
  </div>
</template>
<style scoped>
.card { background: var(--panel); border-radius: var(--radius); padding: 20px; box-shadow: var(--shadow); }
.card-title { font-size: 13px; color: var(--muted); margin-bottom: 12px; text-transform: uppercase; letter-spacing: 0.5px; }
.editor { width: 100%; padding: 12px; border: 1px solid var(--line); border-radius: var(--radius); font-size: 13px; font-family: inherit; line-height: 1.6; resize: vertical; }
.editor:focus { outline: none; border-color: var(--green); box-shadow: 0 0 0 3px rgba(5,150,105,0.1); }
.btn-close { width: 100%; margin-top: 12px; padding: 10px; border: none; border-radius: var(--radius); background: var(--green); color: #fff; font-size: 14px; font-weight: 600; cursor: pointer; }
.btn-close:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
