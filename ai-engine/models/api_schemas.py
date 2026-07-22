"""API request and response schemas."""

from pydantic import Field

from .agent_trace import TraceStep
from .ai_result import AiProcessResult, ApiModel


class CreateTicketRequest(ApiModel):
    id: str | None = None
    no: str | None = None
    title: str
    customer_id: str = ""
    customer_name: str
    phone: str
    card_last4: str
    scene: str
    category: str = ""
    subcategory: str = ""
    priority: str = "normal"
    channel: str = ""
    assignee: str = ""
    department: str = ""
    due_at: str = ""
    risk_label: str = "低风险"
    risk_level: str = "low"
    content: str


class DraftKeyField(ApiModel):
    name: str
    label: str
    value: str
    source: str = "transcript"


class PageTaskHint(ApiModel):
    action: str
    target: str
    label: str
    field: str = ""
    value: str = ""
    source: str = ""
    required: bool = False


class CallMeta(ApiModel):
    customer_id: str = ""
    customer_name: str = ""
    phone: str = ""
    card_last4: str = ""
    channel: str = ""
    agent: str = ""
    call_started_at: str = ""


class GenerateTicketDraftRequest(ApiModel):
    transcript: str = ""
    call_meta: CallMeta | None = None
    sample_id: str | None = None
    operator_id: str | None = None


class GenerateTicketDraftResponse(ApiModel):
    ticket_draft: CreateTicketRequest
    call_summary: str
    detected_scenario: str
    detected_ticket_type: str
    key_fields: list[DraftKeyField] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    source_call_id: str = ""
    page_task_hints: list[PageTaskHint] = Field(default_factory=list)


class UpdateTicketRequest(ApiModel):
    title: str | None = None
    customer_id: str | None = None
    customer_name: str | None = None
    phone: str | None = None
    card_last4: str | None = None
    scene: str | None = None
    category: str | None = None
    subcategory: str | None = None
    priority: str | None = None
    channel: str | None = None
    assignee: str | None = None
    department: str | None = None
    due_at: str | None = None
    risk_label: str | None = None
    risk_level: str | None = None
    content: str | None = None
    operator: str = "operator"


class AssignTicketRequest(ApiModel):
    assignee: str
    department: str | None = None
    operator: str = "operator"


class CancelTicketRequest(ApiModel):
    reason: str
    operator: str = "operator"


class ReopenTicketRequest(ApiModel):
    reason: str = ""
    operator: str = "operator"


class SaveDraftRequest(ApiModel):
    draft: str
    operator: str = "operator"


class TicketResponse(ApiModel):
    id: str
    no: str
    title: str
    customer_id: str = ""
    customer_name: str
    phone: str
    card_last4: str
    scene: str
    category: str = ""
    subcategory: str = ""
    priority: str = "normal"
    channel: str = ""
    assignee: str = ""
    department: str = ""
    created_at: str
    due_at: str = ""
    updated_at: str = ""
    risk_label: str
    risk_level: str
    status: str
    content: str
    closed_at: str = ""
    final_reply: str = ""
    cancel_reason: str = ""


class ProcessTicketRequest(ApiModel):
    ticket_id: str


class ProcessTicketResponse(ApiModel):
    ticket_id: str
    status: str
    result: AiProcessResult | None = None
    trace: list[TraceStep] = Field(default_factory=list)
    total_duration_ms: int = 0
    terminal_event: str = ""
    pause_type: str | None = None
    failure_reason: str = ""


class ConfirmActionRequest(ApiModel):
    ticket_id: str
    approved: bool


class CloseTicketRequest(ApiModel):
    ticket_id: str
    final_reply: str


class ToolCallLogResponse(ApiModel):
    id: int
    ticket_id: str
    tool_name: str
    request: dict
    response: dict
    evidence_id: str = ""
    success: bool
    duration_ms: int
    failure_reason: str = ""
    created_at: str


class TicketOperationLogResponse(ApiModel):
    id: int
    ticket_id: str
    operation: str
    operator: str
    from_status: str = ""
    to_status: str = ""
    detail: dict = Field(default_factory=dict)
    created_at: str


class EvaluationMetrics(ApiModel):
    intent_accuracy: float
    field_completeness: float
    tool_correctness: float
    avg_time_saved_seconds: float
    total_samples: int = 15
    agents: dict = Field(default_factory=dict)
    closed_loop_success_rate: float = 0.0
    avg_processing_ms: float = 0.0
    evaluated_samples: int = 0
    avg_manual_steps_saved: float = 0.0
    source: str = "unknown"
