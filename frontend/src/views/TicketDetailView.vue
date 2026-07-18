<script setup lang="ts">
import { onMounted, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useTicketStore } from '../stores/ticket'
import AppHeader from '../components/layout/AppHeader.vue'
import AppSidebar from '../components/layout/AppSidebar.vue'
import TicketInfo from '../components/ticket/TicketInfo.vue'
import TicketContent from '../components/ticket/TicketContent.vue'
import AiProcessPanel from '../components/ai/AiProcessPanel.vue'
import AgentTraceTimeline from '../components/ai/AgentTraceTimeline.vue'
import AiResultCard from '../components/ai/AiResultCard.vue'
import NotificationBundlePanel from '../components/ai/NotificationBundlePanel.vue'
import ReplyDraftEditor from '../components/ai/ReplyDraftEditor.vue'
import ConfirmDialog from '../components/ai/ConfirmDialog.vue'
import PageAssistantPanel from '../components/ai/PageAssistantPanel.vue'
import ToolRegistryPanel from '../components/tools/ToolRegistryPanel.vue'

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
  scrollToId(store.aiResult?.missingFields?.length ? 'tool-audit' : 'ai-result-card')
}
</script>
<template>
  <div class="detail-layout">
    <AppSidebar />
    <div class="detail-main">
      <AppHeader
        :title="ticket?.title || ''"
        :processing="store.isProcessing"
        @process="handleProcess"
        @reset="handleReset"
      />
      <div v-if="ticket" class="detail-body">
        <div class="content-col">
          <TicketInfo :ticket="ticket" />
          <TicketContent :content="ticket.content" />
        </div>
        <div class="insight-col">
          <AiProcessPanel :trace-steps="store.traceSteps" :is-processing="store.isProcessing" />
          <AgentTraceTimeline :steps="store.traceSteps" />
          <PageAssistantPanel
            :ticket="ticket"
            :result="store.aiResult"
            @fill-reply="fillReplyDraft"
            @check-ticket="checkCurrentTicket"
            @locate-tools="scrollToId('tool-registry')"
            @scroll-review="scrollToId('reply-review')"
          />
          <div id="ai-result-card">
            <AiResultCard v-if="store.aiResult" :result="store.aiResult" />
          </div>
          <NotificationBundlePanel v-if="store.aiResult" :result="store.aiResult" />
          <div id="reply-review">
            <ReplyDraftEditor
              v-if="store.aiResult"
              v-model:draft="store.replyDraft"
              :disabled="store.isProcessing"
              :closure-suggestion="store.aiResult.notification?.closureSuggestion"
              @close="(reply: string) => store.closeTicket(ticketId, reply)"
            />
          </div>
          <div id="tool-registry">
            <ToolRegistryPanel />
          </div>
        </div>
      </div>
      <div v-else class="detail-empty">未找到工单</div>
    </div>
    <ConfirmDialog
      v-if="store.workflowPaused"
      @confirm="store.confirmAction(ticketId, true)"
      @reject="store.confirmAction(ticketId, false)"
    />
  </div>
</template>
<style scoped>
.detail-layout { display: flex; height: 100vh; }
.detail-main { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.detail-body { flex: 1; display: flex; gap: 20px; padding: 20px; overflow-y: auto; }
.content-col { flex: 1; display: flex; flex-direction: column; gap: 16px; min-width: 0; }
.insight-col { width: 420px; flex-shrink: 0; display: flex; flex-direction: column; gap: 16px; overflow-y: auto; }
.detail-empty { flex: 1; display: flex; align-items: center; justify-content: center; color: var(--muted); }
</style>
