"""FastAPI application entry point — REST + SSE endpoints for the multi-agent system.

Run with: uvicorn main:app --reload --port 8000
"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from config import HOST, PORT, CORS_ORIGINS
from models.database import init_db, get_db
from models.ticket import Ticket, TicketStatus
from models.agent_card import AgentCard
from models.tool_schemas import ToolResult
from models.api_schemas import (
    ProcessTicketRequest, ProcessTicketResponse,
    ConfirmActionRequest, CloseTicketRequest,
    EvaluationMetrics,
)

from agents.agent_registry import agent_registry
from tools.registry import tool_registry
from tools.mock_executor import mock_executor
from tools.tool_router import router as tool_router
from orchestrator.state_machine import TicketStateMachine, TicketState
from orchestrator.trace import TraceCollector, TraceStatus
from orchestrator.orchestrator import orchestrator

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize DB and seed data on startup. Graceful shutdown on exit."""
    logger.info("Starting Credit Card Multi-Agent System...")
    await init_db()
    logger.info(f"Database initialized. {len(agent_registry.get_all())} agents registered.")

    # Track active SSE connections so we can cancel them on shutdown
    app.state.active_sse_tasks: set[asyncio.Task] = set()

    yield

    # Shutdown: cancel active SSE tasks with a short timeout
    logger.info("Shutting down — cancelling active SSE connections...")
    for task in list(app.state.active_sse_tasks):
        if not task.done():
            task.cancel()
    # Give tasks a brief moment to clean up
    await asyncio.sleep(0.5)
    logger.info("Shutdown complete.")


app = FastAPI(
    title="信用卡多Agent智能回单系统",
    description="Multi-Agent Credit Card Intelligent Collaborative Operation System",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount tool router
app.include_router(tool_router)

# ---------------------------------------------------------------------------
# Ticket endpoints
# ---------------------------------------------------------------------------

@app.get("/api/tickets")
async def list_tickets():
    """List all tickets."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM tickets ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
    return [
        {
            "id": r["id"], "no": r["no"], "title": r["title"],
            "customerName": r["customer_name"], "phone": r["phone"],
            "cardLast4": r["card_last4"], "scene": r["scene"],
            "createdAt": r["created_at"], "riskLabel": r["risk_label"],
            "riskLevel": r["risk_level"], "status": r["status"],
            "content": r["content"],
        }
        for r in rows
    ]


@app.get("/api/tickets/{ticket_id}")
async def get_ticket(ticket_id: str):
    """Get a single ticket by id."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM tickets WHERE id = ?", (ticket_id,)
        )
        row = await cursor.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return {
        "id": row["id"], "no": row["no"], "title": row["title"],
        "customerName": row["customer_name"], "phone": row["phone"],
        "cardLast4": row["card_last4"], "scene": row["scene"],
        "createdAt": row["created_at"], "riskLabel": row["risk_label"],
        "riskLevel": row["risk_level"], "status": row["status"],
        "content": row["content"],
    }


# ---------------------------------------------------------------------------
# AI Processing endpoints
# ---------------------------------------------------------------------------

@app.post("/api/tickets/{ticket_id}/ai-process")
async def trigger_ai_process(ticket_id: str):
    """Trigger AI processing (synchronous — returns full result)."""
    trace = TraceCollector(ticket_id)
    trace.start()

    result = await orchestrator.process_ticket(ticket_id, trace)

    # Persist trace
    await trace.persist()

    # Save AI result to DB
    async with get_db() as db:
        result_copy = {
            k: v for k, v in result.items()
            if not k.startswith("_")
        }
        await db.execute(
            "INSERT INTO ai_results (ticket_id, result_json) VALUES (?, ?)",
            (ticket_id, json.dumps(result_copy, ensure_ascii=False)),
        )
        await db.commit()

    return ProcessTicketResponse(
        ticket_id=ticket_id,
        status=result.get("_status", "unknown"),
        result=result_copy if "_total_duration_ms" not in result else None,
        trace=[
            {
                "agent": s.agent, "agentId": s.agent_id,
                "summary": s.summary, "duration": s.duration,
                "status": s.status.value,
            }
            for s in trace.steps
        ],
    ).model_dump()


@app.get("/api/tickets/{ticket_id}/ai-process-stream")
async def trigger_ai_process_stream(ticket_id: str):
    """Trigger AI processing with SSE streaming — events pushed in real-time via asyncio.Queue."""
    trace = TraceCollector(ticket_id)
    trace.start()
    event_queue: asyncio.Queue = asyncio.Queue()

    async def event_generator() -> AsyncGenerator[str, None]:
        # Track this task for graceful shutdown
        current_task = asyncio.current_task()
        if current_task:
            app.state.active_sse_tasks.add(current_task)

        # Launch orchestrator as background task
        pipeline_task = asyncio.create_task(
            orchestrator.process_ticket(ticket_id, trace, event_queue)
        )

        try:
            while True:
                # Wait for next event with a timeout to check if task died
                try:
                    event = await asyncio.wait_for(event_queue.get(), timeout=0.5)
                except asyncio.TimeoutError:
                    if pipeline_task.done():
                        # Task finished — check for remaining events
                        while not event_queue.empty():
                            event = event_queue.get_nowait()
                            yield f"event: {event['event']}\ndata: {json.dumps(event['data'], ensure_ascii=False)}\n\n"
                        break
                    continue

                # Yield the SSE event immediately
                yield f"event: {event['event']}\ndata: {json.dumps(event['data'], ensure_ascii=False)}\n\n"

                # If workflow is done, break after yielding the event
                if event["event"] in ("workflow_complete", "workflow_paused"):
                    break

            # Wait for task to finish and get result
            result = await pipeline_task

            # Persist trace + result
            await trace.persist()
            result_copy = {k: v for k, v in result.items() if not k.startswith("_")}
            status = result.get("_status", "")
            if status != TicketState.PENDING_HUMAN_CONFIRM.value:
                async with get_db() as db:
                    await db.execute(
                        "INSERT INTO ai_results (ticket_id, result_json) VALUES (?, ?)",
                        (ticket_id, json.dumps(result_copy, ensure_ascii=False)),
                    )
                    await db.commit()

        except asyncio.CancelledError:
            logger.info(f"SSE connection cancelled for ticket {ticket_id}")
        except Exception as e:
            logger.exception(f"SSE stream error for ticket {ticket_id}")
            yield f"event: error\ndata: {json.dumps({'agent_id': 'orchestrator', 'message': str(e), 'code': type(e).__name__})}\n\n"
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


# ---------------------------------------------------------------------------
# Human-in-the-Loop endpoints
# ---------------------------------------------------------------------------

@app.post("/api/tickets/{ticket_id}/confirm-action")
async def confirm_action(ticket_id: str, body: ConfirmActionRequest):
    """Human confirms or rejects a paused tool execution."""
    if body.approved:
        # Resume the pipeline — re-run from tool step
        trace = TraceCollector(ticket_id)
        trace.start()
        result = await orchestrator.process_ticket(ticket_id, trace)
        await trace.persist()
        return {"ticket_id": ticket_id, "status": result.get("_status", "unknown")}
    else:
        # Reject → escalate
        async with get_db() as db:
            await db.execute(
                "UPDATE tickets SET status = ? WHERE id = ?",
                (TicketState.ESCALATED.value, ticket_id),
            )
            await db.commit()
        return {"ticket_id": ticket_id, "status": TicketState.ESCALATED.value}


@app.post("/api/tickets/{ticket_id}/close")
async def close_ticket(ticket_id: str, body: CloseTicketRequest):
    """Human final review — close the ticket."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM tickets WHERE id = ?", (ticket_id,)
        )
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

    logger.info(f"Ticket {ticket_id} closed. Final reply: {body.final_reply[:50]}...")
    return {"ticket_id": ticket_id, "status": TicketState.CLOSED.value}


# ---------------------------------------------------------------------------
# Trace and result history
# ---------------------------------------------------------------------------

@app.get("/api/tickets/{ticket_id}/trace")
async def get_trace(ticket_id: str):
    """Get trace history for a ticket."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM trace_steps WHERE ticket_id = ? ORDER BY created_at DESC LIMIT 10",
            (ticket_id,),
        )
        rows = await cursor.fetchall()
    return [
        {
            "agent": r["agent"], "agentId": r["agent_id"],
            "summary": r["summary"], "duration": r["duration"],
            "status": r["status"],
        }
        for r in rows
    ]


@app.get("/api/tickets/{ticket_id}/ai-result")
async def get_ai_result(ticket_id: str):
    """Get the latest AI result for a ticket."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT result_json FROM ai_results WHERE ticket_id = ? ORDER BY created_at DESC LIMIT 1",
            (ticket_id,),
        )
        row = await cursor.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="No AI result found")
    return json.loads(row["result_json"])


# ---------------------------------------------------------------------------
# Agent Cards
# ---------------------------------------------------------------------------

@app.get("/api/agent-cards")
async def list_agent_cards():
    """List all registered agent cards."""
    cards = agent_registry.get_all()
    return [c.model_dump() for c in cards]


# ---------------------------------------------------------------------------
# Evaluation (P1)
# ---------------------------------------------------------------------------

@app.get("/api/evaluation/metrics")
async def get_evaluation_metrics():
    """Get evaluation metrics (hardcoded demo values)."""
    return EvaluationMetrics(
        intent_accuracy=0.92,
        field_completeness=0.86,
        tool_correctness=0.95,
        avg_time_saved_seconds=78.0,
        total_samples=15,
    ).model_dump()


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
