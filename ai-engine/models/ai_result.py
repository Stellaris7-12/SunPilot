"""AI processing result models.

Internal Python code may use snake_case field names. API responses use
camelCase aliases so the Vue frontend consumes one stable contract.
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


def to_camel(value: str) -> str:
    parts = value.split("_")
    return parts[0] + "".join(part.capitalize() for part in parts[1:])


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


class IntentResult(ApiModel):
    type: str
    label: str
    confidence: float
    workflow_name: str = ""
    reason: str = ""


class FieldResult(ApiModel):
    label: str
    name: str
    value: str


class VerifyCheck(ApiModel):
    label: str
    status: str


class FieldEnrichmentResult(ApiModel):
    filled_fields: dict = Field(default_factory=dict)
    unresolved_fields: list[str] = Field(default_factory=list)
    source_tools: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    conflicts: list[str] = Field(default_factory=list)
    requires_human_review: bool = False


class NotificationArtifact(ApiModel):
    title: str = ""
    body: str = ""
    status: str = "needs_review"
    evidence_ids: list[str] = Field(default_factory=list)
    next_owner: str = "human"


class ReviewSummary(ApiModel):
    reason: str = ""
    risk_decision: str = ""
    missing_fields: list[str] = Field(default_factory=list)
    tool_evidence_ids: list[str] = Field(default_factory=list)
    suggested_action: str = ""


class ClosureSuggestion(ApiModel):
    can_close: bool = False
    reason: str = ""
    final_reply: str = ""
    requires_human_review: bool = True


class FollowUpPlan(ApiModel):
    enabled: bool = False
    template: str = ""
    trigger_status: str = ""


class NotificationBundle(ApiModel):
    standard_reply: NotificationArtifact = Field(default_factory=NotificationArtifact)
    internal_notice: NotificationArtifact = Field(default_factory=NotificationArtifact)
    review_summary: ReviewSummary = Field(default_factory=ReviewSummary)
    closure_suggestion: ClosureSuggestion = Field(default_factory=ClosureSuggestion)
    follow_up: FollowUpPlan = Field(default_factory=FollowUpPlan)


class AiProcessResult(ApiModel):
    workflow_name: str = ""
    risk_decision: str = ""
    intent: Optional[IntentResult] = None
    fields: list[FieldResult] = Field(default_factory=list)
    tool_evidence: str = ""
    tool_name: str = ""
    tool_request: dict = Field(default_factory=dict)
    tool_response: dict = Field(default_factory=dict)
    field_enrichment: Optional[FieldEnrichmentResult] = None
    verify_checks: list[VerifyCheck] = Field(default_factory=list)
    reply_draft: str = ""
    notification: Optional[NotificationBundle] = None
    requires_human_review: bool = True
    missing_fields: list[str] = Field(default_factory=list)
    failure_reason: str = ""
