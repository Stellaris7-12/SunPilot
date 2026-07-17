"""Agent trace and SSE event models."""

from enum import Enum
from typing import Optional

from pydantic import Field

from .ai_result import ApiModel


class TraceStatus(str, Enum):
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class TraceStep(ApiModel):
    agent: str
    agent_id: str
    summary: str
    duration: str
    status: TraceStatus = TraceStatus.RUNNING
    result: Optional[dict] = None


class SSETraceEvent(ApiModel):
    event: str
    data: dict = Field(default_factory=dict)
