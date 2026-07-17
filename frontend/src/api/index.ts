import axios from 'axios';
import type { Ticket, AiProcessResult, TraceStep, AgentCard, ToolDefinition, ToolResult, EvaluationMetrics } from '../types';

const api = axios.create({ baseURL: 'http://localhost:8000/api' });

export const ticketApi = {
  list: () => api.get<Ticket[]>('/tickets').then(r => r.data),
  get: (id: string) => api.get<Ticket>(`/tickets/${id}`).then(r => r.data),
  aiProcess: (id: string) => api.post<{ticket_id: string; status: string; result: AiProcessResult; trace: TraceStep[]}>(`/tickets/${id}/ai-process`).then(r => r.data),
  getStreamUrl: (id: string) => `http://localhost:8000/api/tickets/${id}/ai-process-stream`,
  confirmAction: (id: string, approved: boolean) => api.post(`/tickets/${id}/confirm-action`, { ticket_id: id, approved }).then(r => r.data),
  close: (id: string, finalReply: string) => api.post<{ticket_id: string; final_reply: string}>(`/tickets/${id}/close`, { ticket_id: id, final_reply: finalReply }).then(r => r.data),
  getTrace: (id: string) => api.get<TraceStep[]>(`/tickets/${id}/trace`).then(r => r.data),
  getAiResult: (id: string) => api.get<AiProcessResult>(`/tickets/${id}/ai-result`).then(r => r.data),
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
