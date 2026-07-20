<script setup lang="ts">
const emit = defineEmits<{ confirm: []; reject: [] }>()
</script>

<template>
  <div class="overlay">
    <section class="dialog" role="dialog" aria-modal="true" aria-labelledby="confirm-title">
      <span class="dialog-mark" aria-hidden="true">!</span>
      <h2 id="confirm-title">人工确认敏感操作</h2>
      <p>当前工单涉及中风险业务动作，需要坐席确认字段、客户身份和处理原因后再继续执行。</p>
      <p class="hint">拒绝后系统会转为人工接管，不会继续自动调用业务工具。</p>
      <div class="actions">
        <button class="btn btn-reject" type="button" @click="emit('reject')">转人工处理</button>
        <button class="btn btn-confirm" type="button" @click="emit('confirm')">确认执行</button>
      </div>
    </section>
  </div>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background: rgba(31, 41, 51, 0.52);
}
.dialog {
  width: min(440px, 100%);
  padding: 22px;
  border: 1px solid var(--line-dark);
  background: var(--panel);
  box-shadow: 0 24px 70px rgba(31, 41, 51, 0.28);
}
.dialog-mark {
  width: 34px;
  height: 34px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 12px;
  border: 1px solid rgba(196, 123, 24, 0.34);
  background: var(--amber-soft);
  color: var(--warn);
  font-family: var(--mono);
  font-weight: 900;
}
h2 {
  font-size: 18px;
}
p {
  margin-top: 10px;
  color: var(--ink-2);
  font-size: 14px;
  line-height: 1.7;
}
.hint {
  color: var(--muted);
  font-size: 13px;
}
.actions {
  display: flex;
  gap: 10px;
  margin-top: 20px;
}
.btn {
  flex: 1;
  padding: 8px;
  font-size: 13px;
  font-weight: 900;
}
.btn-confirm {
  border-color: var(--brand-dark);
  background: var(--brand);
  color: #fff;
}
.btn-reject {
  border-color: rgba(180, 35, 53, 0.3);
  background: var(--red-soft);
  color: var(--danger);
}
</style>
