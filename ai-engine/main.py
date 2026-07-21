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
from evaluation.evaluator import evaluator
from models.ai_result import AiProcessResult
from models.api_schemas import (
    CloseTicketRequest,
    ConfirmActionRequest,
    CreateTicketRequest,
    EvaluationMetrics,
    ProcessTicketResponse,
    TicketResponse,
    ToolCallLogResponse,
)
from models.database import init_db
from models.repositories import (
    ai_result_repository,
    ticket_repository,
    tool_call_repository,
    trace_repository,
)
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
    row = dict(row)
    return TicketResponse(
        id=row["id"],
        no=row["no"],
        title=row["title"],
        customer_id=row.get("customer_id") or "",
        customer_name=row["customer_name"],
        phone=row["phone"],
        card_last4=row["card_last4"],
        scene=row["scene"],
        category=row.get("category") or "",
        subcategory=row.get("subcategory") or "",
        priority=row.get("priority") or "normal",
        channel=row.get("channel") or "",
        assignee=row.get("assignee") or "",
        department=row.get("department") or "",
        created_at=row["created_at"],
        due_at=row.get("due_at") or "",
        updated_at=row.get("updated_at") or "",
        risk_label=row["risk_label"],
        risk_level=row["risk_level"],
        status=row["status"],
        content=row["content"],
        closed_at=row.get("closed_at") or "",
        final_reply=row.get("final_reply") or "",
        cancel_reason=row.get("cancel_reason") or "",
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
    public_result = _public_result(result)
    await ai_result_repository.insert_ai_result(ticket_id, trace, result, public_result)


@app.get("/api/tickets")
async def list_tickets():
    rows = await ticket_repository.list_tickets()
    return [_ticket_response(row) for row in rows]


@app.post("/api/tickets")
async def create_ticket(body: CreateTicketRequest):
    ticket_id = body.id or f"ticket_{uuid.uuid4().hex[:8]}"
    ticket_no = body.no or f"T{datetime.now().strftime('%Y%m%d%H%M%S')}"
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        row = await ticket_repository.create_ticket({
            "id": ticket_id,
            "no": ticket_no,
            "title": body.title,
            "customer_id": body.customer_id,
            "customer_name": body.customer_name,
            "phone": body.phone,
            "card_last4": body.card_last4,
            "scene": body.scene,
            "category": body.category,
            "subcategory": body.subcategory,
            "priority": body.priority,
            "channel": body.channel,
            "assignee": body.assignee,
            "department": body.department,
            "created_at": created_at,
            "due_at": body.due_at,
            "risk_label": body.risk_label,
            "risk_level": body.risk_level,
            "status": TicketState.OPEN.value,
            "content": body.content,
        })
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _ticket_response(row)


@app.get("/api/tickets/{ticket_id}")
async def get_ticket(ticket_id: str):
    row = await ticket_repository.get_ticket(ticket_id)
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
    row = await ticket_repository.get_ticket(ticket_id)
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
                reply_draft="已记录人工复核意见。该工单已转人工处理，后续将由业务人员继续跟进。",
                notification={
                    "standardReply": {
                        "title": "升级回单",
                        "body": "已记录人工复核意见。该工单已转人工处理，后续将由业务人员继续跟进。",
                        "status": "escalated",
                        "evidenceIds": [],
                        "nextOwner": "human",
                    },
                    "internalNotice": {
                        "title": "内部通知",
                        "body": reason,
                        "status": "escalated",
                        "evidenceIds": [],
                        "nextOwner": "human",
                    },
                    "reviewSummary": {
                        "reason": reason,
                        "riskDecision": reason,
                        "missingFields": [],
                        "toolEvidenceIds": [],
                        "suggestedAction": "人工接管该工单，复核客户诉求和拒绝原因后处理。",
                    },
                    "closureSuggestion": {
                        "canClose": False,
                        "reason": "人工已拒绝自动执行，当前工单需人工处理，不建议直接结案。",
                        "finalReply": "已记录人工复核意见。该工单已转人工处理，后续将由业务人员继续跟进。",
                        "requiresHumanReview": True,
                    },
                    "followUp": {
                        "enabled": False,
                        "template": "",
                        "triggerStatus": "",
                    },
                },
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
        await ticket_repository.update_status(
            ticket_id,
            TicketState.ESCALATED.value,
            operation="reject_human_confirm",
            detail={"reason": reason},
        )
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
    row = await ticket_repository.get_ticket(ticket_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Ticket not found")

    current_status = row["status"]
    if not TicketStateMachine.can_transition(current_status, TicketState.CLOSED.value):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot close ticket in status '{current_status}'",
        )

    await ticket_repository.close_ticket(ticket_id, body.final_reply)

    logger.info("Ticket %s closed. Final reply: %s...", ticket_id, body.final_reply[:50])
    return {"ticketId": ticket_id, "status": TicketState.CLOSED.value}


@app.get("/api/tickets/{ticket_id}/trace")
async def get_trace(ticket_id: str):
    rows = await trace_repository.list_recent_trace(ticket_id, limit=10)
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
    result_json = await ai_result_repository.get_latest_result_json(ticket_id)
    if result_json is None:
        raise HTTPException(status_code=404, detail="No AI result found")
    return json.loads(result_json)


@app.get("/api/tickets/{ticket_id}/tool-calls")
async def get_tool_calls(ticket_id: str):
    rows = await tool_call_repository.list_tool_calls(ticket_id)
    return [
        ToolCallLogResponse(
            id=row["id"],
            ticket_id=row["ticket_id"],
            tool_name=row["tool_name"],
            request=json.loads(row["request_json"] or "{}"),
            response=json.loads(row["response_json"] or "{}"),
            evidence_id=row["evidence_id"] or "",
            success=bool(row["success"]),
            duration_ms=row["duration_ms"],
            failure_reason=row["failure_reason"] or "",
            created_at=row["created_at"],
        ).model_dump(by_alias=True)
        for row in rows
    ]


@app.get("/api/agent-cards")
async def list_agent_cards():
    return [card.model_dump(by_alias=True) for card in agent_registry.get_all()]


@app.get("/api/evaluation/metrics")
async def get_evaluation_metrics():
    metrics = evaluator.compute()
    return EvaluationMetrics(
        intent_accuracy=metrics.intent_accuracy,
        field_completeness=metrics.field_completeness,
        tool_correctness=metrics.tool_correctness,
        avg_time_saved_seconds=metrics.avg_time_saved_seconds,
        total_samples=metrics.total_samples,
        agents=metrics.agents,
        closed_loop_success_rate=metrics.closed_loop_success_rate,
        avg_processing_ms=metrics.avg_processing_ms,
        evaluated_samples=metrics.evaluated_samples,
        avg_manual_steps_saved=metrics.avg_manual_steps_saved,
        source=metrics.source,
    ).model_dump(by_alias=True)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
