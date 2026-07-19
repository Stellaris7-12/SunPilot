<script setup lang="ts">
import { computed } from 'vue'
import type { AiProcessResult, Ticket } from '../../types'
import { evidenceIds, nextOwner, statusMeta, suggestedAction } from '../../utils/business'
import StatusBadge from '../shared/StatusBadge.vue'

const props = defineProps<{
  ticket: Ticket
  result: AiProcessResult | null
  processing?: boolean
}>()

const emit = defineEmits<{
  fillReply: []
  checkTicket: []
  locateTools: []
  scrollReview: []
  process: []
}>()

const hasReplyDraft = computed(() =>
  Boolean(props.result?.notification?.standardReply?.body || props.result?.replyDraft)
)
const missingFields = computed(() => props.result?.missingFields || [])
const ids = computed(() => evidenceIds(props.result))
const status = computed(() => statusMeta(props.ticket.status))
const primaryAction = computed(() => suggestedAction(props.ticket, props.result, props.processing))
</script>

<template>
  <section class="action-rail-card">
    <div class="rail-head">
      <span class="section-title">坐席动作栏</span>
      <StatusBadge :value="status.label" :tone="status.tone" />
    </div>

    <div class="next-card">
      <span>建议动作</span>
      <strong>{{ primaryAction }}</strong>
      <p>下一负责人：{{ nextOwner(result, ticket.status) }}</p>
    </div>

    <div class="action-stack">
      <button class="action primary" type="button" :disabled="processing" @click="emit('process')">
        <span aria-hidden="true">▶</span>
        {{ processing ? '处理中' : result ? '重新生成建议' : '启动 AI 辅助' }}
      </button>
      <button class="action" type="button" :disabled="!hasReplyDraft" @click="emit('fillReply')">
        <span aria-hidden="true">✎</span>
        填入回单草稿
      </button>
      <button class="action" type="button" :disabled="!result" @click="emit('checkTicket')">
        <span aria-hidden="true">!</span>
        查看风险/缺失字段
      </button>
      <button class="action" type="button" @click="emit('locateTools')">
        <span aria-hidden="true">#</span>
        查看工具目录
      </button>
      <button class="action" type="button" :disabled="!result" @click="emit('scrollReview')">
        <span aria-hidden="true">✓</span>
        进入回单复核
      </button>
    </div>

    <div v-if="missingFields.length" class="rail-note warn">
      <strong>待补充字段</strong>
      <p>{{ missingFields.join('、') }}</p>
    </div>
    <div v-if="ids.length" class="rail-note">
      <strong>证据编号</strong>
      <p class="mono">{{ ids.join(' / ') }}</p>
    </div>
  </section>
</template>

<style scoped>
.action-rail-card {
  position: sticky;
  top: 16px;
  padding: 18px;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
}
.rail-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 12px;
}
.next-card {
  padding: 14px;
  border-radius: var(--radius);
  background: var(--ink);
  color: #fff;
}
.next-card span {
  display: block;
  color: rgba(255, 255, 255, 0.68);
  font-size: 12px;
  font-weight: 800;
}
.next-card strong {
  display: block;
  margin-top: 5px;
  font-size: 18px;
}
.next-card p {
  margin-top: 8px;
  color: rgba(255, 255, 255, 0.76);
  font-size: 12px;
}
.action-stack {
  display: grid;
  gap: 9px;
  margin-top: 12px;
}
.action {
  width: 100%;
  display: inline-flex;
  align-items: center;
  justify-content: flex-start;
  gap: 10px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--panel-2);
  color: var(--ink);
  padding: 10px 12px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 900;
}
.action span {
  width: 20px;
  height: 20px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  background: var(--neutral-soft);
  font-family: var(--mono);
  font-size: 12px;
}
.action.primary {
  border-color: var(--green);
  background: var(--green);
  color: #fff;
}
.action.primary span { background: rgba(255, 255, 255, 0.2); }
.action:hover:not(:disabled) { transform: translateY(-1px); box-shadow: var(--shadow-soft); }
.action:disabled { opacity: 0.46; cursor: not-allowed; }
.rail-note {
  margin-top: 12px;
  padding: 11px 12px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--panel-2);
}
.rail-note.warn {
  border-color: rgba(196, 134, 34, 0.28);
  background: var(--amber-soft);
}
.rail-note strong {
  display: block;
  margin-bottom: 5px;
  font-size: 12px;
}
.rail-note p {
  color: var(--ink-2);
  font-size: 12px;
  line-height: 1.55;
  overflow-wrap: anywhere;
}
@media (max-width: 1180px) {
  .action-rail-card { position: static; }
}
</style>
