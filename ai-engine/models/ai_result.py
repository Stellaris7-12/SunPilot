"""AI Process Result — the complete output of the 5-agent pipeline."""

from pydantic import BaseModel, Field
from typing import Optional


class IntentResult(BaseModel):
    """Result from IntentAgent."""
    type: str                                   # "COUPON_REISSUE" | "CUSTOMER_ADDRESS_UPDATE" | "TRANSACTION_DISPUTE" | "UNKNOWN"
    label: str                                  # "补发优惠券/权益"
    confidence: float                           # 0.93
    workflow_name: str = ""                     # "coupon_reissue_flow"
    reason: str = ""                            # Brief reasoning


class FieldResult(BaseModel):
    """A single extracted field."""
    label: str                                  # "客户号"
    name: str                                   # "customerId"
    value: str                                  # "C10001"


class VerifyCheck(BaseModel):
    """A single verification check result."""
    label: str                                  # "必填字段完整"
    status: str                                 # "通过" | "待确认" | "需复核" | "已拦截"


class AiProcessResult(BaseModel):
    """The complete AI processing result for a ticket.

    This is the main data contract between the backend orchestrator
    and the frontend. It contains the full chain of agent outputs:
    Intent -> Extract -> (Tool) -> Verify -> Reply.
    """
    workflow_name: str = ""                     # "coupon_reissue_flow"
    risk_decision: str = ""                     # "低风险，可人工确认结单"
    intent: Optional[IntentResult] = None
    fields: list[FieldResult] = []
    tool_evidence: str = ""                     # Human-readable tool execution summary
    tool_name: str = ""                         # Which tool was called
    tool_request: dict = {}                     # Params sent to tool
    tool_response: dict = {}                    # Tool response data
    verify_checks: list[VerifyCheck] = []       # List of verification checks
    reply_draft: str = ""                       # AI-generated reply draft
    requires_human_review: bool = True          # ALWAYS True — never auto-close
