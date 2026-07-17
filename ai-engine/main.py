"""FastAPI application entry point."""

import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from agents.agent_registry import agent_registry
from config import CORS_ORIGINS, HOST, PORT
from models.ai_result import AiProcessResult
from models.api_schemas import (
    CloseTicketRequest,
    ConfirmActionRequest,
    CreateTicketRequest,
    EvaluationMetrics,
    ProcessTicketResponse,
    TicketResponse,
)
from models.database import get_db, init_db
from orchestrator.orchestrator import orchestrator
from orchestrator.state_machine import TicketState, TicketStateMachine
from orchestrator.trace import TraceCollector, TraceStatus
from tools.registry import tool_registry
from tools.tool_router import router as tool_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Credit Card Multi-Agent System...")
    await init_db()
    logger.info("Database initialized. %s agents registered.", len(agent_registry.get_all()))

    app.state.active_sse_tasks: set[asyncio.Task] = set()
    yield

    logger.info("Shutting down; cancelling active SSE connections...")
    for task in list(app.state.active_sse_tasks):
        if not task.done():
            task.cancel()
    await asyncio.sleep(0.5)
    logger.info("Shutdown complete.")


app = FastAPI(
    title="信用卡多Agent智能回单系统",
    description="Multi-Agent Credit Card Intelligent Collaborative Operation System",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tool_router)


def _ticket_response(row) -> dict:
    return TicketResponse(
        id=row["id"],
        no=row["no"],
        title=row["title"],
        customer_name=row["customer_name"],
        phone=row["phone"],
        card_last4=row["card_last4"],
        scene=row["scene"],
        created_at=row["created_at"],
        risk_label=row["risk_label"],
        risk_level=row["risk_level"],
        status=row["status"],
        content=row["content"],
    ).model_dump(by_alias=True)


def _trace_response(trace: TraceCollector) -> list[dict]:
    return [
        {
            "agent": step.agent,
            "agent_id": step.agent_id,
            "summary": step.summary,
            "duration": step.duration,
            "status": step.status.value,
            "result": step.result,
        }
        for step in trace.steps
    ]


def _public_result(result: dict) -> dict:
    return orchestrator.public_result(result)


async def _persist_ai_result(ticket_id: str, trace: TraceCollector, result: dict):
    result_copy = {k: v for k, v in result.items() if not k.startswith("_")}
    public_result = _public_result(result)
    intent = result_copy.get("intent") or {}
    async with get_db() as db:
        await db.execute(
            """INSERT INTO ai_results
               (ticket_id, run_id, status, result_json, workflow_name,
                intent_type, intent_label, intent_confidence, extracted_fields_json,
                tool_name, tool_request_json, tool_response_json, evidence_id,
                reply_draft, requires_human_review, duration_ms, failure_reason)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                ticket_id,
                trace.run_id,
                result.get("_status", ""),
                json.dumps(public_result, ensure_ascii=False),
                result_copy.get("workflow_name", ""),
                intent.get("type", ""),
                intent.get("label", ""),
                intent.get("confidence", 0.0),
                json.dumps(result_copy.get("fields", []), ensure_ascii=False),
                result_copy.get("tool_name", ""),
                json.dumps(result_copy.get("tool_request", {}), ensure_ascii=False),
                json.dumps(result_copy.get("tool_response", {}), ensure_ascii=False),
                (result_copy.get("tool_response", {}) or {}).get("evidenceId", ""),
                result_copy.get("reply_draft", ""),
                1 if result_copy.get("requires_human_review", True) else 0,
                result.get("_total_duration_ms", 0),
                result.get("_failure_reason", "") or result_copy.get("failure_reason", ""),
            ),
        )
        await db.commit()


@app.get("/api/tickets")
async def list_tickets():
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM tickets ORDER BY created_at DESC")
        rows = await cursor.fetchall()
    return [_ticket_response(row) for row in rows]


@app.post("/api/tickets")
async def create_ticket(body: CreateTicketRequest):
    ticket_id = body.id or f"ticket_{uuid.uuid4().hex[:8]}"
    ticket_no = body.no or f"T{datetime.now().strftime('%Y%m%d%H%M%S')}"
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    async with get_db() as db:
        try:
            await db.execute(
                """INSERT INTO tickets
                   (id, no, title, customer_name, phone, card_last4, scene,
                    created_at, risk_label, risk_level, status, content)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    ticket_id,
                    ticket_no,
                    body.title,
                    body.customer_name,
                    body.phone,
                    body.card_last4,
                    body.scene,
                    created_at,
                    body.risk_label,
                    body.risk_level,
                    TicketState.OPEN.value,
                    body.content,
                ),
            )
            await db.commit()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        cursor = await db.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        row = await cursor.fetchone()
    return _ticket_response(row)


@app.get("/api/tickets/{ticket_id}")
async def get_ticket(ticket_id: str):
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        row = await cursor.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return _ticket_response(row)


@app.post("/api/tickets/{ticket_id}/ai-process")
async def trigger_ai_process(ticket_id: str):
    trace = TraceCollector(ticket_id)
    trace.start()

    result = await orchestrator.process_ticket(ticket_id, trace)
    await trace.persist()
    await _persist_ai_result(ticket_id, trace, result)

    response = ProcessTicketResponse(
        ticket_id=ticket_id,
        status=result.get("_status", "unknown"),
        result=AiProcessResult(**{k: v for k, v in result.items() if not k.startswith("_")}),
        trace=_trace_response(trace),
        total_duration_ms=result.get("_total_duration_ms", 0),
        terminal_event=result.get("_terminal_event", ""),
        pause_type=result.get("_pause_type"),
        failure_reason=result.get("_failure_reason", ""),
    )
    return response.model_dump(by_alias=True)


@app.get("/api/tickets/{ticket_id}/ai-process-stream")
async def trigger_ai_process_stream(ticket_id: str):
    trace = TraceCollector(ticket_id)
    trace.start()
    event_queue: asyncio.Queue = asyncio.Queue()

    async def event_generator() -> AsyncGenerator[str, None]:
        current_task = asyncio.current_task()
        if current_task:
            app.state.active_sse_tasks.add(current_task)

        pipeline_task = asyncio.create_task(
            orchestrator.process_ticket(ticket_id, trace, event_queue)
        )
        terminal_events = {
            "workflow_complete",
            "workflow_paused",
            "workflow_escalated",
            "workflow_failed",
        }

        persisted = False

        try:
            while True:
                try:
                    event = await asyncio.wait_for(event_queue.get(), timeout=0.5)
                except asyncio.TimeoutError:
                    if pipeline_task.done():
                        while not event_queue.empty():
                            event = event_queue.get_nowait()
                            if event["event"] in terminal_events and not persisted:
                                result = await pipeline_task
                                await trace.persist()
                                await _persist_ai_result(ticket_id, trace, result)
                                persisted = True
                            yield _sse(event["event"], event["data"])
                        break
                    continue

                if event["event"] in terminal_events:
                    result = await pipeline_task
                    await trace.persist()
                    await _persist_ai_result(ticket_id, trace, result)
                    persisted = True
                    yield _sse(event["event"], event["data"])
                    break
                yield _sse(event["event"], event["data"])

        except asyncio.CancelledError:
            logger.info("SSE connection cancelled for ticket %s", ticket_id)
        except Exception as exc:
            logger.exception("SSE stream error for ticket %s", ticket_id)
            yield _sse("workflow_failed", {
                "agent_id": "orchestrator",
                "message": str(exc),
                "code": type(exc).__name__,
                "status": TicketState.FAILED.value,
            })
        finally:
            if current_task:
                app.state.active_sse_tasks.discard(current_task)
            if not pipeline_task.done():
                pipeline_task.cancel()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/api/tickets/{ticket_id}/confirm-action")
async def confirm_action(ticket_id: str, body: ConfirmActionRequest):
    async with get_db() as db:
        cursor = await db.execute("SELECT status FROM tickets WHERE id = ?", (ticket_id,))
        row = await cursor.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if not body.approved:
        if not TicketStateMachine.can_transition(row["status"], TicketState.ESCALATED.value):
            raise HTTPException(status_code=400, detail=f"Cannot reject ticket in status '{row['status']}'")
        trace = TraceCollector(ticket_id)
        trace.start()
        reason = "人工拒绝执行，已升级人工处理"
        trace.add_step(
            agent="人工确认",
            agent_id="human_confirm",
            summary=reason,
            duration="0ms",
            status=TraceStatus.SKIPPED,
        )
        result = {
            **AiProcessResult(
                workflow_name="manual_escalation_flow",
                risk_decision=reason,
                verify_checks=[{"label": "人工确认", "status": "已拒绝"}],
                requires_human_review=True,
                failure_reason=reason,
            ).model_dump(),
            "_status": TicketState.ESCALATED.value,
            "_total_duration_ms": 0,
            "_terminal_event": "workflow_escalated",
            "_pause_type": None,
            "_failure_reason": reason,
        }
        async with get_db() as db:
            await db.execute(
                "UPDATE tickets SET status = ? WHERE id = ?",
                (TicketState.ESCALATED.value, ticket_id),
            )
            await db.commit()
        await trace.persist()
        await _persist_ai_result(ticket_id, trace, result)
        response = ProcessTicketResponse(
            ticket_id=ticket_id,
            status=TicketState.ESCALATED.value,
            result=AiProcessResult(**{k: v for k, v in result.items() if not k.startswith("_")}),
            trace=_trace_response(trace),
            total_duration_ms=0,
            terminal_event="workflow_escalated",
            failure_reason=reason,
        )
        return response.model_dump(by_alias=True)

    if row["status"] != TicketState.PENDING_HUMAN_CONFIRM.value:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot confirm ticket in status '{row['status']}'",
        )

    trace = TraceCollector(ticket_id)
    trace.start()
    result = await orchestrator.process_ticket(ticket_id, trace, confirmed=True)
    await trace.persist()
    await _persist_ai_result(ticket_id, trace, result)
    response = ProcessTicketResponse(
        ticket_id=ticket_id,
        status=result.get("_status", "unknown"),
        result=AiProcessResult(**{k: v for k, v in result.items() if not k.startswith("_")}),
        trace=_trace_response(trace),
        total_duration_ms=result.get("_total_duration_ms", 0),
        terminal_event=result.get("_terminal_event", ""),
        pause_type=result.get("_pause_type"),
        failure_reason=result.get("_failure_reason", ""),
    )
    return response.model_dump(by_alias=True)


@app.post("/api/tickets/{ticket_id}/close")
async def close_ticket(ticket_id: str, body: CloseTicketRequest):
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        row = await cursor.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Ticket not found")

        current_status = row["status"]
        if not TicketStateMachine.can_transition(current_status, TicketState.CLOSED.value):
            raise HTTPException(
                status_code=400,
                detail=f"Cannot close ticket in status '{current_status}'",
            )

        await db.execute(
            "UPDATE tickets SET status = ? WHERE id = ?",
            (TicketState.CLOSED.value, ticket_id),
        )
        await db.commit()

    logger.info("Ticket %s closed. Final reply: %s...", ticket_id, body.final_reply[:50])
    return {"ticketId": ticket_id, "status": TicketState.CLOSED.value}


@app.get("/api/tickets/{ticket_id}/trace")
async def get_trace(ticket_id: str):
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM trace_steps WHERE ticket_id = ? ORDER BY created_at DESC LIMIT 10",
            (ticket_id,),
        )
        rows = await cursor.fetchall()
    return [
        {
            "agent": row["agent"],
            "agentId": row["agent_id"],
            "summary": row["summary"],
            "duration": row["duration"],
            "status": row["status"],
        }
        for row in rows
    ]


@app.get("/api/tickets/{ticket_id}/ai-result")
async def get_ai_result(ticket_id: str):
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT result_json FROM ai_results WHERE ticket_id = ? ORDER BY created_at DESC LIMIT 1",
            (ticket_id,),
        )
        row = await cursor.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="No AI result found")
    return json.loads(row["result_json"])


@app.get("/api/agent-cards")
async def list_agent_cards():
    return [card.model_dump(by_alias=True) for card in agent_registry.get_all()]


@app.get("/api/evaluation/metrics")
async def get_evaluation_metrics():
    return EvaluationMetrics(
        intent_accuracy=0.92,
        field_completeness=0.86,
        tool_correctness=0.95,
        avg_time_saved_seconds=78.0,
        total_samples=15,
    ).model_dump(by_alias=True)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
