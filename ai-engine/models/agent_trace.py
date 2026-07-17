"""Agent Trace models — SSE event schemas and trace step tracking."""

from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional, Any


class TraceStatus(str, Enum):
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class TraceStep(BaseModel):
    """A single step in the agent execution trace timeline."""
    agent: str                                  # "意图识别Agent" — display name
    agent_id: str                               # "intent_agent" — machine-readable id
    summary: str                                # What this step did
    duration: str                               # "820ms"
    status: TraceStatus = TraceStatus.RUNNING
    result: Optional[dict] = None               # Optional: agent output data


class SSETraceEvent(BaseModel):
    """An event emitted over the SSE stream."""
    event: str                                  # "agent_start" | "agent_thinking" | "agent_complete" | ...
    data: dict                                  # Event-specific payload
