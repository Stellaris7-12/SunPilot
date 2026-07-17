"""SSE formatting helpers for orchestrator events."""

import json
import logging
import time
from typing import AsyncGenerator

from orchestrator.state_machine import TicketState

logger = logging.getLogger(__name__)


TERMINAL_EVENTS = {
    "workflow_complete",
    "workflow_paused",
    "workflow_escalated",
    "workflow_failed",
}


def format_sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


class SSEBridge:
    def emit_agent_start(self, agent_id: str, agent_name: str):
        return format_sse("agent_start", {
            "agent_id": agent_id,
            "agent_name": agent_name,
            "timestamp": time.time(),
        })

    def emit_agent_thinking(self, agent_id: str, message: str):
        return format_sse("agent_thinking", {
            "agent_id": agent_id,
            "message": message,
        })

    def emit_agent_complete(
        self,
        agent_id: str,
        summary: str,
        duration_ms: int,
        result: dict | None = None,
    ):
        return format_sse("agent_complete", {
            "agent_id": agent_id,
            "summary": summary,
            "duration_ms": duration_ms,
            "result": result,
        })

    def emit_terminal(
        self,
        ticket_id: str,
        status: str,
        total_duration_ms: int,
        result: dict | None = None,
        *,
        pause_type: str | None = None,
        failure_reason: str = "",
    ):
        event = terminal_event_for_status(status)
        data = {
            "ticketId": ticket_id,
            "status": status,
            "totalDurationMs": total_duration_ms,
            "result": result or {},
        }
        if pause_type:
            data["pauseType"] = pause_type
        if failure_reason:
            data["failureReason"] = failure_reason
        return format_sse(event, data)

    def emit_error(self, agent_id: str, message: str, code: str = "UNKNOWN"):
        return format_sse("workflow_failed", {
            "agent_id": agent_id,
            "message": message,
            "code": code,
            "status": TicketState.FAILED.value,
        })

    async def stream(self, orchestrator_fn, ticket_id: str) -> AsyncGenerator[str, None]:
        try:
            yield self.emit_agent_start("orchestrator", "编排器")
            yield self.emit_agent_thinking("orchestrator", "正在启动多Agent协同处理...")
            result = await orchestrator_fn(ticket_id)
            yield self.emit_terminal(
                ticket_id,
                result.get("_status", TicketState.PENDING_HUMAN_REVIEW.value),
                result.get("_total_duration_ms", 0),
                result,
                pause_type=result.get("_pause_type"),
                failure_reason=result.get("_failure_reason", ""),
            )
        except Exception as exc:
            logger.exception("[SSEBridge] Pipeline error for ticket %s", ticket_id)
            yield self.emit_error("orchestrator", str(exc), type(exc).__name__)


def terminal_event_for_status(status: str) -> str:
    if status in {TicketState.PENDING_INFO.value, TicketState.PENDING_HUMAN_CONFIRM.value}:
        return "workflow_paused"
    if status == TicketState.ESCALATED.value:
        return "workflow_escalated"
    if status == TicketState.FAILED.value:
        return "workflow_failed"
    return "workflow_complete"
