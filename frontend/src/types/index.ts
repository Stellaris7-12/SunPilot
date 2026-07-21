// Enums
export type RiskLevel = 'low' | 'medium' | 'high';
export type TicketStatus = 'open' | 'in_progress' | 'pending_info' | 'pending_human_confirm' | 'pending_human_review' | 'escalated' | 'failed' | 'closed';
export type TraceStatusEnum = 'RUNNING' | 'SUCCESS' | 'FAILED' | 'SKIPPED';

// Core models
export interface Ticket {
  id: string;
  no: string;
  title: string;
  customerId: string;
  customerName: string;
  phone: string;
  cardLast4: string;
  scene: string;
  category: string;
  subcategory: string;
  priority: 'low' | 'normal' | 'urgent' | 'critical';
  channel: string;
  assignee: string;
  department: string;
  createdAt: string;
  dueAt: string;
  updatedAt: string;
  riskLabel: string;
  riskLevel: RiskLevel;
  status: TicketStatus;
  content: string;
  closedAt: string;
  finalReply: string;
  cancelReason: string;
}

export interface AgentSkill {
  id: string;
  name: string;
  description: string;
  examples: string[];
}

export interface AgentCard {
  agentId: string;
  name: string;
  description: string;
  version: string;
  skills: AgentSkill[];
  inputSchema: Record<string, unknown>;
  outputSchema: Record<string, unknown>;
  requiresHumanReview: boolean;
  maxRiskLevel: string;
  timeoutSeconds: number;
  retryPolicy: string;
  dependencies: string[];
}

export interface TraceStep {
  agent: string;
  agentId: string;
  summary: string;
  duration: string;
  status: TraceStatusEnum;
  result?: Record<string, unknown>;
}

export interface IntentResult {
  type: string;
  label: string;
  confidence: number;
  workflowName: string;
  reason: string;
}

export interface FieldResult {
  label: string;
  name: string;
  value: string;
}

export interface VerifyCheck {
  label: string;
  status: string; // "通过" | "待确认" | "需复核" | "已拦截"
}

export type NotificationStatus = 'ready' | 'needs_info' | 'needs_review' | 'escalated' | 'closed' | 'failed';
export type NotificationOwner = 'customer' | 'agent' | 'human' | 'system';

export interface NotificationArtifact {
  title: string;
  body: string;
  status: NotificationStatus;
  evidenceIds: string[];
  nextOwner: NotificationOwner;
}

export interface ReviewSummary {
  reason: string;
  riskDecision: string;
  missingFields: string[];
  toolEvidenceIds: string[];
  suggestedAction: string;
}

export interface ClosureSuggestion {
  canClose: boolean;
  reason: string;
  finalReply: string;
  requiresHumanReview: boolean;
}

export interface FollowUpPlan {
  enabled: boolean;
  template: string;
  triggerStatus: string;
}

export interface NotificationBundle {
  standardReply: NotificationArtifact;
  internalNotice: NotificationArtifact;
  reviewSummary: ReviewSummary;
  closureSuggestion: ClosureSuggestion;
  followUp: FollowUpPlan;
}

export interface AiProcessResult {
  workflowName: string;
  riskDecision: string;
  intent: IntentResult | null;
  fields: FieldResult[];
  toolEvidence: string;
  toolName: string;
  toolRequest: Record<string, unknown>;
  toolResponse: Record<string, unknown>;
  verifyChecks: VerifyCheck[];
  replyDraft: string;
  notification?: NotificationBundle | null;
  requiresHumanReview: boolean;
  missingFields: string[];
  failureReason: string;
}

export interface ToolCallLog {
  id: number;
  ticketId: string;
  toolName: string;
  request: Record<string, unknown>;
  response: ToolResult;
  evidenceId: string;
  success: boolean;
  durationMs: number;
  failureReason: string;
  createdAt: string;
}

export interface ProcessTicketResponse {
  ticketId: string;
  status: TicketStatus | string;
  result: AiProcessResult | null;
  trace: TraceStep[];
  totalDurationMs: number;
  terminalEvent: string;
  pauseType?: 'missing_info' | 'human_confirm' | null;
  failureReason: string;
}

export interface ToolParameter {
  name: string;
  type: string;
  description: string;
  required: boolean;
  example: string;
}

export interface ToolDefinition {
  name: string;
  displayName: string;
  description: string;
  category: string;
  parameters: ToolParameter[];
  requiresConfirmation: boolean;
  riskLevel: string;
  mockEnabled: boolean;
  mockResponse: Record<string, unknown>;
  mockDelayMs: number;
}

export interface ToolResult {
  success: boolean;
  toolName: string;
  evidenceId: string;
  action: string;
  businessResult: string;
  nextStep: string;
  requiresHuman: boolean;
  failureReason: string;
  data: Record<string, unknown>;
  message: string;
  durationMs: number;
}

export interface EvaluationMetrics {
  intentAccuracy: number;
  fieldCompleteness: number;
  toolCorrectness: number;
  avgTimeSavedSeconds: number;
  totalSamples: number;
  agents?: Record<string, Record<string, { score: number; correct: number; total: number }>>;
  closedLoopSuccessRate?: number;
  avgProcessingMs?: number;
  evaluatedSamples?: number;
  avgManualStepsSaved?: number;
  source?: string;
}

export interface TicketContext {
  ticket: Ticket;
  aiResult: AiProcessResult | null;
  traceSteps: TraceStep[];
  toolCalls: ToolCallLog[];
  replyDraft: string;
  allowedActions: string[];
  disabledReasons: Record<string, string>;
}

export interface ReplyDraftState {
  body: string;
  source: 'agent' | 'operator' | 'empty';
  canSubmit: boolean;
}
