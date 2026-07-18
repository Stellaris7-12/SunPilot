<script setup lang="ts">
import { computed } from 'vue'
import type { ClosureSuggestion } from '../../types'
const props = defineProps<{ draft: string; disabled: boolean; closureSuggestion?: ClosureSuggestion | null }>()
const emit = defineEmits<{ 'update:draft': [value: string]; close: [value: string] }>()
const model = computed({ get: () => props.draft, set: (v) => emit('update:draft', v) })
const buttonLabel = computed(() => {
  if (!props.closureSuggestion) return '人工复核并结单'
  return props.closureSuggestion.canClose ? '确认结案' : '人工处理后结案'
})
</script>
<template>
  <div class="card">
    <h4 class="card-title">回单草稿</h4>
    <div v-if="closureSuggestion" class="closure-note" :data-ready="closureSuggestion.canClose">
      <strong>{{ closureSuggestion.canClose ? '建议复核后结案' : '暂不建议直接结案' }}</strong>
      <p>{{ closureSuggestion.reason }}</p>
    </div>
    <textarea v-model="model" rows="6" class="editor" placeholder="AI 回单草稿将出现在这里..." />
    <button class="btn btn-close" :disabled="disabled || !draft" @click="emit('close', draft)">
      {{ buttonLabel }}
    </button>
  </div>
</template>
<style scoped>
.card { background: var(--panel); border-radius: var(--radius); padding: 20px; box-shadow: var(--shadow); }
.card-title { font-size: 13px; color: var(--muted); margin-bottom: 12px; text-transform: uppercase; letter-spacing: 0.5px; }
.closure-note { border: 1px solid var(--line); border-radius: 6px; padding: 9px 10px; margin-bottom: 10px; background: #fff7ed; color: #9a3412; }
.closure-note[data-ready="true"] { background: var(--green-soft); color: var(--green); }
.closure-note strong { display: block; font-size: 13px; margin-bottom: 4px; }
.closure-note p { font-size: 12px; line-height: 1.5; overflow-wrap: anywhere; }
.editor { width: 100%; padding: 12px; border: 1px solid var(--line); border-radius: var(--radius); font-size: 13px; font-family: inherit; line-height: 1.6; resize: vertical; }
.editor:focus { outline: none; border-color: var(--green); box-shadow: 0 0 0 3px rgba(5,150,105,0.1); }
.btn-close { width: 100%; margin-top: 12px; padding: 10px; border: none; border-radius: var(--radius); background: var(--green); color: #fff; font-size: 14px; font-weight: 600; cursor: pointer; }
.btn-close:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
