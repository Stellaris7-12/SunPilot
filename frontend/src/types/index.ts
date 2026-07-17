// Enums
export type RiskLevel = 'low' | 'medium' | 'high';
export type TicketStatus = 'open' | 'in_progress' | 'pending_info' | 'pending_human_confirm' | 'pending_human_review' | 'escalated' | 'failed' | 'closed';
export type TraceStatusEnum = 'RUNNING' | 'SUCCESS' | 'FAILED' | 'SKIPPED';

// Core models
export interface Ticket {
  id: string;
  no: string;
  title: string;
  customerName: string;
  phone: string;
  cardLast4: string;
  scene: string;
  createdAt: string;
  riskLabel: string;
  riskLevel: RiskLevel;
  status: TicketStatus;
  content: string;
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
}
