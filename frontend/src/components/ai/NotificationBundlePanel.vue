<script setup lang="ts">
import { computed } from 'vue'
import type { AiProcessResult, NotificationArtifact } from '../../types'

const props = defineProps<{ result: AiProcessResult }>()

const notification = computed(() => props.result.notification)
const standardReply = computed<NotificationArtifact | null>(() => {
  if (notification.value?.standardReply) return notification.value.standardReply
  if (!props.result.replyDraft) return null
  return {
    title: '客户标准回单',
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
    agent: '系统',
    human: '坐席/复核岗',
    system: '系统',
  }
  return owner ? map[owner] || owner : '坐席/复核岗'
}

function joinValues(values?: string[]) {
  return values?.length ? values.join('、') : '暂无'
}
</script>

<template>
  <section class="notification-card">
    <div class="card-head">
      <span class="section-title">回单与复核闭环</span>
      <span v-if="standardReply" class="status-pill" :data-status="standardReply.status">
        {{ statusText(standardReply.status) }}
      </span>
    </div>

    <section v-if="standardReply" class="reply-block primary">
      <div class="block-head">
        <h3>{{ standardReply.title || '客户标准回单' }}</h3>
        <span>下一步：{{ ownerText(standardReply.nextOwner) }}</span>
      </div>
      <p>{{ standardReply.body }}</p>
      <div v-if="standardReply.evidenceIds.length" class="evidence-line">
        证据编号：{{ joinValues(standardReply.evidenceIds) }}
      </div>
    </section>

    <section v-if="internalNotice" class="reply-block">
      <div class="block-head">
        <h3>{{ internalNotice.title || '内部通知' }}</h3>
        <span>{{ statusText(internalNotice.status) }} / {{ ownerText(internalNotice.nextOwner) }}</span>
      </div>
      <p>{{ internalNotice.body }}</p>
    </section>

    <section v-if="reviewSummary" class="reply-block">
      <div class="block-head">
        <h3>人工复核摘要</h3>
        <span>证据：{{ joinValues(reviewSummary.toolEvidenceIds) }}</span>
      </div>
      <div class="summary-grid">
        <div>
          <label>复核原因</label>
          <p>{{ reviewSummary.reason || '暂无' }}</p>
        </div>
        <div>
          <label>风险判断</label>
          <p>{{ reviewSummary.riskDecision || result.riskDecision || '暂无' }}</p>
        </div>
        <div>
          <label>缺失字段</label>
          <p>{{ joinValues(reviewSummary.missingFields) }}</p>
        </div>
        <div>
          <label>建议操作</label>
          <p>{{ reviewSummary.suggestedAction || '复核回单内容后继续处理' }}</p>
        </div>
      </div>
    </section>

    <section v-if="closureSuggestion" class="reply-block closure">
      <div class="block-head">
        <h3>结案建议</h3>
        <span :class="closureSuggestion.canClose ? 'ok' : 'warn'">
          {{ closureSuggestion.canClose ? '建议复核后结案' : '暂不建议直接结案' }}
        </span>
      </div>
      <p>{{ closureSuggestion.reason }}</p>
    </section>

    <section v-if="followUp?.enabled" class="reply-block">
      <div class="block-head">
        <h3>回访预留</h3>
        <span>{{ followUp.triggerStatus || 'closed' }}</span>
      </div>
      <p>{{ followUp.template }}</p>
    </section>
  </section>
</template>

<style scoped>
.notification-card {
  padding: 20px;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  box-shadow: var(--shadow-soft);
}
.card-head, .block-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.status-pill {
  flex-shrink: 0;
  border-radius: 999px;
  padding: 4px 9px;
  font-size: 12px;
  font-weight: 800;
  background: var(--neutral-soft);
  color: var(--muted);
}
.status-pill[data-status="ready"], .status-pill[data-status="closed"] { background: var(--green-soft); color: var(--green); }
.status-pill[data-status="needs_info"], .status-pill[data-status="needs_review"] { background: var(--amber-soft); color: var(--amber); }
.status-pill[data-status="escalated"], .status-pill[data-status="failed"] { background: var(--red-soft); color: var(--red); }
.reply-block {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid var(--line);
}
.reply-block.primary {
  padding: 14px;
  border: 1px solid rgba(47, 143, 103, 0.22);
  border-radius: var(--radius);
  background: var(--green-soft);
}
.block-head { margin-bottom: 8px; }
h3 { font-size: 15px; }
.block-head span {
  color: var(--muted);
  font-size: 12px;
  font-weight: 800;
  text-align: right;
}
p {
  color: var(--ink-2);
  font-size: 13px;
  line-height: 1.75;
  overflow-wrap: anywhere;
}
.evidence-line {
  margin-top: 10px;
  color: var(--green);
  font-family: var(--mono);
  font-size: 12px;
  overflow-wrap: anywhere;
}
.summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}
.summary-grid > div {
  min-width: 0;
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--panel-2);
}
label {
  display: block;
  margin-bottom: 5px;
  color: var(--muted);
  font-size: 12px;
  font-weight: 800;
}
.closure {
  border-top-color: rgba(196, 134, 34, 0.26);
}
.ok { color: var(--green) !important; }
.warn { color: var(--amber) !important; }
@media (max-width: 780px) {
  .card-head, .block-head { align-items: flex-start; flex-direction: column; }
  .block-head span { text-align: left; }
  .summary-grid { grid-template-columns: 1fr; }
}
</style>
