"""SSE Bridge — generates Server-Sent Events from orchestrator execution.

Exposes an async generator that yields SSE-formatted strings as the
orchestrator processes a ticket. The frontend consumes these via
EventSource to render the real-time Agent Trace timeline.
"""

import json
import logging
import time
from typing import AsyncGenerator

from orchestrator.trace import TraceCollector, TraceStatus
from orchestrator.state_machine import TicketState

logger = logging.getLogger(__name__)

# SSE event format: "event: {name}\ndata: {json}\n\n"


def _format_sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


class SSEBridge:
    """Wraps orchestrator execution and yields SSE events.

    Usage in FastAPI:
        bridge = SSEBridge()
        return StreamingResponse(
            bridge.stream(ticket_id),
            media_type="text/event-stream"
        )
    """

    def __init__(self):
        self._trace: TraceCollector | None = None

    def set_trace(self, trace: TraceCollector):
        """Bind the trace collector for this execution."""
        self._trace = trace

    def emit_agent_start(self, agent_id: str, agent_name: str):
        """Emit an agent_start event."""
        return _format_sse("agent_start", {
            "agent_id": agent_id,
            "agent_name": agent_name,
            "timestamp": time.time(),
        })

    def emit_agent_thinking(self, agent_id: str, message: str):
        """Emit an agent_thinking event (progress update)."""
        return _format_sse("agent_thinking", {
            "agent_id": agent_id,
            "message": message,
        })

    def emit_agent_complete(
        self, agent_id: str, summary: str, duration_ms: int, result: dict | None = None
    ):
        """Emit an agent_complete event with result and timing."""
        return _format_sse("agent_complete", {
            "agent_id": agent_id,
            "summary": summary,
            "duration_ms": duration_ms,
            "result": result,
        })

    def emit_workflow_paused(self, reason: str, ticket_id: str):
        """Emit a workflow_paused event (waiting for human confirmation)."""
        return _format_sse("workflow_paused", {
            "reason": reason,
            "ticket_id": ticket_id,
        })

    def emit_workflow_complete(
        self, ticket_id: str, status: str, total_duration_ms: int, result: dict
    ):
        """Emit a workflow_complete event with final result."""
        return _format_sse("workflow_complete", {
            "ticket_id": ticket_id,
            "status": status,
            "total_duration_ms": total_duration_ms,
            "result": result,
        })

    def emit_error(self, agent_id: str, message: str, code: str = "UNKNOWN"):
        """Emit an error event."""
        return _format_sse("error", {
            "agent_id": agent_id,
            "message": message,
            "code": code,
        })

    async def stream(self, orchestrator_fn, ticket_id: str) -> AsyncGenerator[str, None]:
        """Async generator that executes the pipeline and yields SSE events.

        Args:
            orchestrator_fn: Async callable that takes (ticket_id, trace, sse_bridge)
                             and returns an AiProcessResult.
            ticket_id: The ticket to process.
        """
        try:
            yield self.emit_agent_start("orchestrator", "编排器")
            yield self.emit_agent_thinking("orchestrator", "正在启动多Agent协同处理...")

            result = await orchestrator_fn(ticket_id, self._trace, self)

            total_ms = result.get("_total_duration_ms", 0)
            status = result.get("_status", "pending_human_review")
            yield self.emit_workflow_complete(ticket_id, status, total_ms, result)

        except Exception as e:
            logger.exception(f"[SSEBridge] Pipeline error for ticket {ticket_id}")
            yield self.emit_error("orchestrator", str(e), type(e).__name__)
