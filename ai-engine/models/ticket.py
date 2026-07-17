"""Ticket model — mirrors the core business entity."""

from enum import Enum
from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TicketStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    PENDING_HUMAN_CONFIRM = "pending_human_confirm"
    PENDING_HUMAN_REVIEW = "pending_human_review"
    ESCALATED = "escalated"
    CLOSED = "closed"


class Ticket(BaseModel):
    id: str                                    # "coupon" | "address" | "dispute"
    no: str                                    # "T20260715001"
    title: str
    customer_name: str
    phone: str
    card_last4: str
    scene: str                                 # "补发优惠券" | "资料修改" | "交易核查"
    created_at: str                            # "2026-07-15 09:12"
    risk_label: str                            # "低风险" display text
    risk_level: RiskLevel
    status: TicketStatus = TicketStatus.OPEN
    content: str                               # Full ticket text

    class Config:
        use_enum_values = True
