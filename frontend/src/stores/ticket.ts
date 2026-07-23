import { defineStore } from 'pinia';
import { computed, ref } from 'vue';
import type { AiProcessResult, CallRecordSample, CreateTicketPayload, GenerateTicketDraftPayload, PageActionLogEntry, PageActionLogPayload, PageActionLogRecord, PageActionStatus, RiskLevel, Ticket, TicketDraftResult, TicketListFilters, TicketOperationLog, ToolCallLog, TraceStep, UpdateTicketPayload } from '../types';
import { ticketApi } from '../api';

export const useTicketStore = defineStore('ticket', () => {
  const tickets = ref<Ticket[]>([]);
  const selectedTicketId = ref<string | null>(null);
  const isProcessing = ref(false);
  const aiResult = ref<AiProcessResult | null>(null);
  const traceSteps = ref<TraceStep[]>([]);
  const toolCalls = ref<ToolCallLog[]>([]);
  const operationLogs = ref<TicketOperationLog[]>([]);
  const callRecords = ref<CallRecordSample[]>([]);
  const ticketDraftResult = ref<TicketDraftResult | null>(null);
  const pageActionLogs = ref<PageActionLogEntry[]>([]);
  const pageAgentStatus = ref<PageActionStatus>('done');
  const pageAgentGoal = ref('');
  const replyDraft = ref('');
  const workflowPaused = ref(false);

  const selectedTicket = computed(() =>
    tickets.value.find(t => t.id === selectedTicketId.value) || null
  );
  const openCount = computed(() => tickets.value.filter(t => t.status !== 'closed').length);
  const closedCount = computed(() => tickets.value.filter(t => t.status === 'closed').length);

  async function fetchTickets(filters?: TicketListFilters) {
    tickets.value = await ticketApi.list(filters);
  }

  async function fetchCallRecords() {
    callRecords.value = await ticketApi.listCallRecords();
  }

  async function generateTicketDraft(payload: GenerateTicketDraftPayload) {
    ticketDraftResult.value = await ticketApi.generateTicketDraft(payload);
    return ticketDraftResult.value;
  }

  function setPageAgentStatus(status: PageActionStatus, goal = pageAgentGoal.value) {
    pageAgentStatus.value = status;
    pageAgentGoal.value = goal;
  }

  function appendPageActionLog(entry: PageActionLogEntry) {
    pageActionLogs.value.unshift(entry);
    pageActionLogs.value = pageActionLogs.value.slice(0, 60);
  }

  function clearPageActionLogs() {
    pageActionLogs.value = [];
  }

  async function recordPageActionLog(payload: PageActionLogPayload) {
    const saved = await ticketApi.recordPageActionLog(payload);
    appendPageActionLog(pageActionRecordToEntry(saved));
    return saved;
  }

  function selectTicket(id: string) {
    selectedTicketId.value = id;
    resetState();
  }

  function clearSelectedTicket() {
    selectedTicketId.value = null;
    resetState();
  }

  async function loadTicketContext(id: string) {
    selectedTicketId.value = id;
    resetState();
    const [resultResponse, traceResponse, toolCallsResponse, operationsResponse, pageActionLogsResponse] = await Promise.allSettled([
      ticketApi.getAiResult(id),
      ticketApi.getTrace(id),
      ticketApi.getToolCalls(id),
      ticketApi.getOperations(id),
      ticketApi.getPageActionLogs(id),
    ]);
    if (resultResponse.status === 'fulfilled') {
      applyProcessResult(resultResponse.value);
    }
    if (traceResponse.status === 'fulfilled') {
      traceSteps.value = traceResponse.value;
    }
    if (toolCallsResponse.status === 'fulfilled') {
      toolCalls.value = toolCallsResponse.value;
    }
    if (operationsResponse.status === 'fulfilled') {
      operationLogs.value = operationsResponse.value;
    }
    if (pageActionLogsResponse.status === 'fulfilled') {
      pageActionLogs.value = pageActionLogsResponse.value.map(pageActionRecordToEntry);
    }
  }

  function applyProcessResult(result: AiProcessResult | null | undefined) {
    if (!result) return;
    aiResult.value = result;
    replyDraft.value = result.notification?.standardReply?.body || result.replyDraft || '';
  }

  async function refreshTicket(ticketId: string) {
    const updated = await ticketApi.get(ticketId);
    const index = tickets.value.findIndex(t => t.id === ticketId);
    if (index >= 0) tickets.value[index] = updated;
  }

  async function startAiProcess(ticketId: string) {
    isProcessing.value = true;
    aiResult.value = null;
    traceSteps.value = [];
    toolCalls.value = [];
    replyDraft.value = '';
    workflowPaused.value = false;

    const eventSource = new EventSource(ticketApi.getStreamUrl(ticketId));

    eventSource.addEventListener('agent_start', (e: MessageEvent) => {
      const { agent_id, agent_name } = JSON.parse(e.data);
      traceSteps.value.push({
        agent: agent_name,
        agentId: agent_id,
        summary: '执行中...',
        duration: '等待返回',
        status: 'RUNNING',
      });
    });

    eventSource.addEventListener('agent_thinking', (e: MessageEvent) => {
      const { agent_id, message } = JSON.parse(e.data);
      const step = traceSteps.value.find(s => s.agentId === agent_id && s.status === 'RUNNING');
      if (step) step.summary = message;
    });

    eventSource.addEventListener('agent_complete', (e: MessageEvent) => {
      const { agent_id, summary, duration_ms, status } = JSON.parse(e.data);
      const step = traceSteps.value.find(s => s.agentId === agent_id && s.status === 'RUNNING');
      if (step) {
        step.status = status || 'SUCCESS';
        step.duration = `${duration_ms}ms`;
        step.summary = summary || step.summary;
      }
    });

    const finish = async (e: MessageEvent, paused = false) => {
      const payload = JSON.parse(e.data);
      const { result } = payload;
      applyProcessResult(result);
      workflowPaused.value = paused && payload.pauseType === 'human_confirm';
      isProcessing.value = false;
      eventSource.close();
      await refreshTicket(ticketId);
      try {
        toolCalls.value = await ticketApi.getToolCalls(ticketId);
      } catch {
        toolCalls.value = [];
      }
    };

    eventSource.addEventListener('workflow_paused', e => finish(e as MessageEvent, true));
    eventSource.addEventListener('workflow_complete', e => finish(e as MessageEvent));
    eventSource.addEventListener('workflow_escalated', e => finish(e as MessageEvent));
    eventSource.addEventListener('workflow_failed', e => finish(e as MessageEvent));

    eventSource.addEventListener('error', () => {
      isProcessing.value = false;
      eventSource.close();
    });
  }

  async function confirmAction(ticketId: string, approved: boolean) {
    const response = await ticketApi.confirmAction(ticketId, approved);
    workflowPaused.value = false;
    if ('result' in response) {
      applyProcessResult(response.result);
      traceSteps.value = response.trace || traceSteps.value;
    }
    await refreshTicket(ticketId);
    try {
      toolCalls.value = await ticketApi.getToolCalls(ticketId);
    } catch {
      toolCalls.value = [];
    }
  }

  async function closeTicket(ticketId: string, finalReply: string) {
    await ticketApi.close(ticketId, finalReply);
    await refreshTicket(ticketId);
  }

  async function updateTicket(ticketId: string, payload: UpdateTicketPayload) {
    const updated = await ticketApi.update(ticketId, payload);
    upsertTicket(updated);
  }

  async function createTicket(payload: CreateTicketPayload) {
    const created = await ticketApi.create(payload);
    upsertTicket(created);
    selectedTicketId.value = created.id;
    return created;
  }

  async function assignTicket(ticketId: string, assignee: string, department?: string, operator?: string) {
    const updated = await ticketApi.assign(ticketId, assignee, department, operator);
    upsertTicket(updated);
    operationLogs.value = await ticketApi.getOperations(ticketId);
  }

  async function cancelTicket(ticketId: string, reason: string, operator?: string) {
    const updated = await ticketApi.cancel(ticketId, reason, operator);
    upsertTicket(updated);
    operationLogs.value = await ticketApi.getOperations(ticketId);
  }

  async function reopenTicket(ticketId: string, reason = '', operator?: string) {
    const updated = await ticketApi.reopen(ticketId, reason, operator);
    upsertTicket(updated);
    operationLogs.value = await ticketApi.getOperations(ticketId);
  }

  async function saveReplyDraft(ticketId: string, draft: string, operator?: string) {
    await ticketApi.saveDraft(ticketId, draft, operator);
    replyDraft.value = draft;
    operationLogs.value = await ticketApi.getOperations(ticketId);
  }

  function upsertTicket(updated: Ticket) {
    const index = tickets.value.findIndex(t => t.id === updated.id);
    if (index >= 0) tickets.value[index] = updated;
    else tickets.value.unshift(updated);
  }

  function resetState() {
    isProcessing.value = false;
    aiResult.value = null;
    traceSteps.value = [];
    toolCalls.value = [];
    operationLogs.value = [];
    pageActionLogs.value = [];
    replyDraft.value = '';
    workflowPaused.value = false;
  }

  return {
    tickets,
    selectedTicketId,
    isProcessing,
    aiResult,
    traceSteps,
    toolCalls,
    operationLogs,
    callRecords,
    ticketDraftResult,
    pageActionLogs,
    pageAgentStatus,
    pageAgentGoal,
    replyDraft,
    workflowPaused,
    selectedTicket,
    openCount,
    closedCount,
    fetchTickets,
    fetchCallRecords,
    generateTicketDraft,
    setPageAgentStatus,
    appendPageActionLog,
    recordPageActionLog,
    clearPageActionLogs,
    selectTicket,
    clearSelectedTicket,
    loadTicketContext,
    startAiProcess,
    confirmAction,
    closeTicket,
    createTicket,
    updateTicket,
    assignTicket,
    cancelTicket,
    reopenTicket,
    saveReplyDraft,
    resetState,
  };
});

function pageActionRecordToEntry(record: PageActionLogRecord): PageActionLogEntry {
  return {
    id: String(record.id),
    planId: record.taskId,
    instruction: record.actionKind,
    contextSummary: record.resultSummary,
    tool: record.toolName || record.actionKind,
    target: record.target,
    inputSummary: summarizeRecord(record.input),
    status: normalizePageActionStatus(record.status),
    result: record.resultSummary,
    durationMs: record.durationMs,
    riskLevel: normalizeRiskLevel(record.riskLevel),
    stopReason: record.stopReason,
    createdAt: record.createdAt,
  };
}

function summarizeRecord(value: Record<string, unknown>) {
  const text = JSON.stringify(value || {});
  return text.length > 120 ? `${text.slice(0, 120)}...` : text;
}

function normalizePageActionStatus(status: string): PageActionStatus {
  if (['thinking', 'executing', 'executed', 'retrying', 'error', 'done', 'stopped'].includes(status)) {
    return status as PageActionStatus;
  }
  return status === 'success' ? 'executed' : status === 'failed' ? 'error' : 'done';
}

function normalizeRiskLevel(value: string): RiskLevel {
  return value === 'medium' || value === 'high' ? value : 'low';
}
