import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type { Ticket, AiProcessResult, TraceStep } from '../types';
import { ticketApi } from '../api';

export const useTicketStore = defineStore('ticket', () => {
  // State
  const tickets = ref<Ticket[]>([]);
  const selectedTicketId = ref<string | null>(null);
  const isProcessing = ref(false);
  const aiResult = ref<AiProcessResult | null>(null);
  const traceSteps = ref<TraceStep[]>([]);
  const replyDraft = ref('');
  const workflowPaused = ref(false);

  // Getters
  const selectedTicket = computed(() =>
    tickets.value.find(t => t.id === selectedTicketId.value) || null
  );
  const openCount = computed(() => tickets.value.filter(t => t.status !== 'closed').length);
  const closedCount = computed(() => tickets.value.filter(t => t.status === 'closed').length);

  // Actions
  async function fetchTickets() {
    tickets.value = await ticketApi.list();
  }

  function selectTicket(id: string) {
    selectedTicketId.value = id;
    resetState();
  }

  async function startAiProcess(ticketId: string) {
    isProcessing.value = true;
    aiResult.value = null;
    traceSteps.value = [];
    replyDraft.value = '';
    workflowPaused.value = false;

    const url = ticketApi.getStreamUrl(ticketId);
    const eventSource = new EventSource(url);

    eventSource.addEventListener('agent_start', (e: MessageEvent) => {
      const { agent_id, agent_name } = JSON.parse(e.data);
      traceSteps.value.push({
        agent: agent_name, agentId: agent_id,
        summary: '执行中...', duration: '等待返回',
        status: 'RUNNING'
      });
    });

    eventSource.addEventListener('agent_thinking', (e: MessageEvent) => {
      const { agent_id, message } = JSON.parse(e.data);
      const step = traceSteps.value.find(s => s.agentId === agent_id && s.status === 'RUNNING');
      if (step) step.summary = message;
    });

    eventSource.addEventListener('agent_complete', (e: MessageEvent) => {
      const { agent_id, summary, duration_ms } = JSON.parse(e.data);
      const step = traceSteps.value.find(s => s.agentId === agent_id && s.status === 'RUNNING');
      if (step) {
        step.status = 'SUCCESS';
        step.duration = `${duration_ms}ms`;
        step.summary = summary || step.summary;
      }
    });

    eventSource.addEventListener('workflow_paused', (_e: MessageEvent) => {
      workflowPaused.value = true;
      isProcessing.value = false;
      eventSource.close();
    });

    eventSource.addEventListener('workflow_complete', (e: MessageEvent) => {
      const { result } = JSON.parse(e.data);
      aiResult.value = result;
      replyDraft.value = result.reply_draft || '';
      isProcessing.value = false;
      eventSource.close();
    });

    eventSource.addEventListener('error', () => {
      isProcessing.value = false;
      eventSource.close();
    });
  }

  async function confirmAction(ticketId: string, approved: boolean) {
    await ticketApi.confirmAction(ticketId, approved);
    workflowPaused.value = false;
    // Resume SSE after confirmation — the backend will resume the pipeline
    await startAiProcess(ticketId);
  }

  async function closeTicket(ticketId: string, finalReply: string) {
    await ticketApi.close(ticketId, finalReply);
    // Refresh ticket status
    const updated = await ticketApi.get(ticketId);
    const index = tickets.value.findIndex(t => t.id === ticketId);
    if (index >= 0) tickets.value[index] = updated;
  }

  function resetState() {
    isProcessing.value = false;
    aiResult.value = null;
    traceSteps.value = [];
    replyDraft.value = '';
    workflowPaused.value = false;
  }

  return {
    tickets, selectedTicketId, isProcessing, aiResult, traceSteps, replyDraft, workflowPaused,
    selectedTicket, openCount, closedCount,
    fetchTickets, selectTicket, startAiProcess, confirmAction, closeTicket, resetState,
  };
});
