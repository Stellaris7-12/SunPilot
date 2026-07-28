"""FastAPI application entry point."""

import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from ticket_agent.auth import verify_admin_key
from ticket_agent.agents.agent_registry import agent_registry
from ticket_agent.config import (
    CORS_ORIGINS,
    HOST,
    PORT,
)
from ticket_agent.models.schemas.ai_result import AiProcessResult
from ticket_agent.models.schemas.api_schemas import (
    CloseTicketRequest,
    ConfirmActionRequest,
    CreateTicketRequest,
    EvaluationMetrics,
    GenerateTicketDraftRequest,
    GenerateTicketDraftResponse,
    PageActionLogRequest,
    AssignTicketRequest,
    CancelTicketRequest,
    ProcessTicketResponse,
    ReopenTicketRequest,
    SaveDraftRequest,
    TicketResponse,
    ToolCallLogResponse,
    UpdateTicketRequest,
)
from ticket_agent.models.database import init_db
from ticket_agent.models.domain.workflow import WorkflowConfig
from ticket_agent.repositories.repositories import (
    agent_execution_log_repository,
    ai_result_repository,
    call_record_repository,
    page_action_log_repository,
    ticket_repository,
    ticket_draft_repository,
    tool_call_repository,
    trace_repository,
)
from ticket_agent.orchestrator.orchestrator import orchestrator
from ticket_agent.orchestrator.state_machine import TicketState, TicketStateMachine
from ticket_agent.orchestrator.trace import TraceCollector, TraceStatus
from ticket_agent.orchestrator.workflow_config import load_workflow_config
from ticket_agent.orchestrator.semantic_targets import load_semantic_targets
from ticket_agent.tools.registry import tool_registry
from ticket_agent.tools.tool_router import router as tool_router
from ticket_agent.api.routers.llm_proxy import router as llm_proxy_router

# 阶段1 重构：序列化器、LLM 代理客户端、通话发单业务逻辑已抽取到独立模块。
# 以下别名保持 main 的公开符号不变（smoke 脚本 import 依赖 + 路由体零改动）。
from ticket_agent.api.serializers import (
    agent_execution_response as _agent_execution_response,
    operation_log_response as _operation_log_response,
    page_action_log_response as _page_action_log_response,
    parse_json_object as _parse_json_object,
    public_result as _public_result,
    ticket_response as _ticket_response,
    trace_response as _trace_response,
)
from ticket_agent.domain.services.call_intake import (
    apply_dispatch_config as _apply_dispatch_config,
    build_key_fields as _build_key_fields,
    build_page_task_from_hints as _build_page_task_from_hints,
    build_page_task_hints as _build_page_task_hints,
    call_record_response as _call_record_response,
    compact_summary as _compact_summary,
    detect_call_scenario as _detect_call_scenario,
    draft_from_transcript as _draft_from_transcript,
    ensure_call_record_samples_persisted as _ensure_call_record_samples_persisted,
    missing_draft_fields as _missing_draft_fields,
    persist_ai_result as _persist_ai_result,
    row_raw_json as _row_raw_json,
    scenario_specific_fields as _scenario_specific_fields,
)

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
app.include_router(llm_proxy_router)


# P0 安全修复：删除危险的运行时配置修改端点
# 原端点允许无鉴权覆写进程级共享的 API key/model，存在成本滥用和配置投毒风险
# PageAgent LLM 配置现在只能通过环境变量 PAGE_AGENT_LLM_* 在部署时设置
# 如需运行时修改配置，需先实现完整的鉴权+审计机制


@app.get("/api/call-records")
async def list_call_records():
    await _ensure_call_record_samples_persisted()
    rows = await call_record_repository.list_call_records()
    return [_call_record_response(row) for row in rows]


@app.post("/api/call-records/generate-ticket-draft")
async def generate_ticket_draft(body: GenerateTicketDraftRequest):
    sample = None
    await _ensure_call_record_samples_persisted()
    if body.sample_id:
        sample_row = await call_record_repository.get_call_record(body.sample_id)
        sample = _row_raw_json(sample_row)
        if not sample:
            raise HTTPException(status_code=404, detail="Call sample not found")

    if sample:
        transcript = sample.get("transcript") or body.transcript
        call_meta = sample.get("callMeta") or {}
        sample_draft = dict(sample.get("ticketDraft") or {})
        # 历史/无草稿的通话记录 ticketDraft 可能为空或缺必填字段，
        # 先用通话文本合成一份完整草稿作为兜底，再用样本已有字段覆盖，
        # 避免空草稿直接进入 CreateTicketRequest 触发 500（“来电内容整理失败”）。
        base_draft, base_summary, base_type, _ = _draft_from_transcript(transcript, call_meta)
        draft = {**base_draft, **{k: v for k, v in sample_draft.items() if str(v or "").strip()}}
        draft = _apply_dispatch_config(draft, transcript, call_meta)
        summary = _compact_summary(transcript) or base_summary
        detected_type = draft.get("scene") or base_type or "UNKNOWN"
        key_fields = _build_key_fields(draft, sample.get("expected"))
        confidence = 0.96 if sample_draft else 0.82
        source_call_id = sample.get("id", "")
    else:
        transcript = body.transcript.strip()
        if not transcript:
            raise HTTPException(status_code=400, detail="transcript or sampleId is required")
        call_meta = body.call_meta.model_dump(by_alias=True) if body.call_meta else {}
        draft, summary, detected_type, key_fields = _draft_from_transcript(transcript, call_meta)
        confidence = 0.78 if "待补充" not in json.dumps(draft, ensure_ascii=False) else 0.58
        call_record = await call_record_repository.upsert_call_record({
            "id": f"call-{uuid.uuid4().hex[:8]}",
            "source": "manual_transcript",
            "scenario": detected_type,
            "riskLevel": draft.get("riskLevel", "low"),
            "callMeta": call_meta,
            "transcript": transcript,
            "status": "draft_generated",
        })
        source_call_id = call_record["id"]

    draft.setdefault("customerId", call_meta.get("customerId") or "")
    draft.setdefault("assignee", call_meta.get("agent") or body.operator_id or "坐席 A1027")
    draft.setdefault("department", "信用卡运营组")
    draft.setdefault("channel", call_meta.get("channel") or "客服热线发单")
    draft = _apply_dispatch_config(draft, transcript, call_meta)
    missing_fields = _missing_draft_fields(draft)
    page_task_hints = _build_page_task_hints(draft, missing_fields)
    page_task = _build_page_task_from_hints(draft, page_task_hints, missing_fields, source_call_id)
    response = GenerateTicketDraftResponse(
        ticket_draft=CreateTicketRequest(**draft),
        call_summary=summary,
        detected_scenario=draft.get("scene", ""),
        detected_ticket_type=detected_type,
        key_fields=key_fields,
        missing_fields=missing_fields,
        confidence=confidence,
        source_call_id=source_call_id,
        page_task_hints=page_task_hints,
        page_task=page_task,
    )
    await ticket_draft_repository.insert_ticket_draft(
        draft_id=page_task.id,
        call_record_id=source_call_id,
        draft=response.ticket_draft.model_dump(by_alias=True),
        page_task=page_task.model_dump(by_alias=True),
        page_task_hints=[hint.model_dump(by_alias=True) for hint in page_task_hints],
        confidence=confidence,
        detected_scenario=response.detected_scenario,
        detected_ticket_type=detected_type,
        missing_fields=missing_fields,
        key_fields=[field.model_dump(by_alias=True) for field in key_fields],
        created_by=body.operator_id or "system",
    )
    return response.model_dump(by_alias=True)


@app.get("/api/tickets")
async def list_tickets(
    ticket_no: str | None = Query(None, alias="ticketNo"),
    customer_id: str | None = Query(None, alias="customerId"),
    customer_name: str | None = Query(None, alias="customerName"),
    status: str | None = None,
    category: str | None = None,
    priority: str | None = None,
    risk_level: str | None = Query(None, alias="riskLevel"),
    assignee: str | None = None,
    channel: str | None = None,
    created_from: str | None = Query(None, alias="createdFrom"),
    created_to: str | None = Query(None, alias="createdTo"),
    sla_overdue: bool | None = Query(None, alias="slaOverdue"),
):
    rows = await ticket_repository.list_tickets({
        "ticket_no": ticket_no,
        "customer_id": customer_id,
        "customer_name": customer_name,
        "status": status,
        "category": category,
        "priority": priority,
        "risk_level": risk_level,
        "assignee": assignee,
        "channel": channel,
        "created_from": created_from,
        "created_to": created_to,
        "sla_overdue": sla_overdue,
    })
    return [_ticket_response(row) for row in rows]


@app.get("/api/workflow-config")
async def get_workflow_config():
    return WorkflowConfig.model_validate(load_workflow_config()).model_dump(by_alias=True)


@app.get("/api/semantic-targets")
async def get_semantic_targets():
    """P1-4: 暴露语义 target 配置给前端。

    返回 semantic_targets.json 的完整配置，供前端验证或动态加载。
    """
    semantic_config = load_semantic_targets()
    return {
        "version": semantic_config.version,
        "description": semantic_config.description,
        "scenes": {
            scene: [target.to_dict() for target in semantic_config.get_targets(scene)]
            for scene in ["call-intake", "ticket-reply", "evidence-review", "human-confirm"]
        },
    }


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
            "ext_json": body.ext_json,
            "order_prefix": body.order_prefix,
            "biz_type": body.biz_type,
            "biz_sub_type": body.biz_sub_type,
            "priority": body.priority,
            "channel": body.channel,
            "assignee": body.assignee,
            "department": body.department,
            "created_at": created_at,
            "due_at": body.due_at,
            "deadline": body.deadline,
            "risk_label": body.risk_label,
            "risk_level": body.risk_level,
            "receive_unit": body.receive_unit,
            "need_reply": body.need_reply,
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


@app.patch("/api/tickets/{ticket_id}")
async def update_ticket(ticket_id: str, body: UpdateTicketRequest):
    row = await ticket_repository.get_ticket(ticket_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    try:
        updated = await ticket_repository.update_ticket(
            ticket_id,
            body.model_dump(exclude={"operator"}, exclude_none=True),
            operator=body.operator,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _ticket_response(updated)


@app.post("/api/tickets/{ticket_id}/assign")
async def assign_ticket(ticket_id: str, body: AssignTicketRequest):
    row = await ticket_repository.get_ticket(ticket_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    try:
        updated = await ticket_repository.assign_ticket(
            ticket_id,
            body.assignee,
            body.department,
            operator=body.operator,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _ticket_response(updated)


@app.post("/api/tickets/{ticket_id}/cancel")
async def cancel_ticket(ticket_id: str, body: CancelTicketRequest):
    row = await ticket_repository.get_ticket(ticket_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    try:
        updated = await ticket_repository.cancel_ticket(ticket_id, body.reason, operator=body.operator)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _ticket_response(updated)


@app.post("/api/tickets/{ticket_id}/reopen")
async def reopen_ticket(ticket_id: str, body: ReopenTicketRequest):
    row = await ticket_repository.get_ticket(ticket_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    try:
        updated = await ticket_repository.reopen_ticket(ticket_id, body.reason, operator=body.operator)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _ticket_response(updated)


@app.post("/api/tickets/{ticket_id}/reply-draft")
async def save_reply_draft(ticket_id: str, body: SaveDraftRequest):
    row = await ticket_repository.get_ticket(ticket_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    try:
        await ticket_repository.save_reply_draft(ticket_id, body.draft, operator=body.operator)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ticketId": ticket_id, "status": row["status"]}


@app.get("/api/tickets/{ticket_id}/operations")
async def get_ticket_operations(ticket_id: str):
    row = await ticket_repository.get_ticket(ticket_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    rows = await ticket_repository.list_operation_logs(ticket_id)
    return [_operation_log_response(item) for item in rows]


@app.post("/api/page-action-logs")
async def create_page_action_log(body: PageActionLogRequest):
    row = await page_action_log_repository.insert_page_action_log(
        body.model_dump(by_alias=True)
    )
    return _page_action_log_response(row)


@app.get("/api/tickets/{ticket_id}/page-action-logs")
async def get_page_action_logs(ticket_id: str, limit: int = Query(50, ge=1, le=200)):
    rows = await page_action_log_repository.list_page_action_logs(ticket_id, limit=limit)
    return [_page_action_log_response(row) for row in rows]


@app.get("/api/tickets/{ticket_id}/agent-executions")
async def get_agent_executions(ticket_id: str, limit: int = Query(20, ge=1, le=100)):
    row = await ticket_repository.get_ticket(ticket_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    rows = await agent_execution_log_repository.list_agent_executions(ticket_id, limit=limit)
    return [_agent_execution_response(item) for item in rows]


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
    """Close ticket (requires human review in frontend).

    P0-2 Note: Authentication temporarily removed to unblock frontend.
    TODO: Implement session-based authentication for operator identity.
    """
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
    from evaluation.evaluator import evaluator  # 延迟导入避免循环依赖
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


@app.post("/api/config/reload")
async def reload_config(auth: None = Depends(verify_admin_key)):
    """P2-12: 配置热加载端点（管理员专用）。

    重新加载 workflow_config.json，无需重启服务。
    失败时保留旧配置，返回 500 错误。

    Requires X-API-Key header with valid admin key.
    """
    from ticket_agent.orchestrator.workflow_config import reload_workflow_config

    try:
        new_config = reload_workflow_config()
        scenario_count = len(new_config.get("scenarios", {}))
        return {
            "success": True,
            "message": f"配置已重新加载，当前包含 {scenario_count} 个场景",
            "scenarios": list(new_config.get("scenarios", {}).keys()),
        }
    except Exception as exc:
        logger.error("Failed to reload config: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"配置重新加载失败，保留旧配置: {str(exc)}"
        ) from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
