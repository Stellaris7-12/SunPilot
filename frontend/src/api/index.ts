import axios from 'axios';
import type { Ticket, AiProcessResult, TraceStep, AgentCard, ToolDefinition, ToolResult, ToolCallLog, EvaluationMetrics, ProcessTicketResponse, TicketListFilters, TicketOperationLog, UpdateTicketPayload, CreateTicketPayload } from '../types';

const api = axios.create({ baseURL: 'http://localhost:8000/api' });

export const ticketApi = {
  list: (filters?: TicketListFilters) => api.get<Ticket[]>('/tickets', { params: filters }).then(r => r.data),
  get: (id: string) => api.get<Ticket>(`/tickets/${id}`).then(r => r.data),
  create: (payload: CreateTicketPayload) => api.post<Ticket>('/tickets', payload).then(r => r.data),
  update: (id: string, payload: UpdateTicketPayload) => api.patch<Ticket>(`/tickets/${id}`, payload).then(r => r.data),
  assign: (id: string, assignee: string, department?: string, operator = 'operator') => api.post<Ticket>(`/tickets/${id}/assign`, { assignee, department, operator }).then(r => r.data),
  cancel: (id: string, reason: string, operator = 'operator') => api.post<Ticket>(`/tickets/${id}/cancel`, { reason, operator }).then(r => r.data),
  reopen: (id: string, reason = '', operator = 'operator') => api.post<Ticket>(`/tickets/${id}/reopen`, { reason, operator }).then(r => r.data),
  saveDraft: (id: string, draft: string, operator = 'operator') => api.post<{ticketId: string; status: string}>(`/tickets/${id}/reply-draft`, { draft, operator }).then(r => r.data),
  aiProcess: (id: string) => api.post<ProcessTicketResponse>(`/tickets/${id}/ai-process`).then(r => r.data),
  getStreamUrl: (id: string) => `http://localhost:8000/api/tickets/${id}/ai-process-stream`,
  confirmAction: (id: string, approved: boolean) => api.post<ProcessTicketResponse | {ticketId: string; status: string}>(`/tickets/${id}/confirm-action`, { ticketId: id, approved }).then(r => r.data),
  close: (id: string, finalReply: string) => api.post<{ticketId: string; status: string}>(`/tickets/${id}/close`, { ticketId: id, finalReply }).then(r => r.data),
  getTrace: (id: string) => api.get<TraceStep[]>(`/tickets/${id}/trace`).then(r => r.data),
  getAiResult: (id: string) => api.get<AiProcessResult>(`/tickets/${id}/ai-result`).then(r => r.data),
  getToolCalls: (id: string) => api.get<ToolCallLog[]>(`/tickets/${id}/tool-calls`).then(r => r.data),
  getOperations: (id: string) => api.get<TicketOperationLog[]>(`/tickets/${id}/operations`).then(r => r.data),
};

export const agentApi = {
  listCards: () => api.get<AgentCard[]>('/agent-cards').then(r => r.data),
};

export const toolApi = {
  list: () => api.get<ToolDefinition[]>('/tools').then(r => r.data),
  execute: (name: string, params: Record<string, unknown>) => api.post<ToolResult>(`/tools/${name}/execute`, params).then(r => r.data),
};

export const evalApi = {
  metrics: () => api.get<EvaluationMetrics>('/evaluation/metrics').then(r => r.data),
};
