"""API request and response schemas."""

from pydantic import Field

from .agent_trace import TraceStep
from .ai_result import AiProcessResult, ApiModel


class CreateTicketRequest(ApiModel):
    id: str | None = None
    no: str | None = None
    title: str
    customer_name: str
    phone: str
    card_last4: str
    scene: str
    risk_label: str = "低风险"
    risk_level: str = "low"
    content: str


class TicketResponse(ApiModel):
    id: str
    no: str
    title: str
    customer_name: str
    phone: str
    card_last4: str
    scene: str
    created_at: str
    risk_label: str
    risk_level: str
    status: str
    content: str


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
