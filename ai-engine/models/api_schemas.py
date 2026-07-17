"""API request/response schemas."""

from pydantic import BaseModel, Field
from typing import Optional
from .agent_trace import TraceStep
from .ai_result import AiProcessResult


class ProcessTicketRequest(BaseModel):
    ticket_id: str


class ProcessTicketResponse(BaseModel):
    ticket_id: str
    status: str                                 # "completed" | "paused" | "escalated"
    result: Optional[AiProcessResult] = None
    trace: list[TraceStep] = []


class ConfirmActionRequest(BaseModel):
    ticket_id: str
    approved: bool                              # True = confirm, False = reject → escalate


class CloseTicketRequest(BaseModel):
    ticket_id: str
    final_reply: str                            # Human-edited final reply text


class EvaluationMetrics(BaseModel):
    intent_accuracy: float                      # 0.92
    field_completeness: float                   # 0.86
    tool_correctness: float                     # 0.95
    avg_time_saved_seconds: float               # 78.0
    total_samples: int = 15
