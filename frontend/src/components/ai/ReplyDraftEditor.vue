<script setup lang="ts">
import { computed } from 'vue'
import type { ClosureSuggestion } from '../../types'

const props = defineProps<{ draft: string; disabled: boolean; closureSuggestion?: ClosureSuggestion | null }>()
const emit = defineEmits<{ 'update:draft': [value: string]; close: [value: string] }>()

const model = computed({ get: () => props.draft, set: (value) => emit('update:draft', value) })
const buttonLabel = computed(() => {
  if (!props.closureSuggestion) return '复核并结案'
  return props.closureSuggestion.canClose ? '确认结案' : '人工处理后结案'
})
</script>

<template>
  <section class="reply-editor">
    <div class="card-head">
      <span class="section-title">坐席回单</span>
      <span>{{ draft ? '草稿已生成' : '等待生成' }}</span>
    </div>
    <div v-if="closureSuggestion" class="closure-note" :data-ready="closureSuggestion.canClose">
      <strong>{{ closureSuggestion.canClose ? '建议复核后结案' : '暂不建议直接结案' }}</strong>
      <p>{{ closureSuggestion.reason }}</p>
    </div>
    <textarea v-model="model" rows="8" class="editor" placeholder="客户回单将在这里生成，坐席复核后再提交。" />
    <button class="btn-close" type="button" :disabled="disabled || !draft" @click="emit('close', draft)">
      <span aria-hidden="true">✓</span>
      {{ buttonLabel }}
    </button>
  </section>
</template>

<style scoped>
.reply-editor {
  padding: 18px;
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
.card-head span:last-child {
  color: var(--muted);
  font-size: 12px;
  font-weight: 800;
}
.closure-note {
  border: 1px solid rgba(196, 134, 34, 0.28);
  border-radius: var(--radius);
  padding: 10px 12px;
  margin-bottom: 12px;
  background: var(--amber-soft);
  color: var(--amber);
}
.closure-note[data-ready="true"] { border-color: rgba(47, 143, 103, 0.28); background: var(--green-soft); color: var(--green); }
.closure-note strong { display: block; font-size: 13px; margin-bottom: 4px; }
.closure-note p { font-size: 12px; line-height: 1.55; overflow-wrap: anywhere; }
.editor {
  width: 100%;
  min-height: 180px;
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--panel-2);
  color: var(--ink);
  font-size: 13px;
  line-height: 1.7;
  resize: vertical;
}
.editor:focus { border-color: var(--green); outline: none; box-shadow: 0 0 0 3px rgba(47, 143, 103, 0.12); }
.btn-close {
  width: 100%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-top: 12px;
  border: 1px solid var(--green);
  border-radius: var(--radius);
  background: var(--green);
  color: #fff;
  padding: 10px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 900;
}
.btn-close:disabled { opacity: 0.45; cursor: not-allowed; }
</style>
