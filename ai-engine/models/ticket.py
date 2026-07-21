"""Core ticket model."""

from enum import Enum

from pydantic import BaseModel


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TicketStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    PENDING_INFO = "pending_info"
    PENDING_HUMAN_CONFIRM = "pending_human_confirm"
    PENDING_HUMAN_REVIEW = "pending_human_review"
    ESCALATED = "escalated"
    FAILED = "failed"
    CLOSED = "closed"


class Ticket(BaseModel):
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
    risk_level: RiskLevel
    status: TicketStatus = TicketStatus.OPEN
    content: str
    closed_at: str = ""
    final_reply: str = ""
    cancel_reason: str = ""

    class Config:
        use_enum_values = True
