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
    customer_name: str
    phone: str
    card_last4: str
    scene: str
    created_at: str
    risk_label: str
    risk_level: RiskLevel
    status: TicketStatus = TicketStatus.OPEN
    content: str

    class Config:
        use_enum_values = True
