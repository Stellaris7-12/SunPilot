"""Runtime context for one orchestrated ticket-processing pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Awaitable, Callable, Any

from models.ticket import Ticket
from orchestrator.trace import TraceCollector

PushFn = Callable[[str, dict], Awaitable[None]]


@dataclass
class PipelineContext:
    """Shared runtime state for the current Orchestrator run."""

    ticket_id: str
    trace: TraceCollector
    push: PushFn
    overall_start: float
    confirmed: bool = False
    workflow_config: dict[str, Any] = field(default_factory=dict)
    ticket: Ticket | None = None
    ticket_context: str = ""
    intent_result: dict[str, Any] = field(default_factory=dict)
    extract_result: dict[str, Any] = field(default_factory=dict)
    verify_result: dict[str, Any] = field(default_factory=dict)
    tool_result: Any = None
    tool_params: dict[str, Any] = field(default_factory=dict)
    available_tool_names: list[str] = field(default_factory=list)
