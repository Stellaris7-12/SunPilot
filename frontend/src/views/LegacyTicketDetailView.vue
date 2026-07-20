<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import AgentTraceTimeline from '../components/ai/AgentTraceTimeline.vue'
import AiProcessPanel from '../components/ai/AiProcessPanel.vue'
import AiResultCard from '../components/ai/AiResultCard.vue'
import ConfirmDialog from '../components/ai/ConfirmDialog.vue'
import NotificationBundlePanel from '../components/ai/NotificationBundlePanel.vue'
import PageAssistantPanel from '../components/ai/PageAssistantPanel.vue'
import ReplyDraftEditor from '../components/ai/ReplyDraftEditor.vue'
import AppHeader from '../components/layout/AppHeader.vue'
import AppSidebar from '../components/layout/AppSidebar.vue'
import ToolRegistryPanel from '../components/tools/ToolRegistryPanel.vue'
import TicketContent from '../components/ticket/TicketContent.vue'
import TicketInfo from '../components/ticket/TicketInfo.vue'
import { useTicketStore } from '../stores/ticket'

const route = useRoute()
const store = useTicketStore()

const ticketId = computed(() => route.params.id as string)
const ticket = computed(() => store.selectedTicket)

onMounted(async () => {
  await store.fetchTickets()
  if (ticketId.value) await store.loadTicketContext(ticketId.value)
})

watch(ticketId, async id => {
  if (id) await store.loadTicketContext(id)
})

function handleProcess() {
  if (ticketId.value) store.startAiProcess(ticketId.value)
}

function handleReset() {
  store.resetState()
}

function scrollToId(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function fillReplyDraft() {
  const draft = store.aiResult?.notification?.standardReply?.body || store.aiResult?.replyDraft
  if (draft) {
    store.replyDraft = draft
    scrollToId('reply-review')
  }
}

function checkCurrentTicket() {
  scrollToId(store.aiResult?.missingFields?.length ? 'tool-audit' : 'case-result')
}
</script>

<template>
  <div class="detail-layout">
    <AppSidebar />
    <div class="detail-main">
      <AppHeader :ticket="ticket" :processing="store.isProcessing" @process="handleProcess" @reset="handleReset" />

      <div v-if="ticket" class="detail-body">
        <main class="case-col">
          <TicketInfo :ticket="ticket" :result="store.aiResult" :processing="store.isProcessing" />
          <TicketContent :content="ticket.content" />
          <AiProcessPanel :trace-steps="store.traceSteps" :is-processing="store.isProcessing" :result="store.aiResult" />
          <div id="case-result">
            <AiResultCard v-if="store.aiResult" :result="store.aiResult" />
            <section v-else class="empty-state">
              <span class="section-title">处理建议</span>
              <h2>等待坐席启动 AI 辅助</h2>
              <p>系统会按业务场景提取字段、分诊风险、调用工具或生成转人工建议，并留下证据编号。</p>
            </section>
          </div>
          <NotificationBundlePanel v-if="store.aiResult" :result="store.aiResult" />
          <AgentTraceTimeline :steps="store.traceSteps" />
          <div id="tool-registry">
            <ToolRegistryPanel />
          </div>
        </main>

        <aside class="operator-col">
          <PageAssistantPanel
            :ticket="ticket"
            :result="store.aiResult"
            :processing="store.isProcessing"
            @process="handleProcess"
            @fill-reply="fillReplyDraft"
            @check-ticket="checkCurrentTicket"
            @locate-tools="scrollToId('tool-registry')"
            @scroll-review="scrollToId('reply-review')"
          />
          <div id="reply-review">
            <ReplyDraftEditor
              v-if="store.aiResult"
              v-model:draft="store.replyDraft"
              :disabled="store.isProcessing"
              :closure-suggestion="store.aiResult.notification?.closureSuggestion"
              @close="(reply: string) => store.closeTicket(ticketId, reply)"
            />
          </div>
        </aside>
      </div>

      <div v-else class="detail-empty">
        <span class="section-title">未找到工单</span>
        <p>请从左侧工作池重新选择工单。</p>
      </div>
    </div>

    <ConfirmDialog
      v-if="store.workflowPaused"
      @confirm="store.confirmAction(ticketId, true)"
      @reject="store.confirmAction(ticketId, false)"
    />
  </div>
</template>

<style scoped>
.detail-layout {
  min-height: 100vh;
  display: flex;
}
.detail-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.detail-body {
  flex: 1;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 360px;
  gap: 18px;
  padding: 18px;
  overflow-y: auto;
}
.case-col {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.operator-col {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.empty-state {
  padding: 24px;
  border: 1px dashed var(--line-strong);
  border-radius: var(--radius);
  background: rgba(255, 255, 255, 0.72);
  text-align: left;
}
.empty-state h2 {
  margin-top: 8px;
  font-size: 20px;
}
.empty-state p {
  max-width: 640px;
  margin-top: 8px;
  color: var(--muted);
  font-size: 14px;
  line-height: 1.7;
}
.detail-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--muted);
}
@media (max-width: 1180px) {
  .detail-layout { flex-direction: column; }
  .detail-body { grid-template-columns: 1fr; }
}
@media (max-width: 720px) {
  .detail-body { padding: 12px; }
}
</style>
