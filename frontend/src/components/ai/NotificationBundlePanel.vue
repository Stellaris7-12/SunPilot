<script setup lang="ts">
import { computed } from 'vue'
import type { AiProcessResult, NotificationArtifact } from '../../types'

const props = defineProps<{ result: AiProcessResult }>()

const notification = computed(() => props.result.notification)
const standardReply = computed<NotificationArtifact | null>(() => {
  if (notification.value?.standardReply) return notification.value.standardReply
  if (!props.result.replyDraft) return null
  return {
    title: '标准回单',
    body: props.result.replyDraft,
    status: 'needs_review',
    evidenceIds: [],
    nextOwner: 'human',
  }
})
const internalNotice = computed(() => notification.value?.internalNotice || null)
const reviewSummary = computed(() => notification.value?.reviewSummary || null)
const closureSuggestion = computed(() => notification.value?.closureSuggestion || null)
const followUp = computed(() => notification.value?.followUp || null)

function statusText(status?: string) {
  const map: Record<string, string> = {
    ready: '待复核',
    needs_info: '待补充',
    needs_review: '待人工复核',
    escalated: '已升级',
    failed: '处理失败',
    closed: '已结案',
  }
  return status ? map[status] || status : '待复核'
}

function ownerText(owner?: string) {
  const map: Record<string, string> = {
    customer: '客户',
    agent: 'AI Agent',
    human: '业务人员',
    system: '系统',
  }
  return owner ? map[owner] || owner : '业务人员'
}

function joinValues(values?: string[]) {
  return values?.length ? values.join('、') : '无'
}
</script>

<template>
  <div class="card notification-card">
    <div class="card-head">
      <h4 class="card-title">通知与回单闭环</h4>
      <span v-if="standardReply" class="status-pill" :data-status="standardReply.status">
        {{ statusText(standardReply.status) }}
      </span>
    </div>

    <section v-if="standardReply" class="notice-section primary">
      <div class="section-head">
        <h5>{{ standardReply.title || '标准回单' }}</h5>
        <span>下一步：{{ ownerText(standardReply.nextOwner) }}</span>
      </div>
      <p>{{ standardReply.body }}</p>
      <div v-if="standardReply.evidenceIds.length" class="evidence-line">
        证据编号：{{ joinValues(standardReply.evidenceIds) }}
      </div>
    </section>

    <section v-if="internalNotice" class="notice-section">
      <div class="section-head">
        <h5>{{ internalNotice.title || '内部通知' }}</h5>
        <span>{{ statusText(internalNotice.status) }} · {{ ownerText(internalNotice.nextOwner) }}</span>
      </div>
      <p>{{ internalNotice.body }}</p>
    </section>

    <section v-if="reviewSummary" class="notice-section">
      <div class="section-head">
        <h5>复核摘要</h5>
        <span>证据：{{ joinValues(reviewSummary.toolEvidenceIds) }}</span>
      </div>
      <div class="summary-grid">
        <div>
          <label>复核原因</label>
          <p>{{ reviewSummary.reason || '无' }}</p>
        </div>
        <div>
          <label>风险判断</label>
          <p>{{ reviewSummary.riskDecision || result.riskDecision || '无' }}</p>
        </div>
        <div>
          <label>缺失字段</label>
          <p>{{ joinValues(reviewSummary.missingFields) }}</p>
        </div>
        <div>
          <label>建议操作</label>
          <p>{{ reviewSummary.suggestedAction || '人工复核回单内容后处理' }}</p>
        </div>
      </div>
    </section>

    <section v-if="closureSuggestion" class="notice-section">
      <div class="section-head">
        <h5>结案建议</h5>
        <span :class="closureSuggestion.canClose ? 'ok' : 'warn'">
          {{ closureSuggestion.canClose ? '建议复核后结案' : '暂不建议直接结案' }}
        </span>
      </div>
      <p>{{ closureSuggestion.reason }}</p>
    </section>

    <section v-if="followUp?.enabled" class="notice-section">
      <div class="section-head">
        <h5>回访预留</h5>
        <span>{{ followUp.triggerStatus || 'closed' }}</span>
      </div>
      <p>{{ followUp.template }}</p>
    </section>
  </div>
</template>

<style scoped>
.card { background: var(--panel); border-radius: var(--radius); padding: 20px; box-shadow: var(--shadow); }
.card-head { display: flex; justify-content: space-between; gap: 12px; align-items: center; margin-bottom: 12px; }
.card-title { font-size: 13px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; }
.status-pill { flex-shrink: 0; border-radius: 999px; padding: 4px 8px; font-size: 12px; font-weight: 700; background: var(--paper); color: var(--muted); }
.status-pill[data-status="ready"] { background: var(--green-soft); color: var(--green); }
.status-pill[data-status="needs_info"], .status-pill[data-status="needs_review"] { background: #fef3c7; color: #a16207; }
.status-pill[data-status="escalated"], .status-pill[data-status="failed"] { background: var(--red-soft); color: var(--red); }
.notice-section { border-top: 1px solid var(--line); padding-top: 12px; margin-top: 12px; }
.notice-section:first-of-type { border-top: none; padding-top: 0; margin-top: 0; }
.notice-section.primary p { font-size: 14px; }
.section-head { display: flex; justify-content: space-between; gap: 10px; align-items: center; margin-bottom: 7px; }
.section-head h5 { font-size: 12px; color: var(--muted); text-transform: uppercase; }
.section-head span { font-size: 12px; color: var(--muted); text-align: right; }
.notice-section p { font-size: 13px; line-height: 1.6; overflow-wrap: anywhere; }
.evidence-line { margin-top: 8px; font-size: 12px; color: var(--blue); overflow-wrap: anywhere; }
.summary-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.summary-grid > div { border: 1px solid var(--line); border-radius: 6px; padding: 8px 10px; background: var(--paper); min-width: 0; }
.summary-grid label { display: block; color: var(--muted); font-size: 11px; margin-bottom: 4px; }
.summary-grid p { font-size: 12px; }
.ok { color: var(--green) !important; font-weight: 700; }
.warn { color: #a16207 !important; font-weight: 700; }
@media (max-width: 720px) {
  .summary-grid { grid-template-columns: 1fr; }
  .section-head { align-items: flex-start; flex-direction: column; }
  .section-head span { text-align: left; }
}
</style>
