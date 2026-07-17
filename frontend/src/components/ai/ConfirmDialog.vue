<script setup lang="ts">
const emit = defineEmits<{ confirm: []; reject: [] }>()
</script>
<template>
  <div class="overlay">
    <div class="dialog">
      <h3>⚠️ 操作确认</h3>
      <p>此工单涉及中风险操作，需要您确认后继续执行业务处理。</p>
      <p class="hint">请检查字段是否正确，确认后系统将执行对应业务操作。</p>
      <div class="actions">
        <button class="btn btn-reject" @click="emit('reject')">拒绝（转人工）</button>
        <button class="btn btn-confirm" @click="emit('confirm')">确认执行</button>
      </div>
    </div>
  </div>
</template>
<style scoped>
.overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 100; }
.dialog { background: var(--panel); border-radius: 12px; padding: 28px; max-width: 400px; width: 90%; box-shadow: 0 20px 60px rgba(0,0,0,0.2); }
.dialog h3 { font-size: 16px; margin-bottom: 12px; }
.dialog p { font-size: 14px; color: var(--ink); margin-bottom: 8px; line-height: 1.6; }
.hint { font-size: 12px; color: var(--muted); }
.actions { display: flex; gap: 10px; margin-top: 20px; }
.btn { flex: 1; padding: 10px; border: none; border-radius: var(--radius); font-size: 13px; font-weight: 600; cursor: pointer; }
.btn-confirm { background: var(--green); color: #fff; }
.btn-reject { background: var(--red-soft); color: var(--red); }
</style>
