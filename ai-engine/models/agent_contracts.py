"""Typed contracts for payloads exchanged between business agents."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from models.ai_result import ApiModel, FieldResult, IntentResult, VerifyCheck
from models.ticket import Ticket


class AgentPayload(ApiModel):
    """Base class for Orchestrator-to-Agent payload DTOs."""

    def to_agent_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="python", by_alias=False, exclude_none=True)


class TicketContext(ApiModel):
    """Stable ticket snapshot passed through the agent pipeline."""

    id: str
    no: str
    title: str
    customer_id: str = ""
    customer_name: str = ""
    phone: str = ""
    card_last4: str = ""
    scene: str = ""
    category: str = ""
    subcategory: str = ""
    priority: str = "normal"
    channel: str = ""
    risk_label: str = ""
    risk_level: str = "low"
    status: str = ""
    content: str = ""

    @classmethod
    def from_ticket(cls, ticket: Ticket) -> "TicketContext":
        status = ticket.status.value if hasattr(ticket.status, "value") else str(ticket.status)
        return cls(
            id=ticket.id,
            no=ticket.no,
            title=ticket.title,
            customer_id=ticket.customer_id,
            customer_name=ticket.customer_name,
            phone=ticket.phone,
            card_last4=ticket.card_last4,
            scene=ticket.scene,
            category=ticket.category,
            subcategory=ticket.subcategory,
            priority=ticket.priority,
            channel=ticket.channel,
            risk_label=ticket.risk_label,
            risk_level=ticket.risk_level,
            status=status,
            content=ticket.content,
        )

    def to_summary_text(self) -> str:
        parts = [
            ("标题", self.title),
            ("场景", self.scene),
            ("类目", self.category),
            ("子类目", self.subcategory),
            ("客户号", self.customer_id),
            ("手机号", self.phone),
            ("卡尾号", self.card_last4),
            ("风险等级", self.risk_level),
            ("正文", self.content),
        ]
        return "\n".join(f"{label}: {value}" for label, value in parts if value)

    def to_resolution_ticket(self) -> dict[str, Any]:
        return self.model_dump(mode="python", by_alias=True)

    def to_risk_ticket(self) -> dict[str, Any]:
        return {
            "risk_level": self.risk_level,
            "risk_label": self.risk_label,
            "scene": self.scene,
        }

    def to_notification_ticket(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "no": self.no,
            "title": self.title,
            "customer_name": self.customer_name,
            "scene": self.scene,
            "risk_level": self.risk_level,
            "risk_label": self.risk_label,
        }


class IntakeResult(AgentPayload):
    fields: list[FieldResult] = Field(default_factory=list)
    field_enrichment: dict[str, Any] | None = Field(default=None, alias="_field_enrichment")


class RiskDecision(AgentPayload):
    checks: list[VerifyCheck] = Field(default_factory=list)
    risk_level: str = "low"
    risk_decision: str = ""
    can_auto_proceed: bool = True
    missing_fields: list[str] = Field(default_factory=list)
    needs_more_info: bool = False


class ToolPlan(AgentPayload):
    tool_name: str = ""
    tool_params: dict[str, Any] = Field(default_factory=dict)
    skip: bool = False
    skip_reason: str = ""
    available_tool_names: list[str] = Field(default_factory=list)


class ClassifierInput(AgentPayload):
    ticket_content: str
    workflow_config: dict[str, Any] = Field(default_factory=dict)


class IntakeInput(AgentPayload):
    ticket_content: str
    intent_type: str
    intent_label: str = ""
    workflow_config: dict[str, Any] = Field(default_factory=dict)


class EscalationInput(AgentPayload):
    ticket: dict[str, Any]
    intent: dict[str, Any]
    fields: list[dict[str, Any]] = Field(default_factory=list)
    tool_result: dict[str, Any] | None = None
    workflow_config: dict[str, Any] = Field(default_factory=dict)


class ResolutionInput(AgentPayload):
    intent: dict[str, Any]
    fields: list[dict[str, Any]] = Field(default_factory=list)
    ticket_content: str = ""
    ticket: dict[str, Any] = Field(default_factory=dict)
    available_tool_names: list[str] = Field(default_factory=list)
    available_tools: str = ""
    workflow_config: dict[str, Any] = Field(default_factory=dict)


class NotificationInput(AgentPayload):
    ticket: dict[str, Any]
    intent: dict[str, Any]
    fields: list[dict[str, Any]] = Field(default_factory=list)
    tool_result: dict[str, Any] | None = None
    tool_request: dict[str, Any] = Field(default_factory=dict)
    verify_result: dict[str, Any]
    workflow_config: dict[str, Any] = Field(default_factory=dict)
    status: str
    missing_fields: list[str] = Field(default_factory=list)
    failure_reason: str = ""
    pause_type: str | None = None


def coerce_intent_result(payload: dict[str, Any]) -> dict[str, Any]:
    return IntentResult(
        type=payload.get("type", "UNKNOWN"),
        label=payload.get("label", "未知"),
        confidence=float(payload.get("confidence", 0.0) or 0.0),
        workflow_name=payload.get("workflow_name", ""),
        reason=payload.get("reason", ""),
    ).model_dump()


def coerce_intake_result(payload: dict[str, Any]) -> dict[str, Any]:
    result = IntakeResult(**payload).to_agent_dict()
    enrichment = payload.get("_field_enrichment")
    if enrichment:
        result["_field_enrichment"] = enrichment
    return result


def coerce_risk_decision(payload: dict[str, Any]) -> dict[str, Any]:
    return RiskDecision(
        checks=payload.get("checks", []),
        risk_level=payload.get("risk_level", "low"),
        risk_decision=payload.get("risk_decision", ""),
        can_auto_proceed=bool(payload.get("can_auto_proceed", True)),
        missing_fields=payload.get("missing_fields", []),
        needs_more_info=bool(payload.get("needs_more_info", False)),
    ).to_agent_dict()


def coerce_tool_plan(payload: dict[str, Any]) -> dict[str, Any]:
    return ToolPlan(
        tool_name=payload.get("tool_name", ""),
        tool_params=payload.get("tool_params", {}) or {},
        skip=bool(payload.get("skip", False)),
        skip_reason=payload.get("skip_reason", ""),
        available_tool_names=payload.get("available_tool_names", []) or [],
    ).to_agent_dict()
