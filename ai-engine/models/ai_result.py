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


class AiProcessResult(ApiModel):
    workflow_name: str = ""
    risk_decision: str = ""
    intent: Optional[IntentResult] = None
    fields: list[FieldResult] = Field(default_factory=list)
    tool_evidence: str = ""
    tool_name: str = ""
    tool_request: dict = Field(default_factory=dict)
    tool_response: dict = Field(default_factory=dict)
    verify_checks: list[VerifyCheck] = Field(default_factory=list)
    reply_draft: str = ""
    requires_human_review: bool = True
    missing_fields: list[str] = Field(default_factory=list)
    failure_reason: str = ""
