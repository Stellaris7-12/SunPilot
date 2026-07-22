"""FastAPI application entry point."""

import asyncio
import json
import logging
import re
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from agents.agent_registry import agent_registry
from config import CALL_TRANSCRIPTS_JSON, CORS_ORIGINS, HOST, PORT
from evaluation.evaluator import evaluator
from models.ai_result import AiProcessResult
from models.api_schemas import (
    CloseTicketRequest,
    ConfirmActionRequest,
    CreateTicketRequest,
    DraftKeyField,
    EvaluationMetrics,
    GenerateTicketDraftRequest,
    GenerateTicketDraftResponse,
    PageTaskHint,
    AssignTicketRequest,
    CancelTicketRequest,
    ProcessTicketResponse,
    ReopenTicketRequest,
    SaveDraftRequest,
    TicketResponse,
    TicketOperationLogResponse,
    ToolCallLogResponse,
    UpdateTicketRequest,
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


def _operation_log_response(row) -> dict:
    return TicketOperationLogResponse(
        id=row["id"],
        ticket_id=row["ticket_id"],
        operation=row["operation"],
        operator=row["operator"],
        from_status=row["from_status"] or "",
        to_status=row["to_status"] or "",
        detail=json.loads(row["detail_json"] or "{}"),
        created_at=row["created_at"],
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


def _load_call_records() -> list[dict]:
    if not CALL_TRANSCRIPTS_JSON.exists():
        return []
    with CALL_TRANSCRIPTS_JSON.open("r", encoding="utf-8") as file:
        data = json.load(file)
    return data if isinstance(data, list) else []


def _compact_summary(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    customer_lines = [line for line in lines if line.startswith("客户")]
    basis = customer_lines or lines
    summary = "；".join(line.split("：", 1)[-1] for line in basis[:3])
    return summary[:180] or "已读取通话记录，等待坐席补充关键信息。"


def _first_match(pattern: str, text: str) -> str:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _detect_call_scenario(text: str) -> tuple[str, str, str, str]:
    if re.search(r"优惠券|满减|券|活动达标|DINING|MALL_CASHBACK", text, re.I):
        return "优惠券补发", "权益与活动", "优惠券补发", "COUPON_REISSUE"
    if re.search(r"贵宾厅|权益|机场|积分|兑换|AIRPORT|POINT", text, re.I):
        return "权益资格查询", "权益与活动", "权益查询", "BENEFIT_QUERY"
    if re.search(r"申请进度|申请单|APP\d+", text, re.I):
        return "申请进度查询", "申请与账务", "信用卡申请", "APPLICATION_PROGRESS_QUERY"
    if re.search(r"地址|手机|资料|联系人|变更", text, re.I):
        return "资料变更", "客户资料", "资料变更", "CUSTOMER_INFO_UPDATE"
    if re.search(r"交易|流水|入账|盗刷|非本人|TXN\d+", text, re.I):
        return "交易查询", "交易与风险", "交易核查", "TRANSACTION_QUERY"
    return "人工客服发单", "综合服务", "待分类", "CALL_INTAKE"


def _build_key_fields(draft: dict, expected: dict | None = None) -> list[DraftKeyField]:
    source_fields = expected.get("keyFields", {}) if expected else {}
    fields = {
        "customerId": draft.get("customerId") or source_fields.get("customerId") or "",
        "customerName": draft.get("customerName") or "",
        "cardLast4": draft.get("cardLast4") or "",
        "scene": draft.get("scene") or "",
    }
    for key, value in source_fields.items():
        if key not in fields:
            fields[key] = str(value)
    labels = {
        "customerId": "客户号",
        "customerName": "客户姓名",
        "cardLast4": "卡尾号",
        "scene": "业务场景",
        "couponType": "券类型",
        "benefitCode": "权益编码",
        "applicationNo": "申请单号",
        "transactionId": "交易流水",
        "field": "变更字段",
        "newValue": "变更内容",
    }
    return [
        DraftKeyField(name=name, label=labels.get(name, name), value=str(value), source="通话文本")
        for name, value in fields.items()
        if str(value).strip()
    ]


def _missing_draft_fields(draft: dict) -> list[str]:
    required = {
        "title": "标题",
        "customerName": "客户姓名",
        "phone": "预留手机",
        "cardLast4": "卡尾号",
        "scene": "业务场景",
        "content": "发单内容",
    }
    return [label for key, label in required.items() if not str(draft.get(key) or "").strip()]


def _build_page_task_hints(draft: dict, missing_fields: list[str]) -> list[PageTaskHint]:
    hints = [
        PageTaskHint(action="open", target="call-intake-workspace", label="打开通话发单工作区"),
    ]
    field_labels = {
        "title": "标题",
        "customerId": "客户号",
        "customerName": "客户姓名",
        "phone": "预留手机",
        "cardLast4": "卡尾号",
        "scene": "业务场景",
        "category": "业务大类",
        "subcategory": "业务小类",
        "priority": "优先级",
        "riskLabel": "风险标签",
        "riskLevel": "风险等级",
        "content": "发单内容",
    }
    for field, label in field_labels.items():
        hints.append(PageTaskHint(
            action="fill",
            target=f"draft-{field}",
            label=f"填写{label}",
            field=field,
            value=str(draft.get(field) or ""),
            source="CallIntakeAgent",
            required=label in missing_fields,
        ))
    hints.append(PageTaskHint(
        action="submit" if not missing_fields else "stop",
        target="draft-submit",
        label="字段完整，提交标准工单" if not missing_fields else "字段不足，等待人工补充",
        source="TicketAgent Policy Layer",
        required=not missing_fields,
    ))
    return hints


def _draft_from_transcript(transcript: str, call_meta: dict | None = None) -> tuple[dict, str, str, list[DraftKeyField]]:
    meta = call_meta or {}
    customer_id = meta.get("customerId") or meta.get("customer_id") or _first_match(r"(C\d{5,})", transcript)
    card_last4 = meta.get("cardLast4") or meta.get("card_last4") or _first_match(r"卡尾(?:号)?\s*(\d{4})", transcript)
    phone = meta.get("phone") or _first_match(r"(1\d{2}\*{4}\d{4}|1\d{10})", transcript) or "待补充"
    customer_name = meta.get("customerName") or meta.get("customer_name") or "待补充客户"
    scene, category, subcategory, ticket_type = _detect_call_scenario(transcript)
    business_code = (
        _first_match(r"((?:DINING|COFFEE|AIRPORT|HOTEL|POINT|MALL|CONCIERGE)[A-Z0-9_]*\d*)", transcript)
        or _first_match(r"((?:TXN|APP)\d{6,})", transcript)
    )
    summary = _compact_summary(transcript)
    title = f"{scene} - {customer_id or customer_name or '待补充客户'}"
    if scene == "优惠券补发":
        title = "活动达标未收到优惠券"
    elif scene == "交易查询":
        title = "交易入账/争议核查"
    draft = {
        "title": title,
        "customerId": customer_id,
        "customerName": customer_name,
        "phone": phone,
        "cardLast4": card_last4 or "待补充",
        "scene": scene,
        "category": category,
        "subcategory": subcategory,
        "priority": "normal",
        "channel": meta.get("channel") or "客服热线发单",
        "assignee": meta.get("agent") or "坐席 A1027",
        "department": "信用卡运营组",
        "riskLabel": "中风险" if scene == "资料变更" else "低风险",
        "riskLevel": "medium" if scene == "资料变更" else "low",
        "content": f"{summary}。{('关键业务编号：' + business_code + '。') if business_code else ''}原始通话已由发单 Agent 摘要，创建后进入标准多 Agent 工单处理链路。",
    }
    key_fields = _build_key_fields(draft)
    return draft, summary, ticket_type, key_fields


@app.get("/api/call-records")
async def list_call_records():
    records = _load_call_records()
    return [
        {
            "id": item.get("id", ""),
            "source": item.get("source", ""),
            "scenario": item.get("scenario", ""),
            "riskLevel": item.get("riskLevel", "low"),
            "callMeta": item.get("callMeta", {}),
            "transcript": item.get("transcript", ""),
        }
        for item in records
    ]


@app.post("/api/call-records/generate-ticket-draft")
async def generate_ticket_draft(body: GenerateTicketDraftRequest):
    sample = None
    if body.sample_id:
        sample = next((item for item in _load_call_records() if item.get("id") == body.sample_id), None)
        if sample is None:
            raise HTTPException(status_code=404, detail="Call sample not found")

    if sample:
        draft = dict(sample.get("ticketDraft") or {})
        transcript = sample.get("transcript") or body.transcript
        call_meta = sample.get("callMeta") or {}
        summary = _compact_summary(transcript)
        detected_type = (sample.get("expected") or {}).get("intentType") or sample.get("scenario") or "CALL_INTAKE"
        key_fields = _build_key_fields(draft, sample.get("expected"))
        confidence = 0.96
        source_call_id = sample.get("id", "")
    else:
        transcript = body.transcript.strip()
        if not transcript:
            raise HTTPException(status_code=400, detail="transcript or sampleId is required")
        call_meta = body.call_meta.model_dump(by_alias=True) if body.call_meta else {}
        draft, summary, detected_type, key_fields = _draft_from_transcript(transcript, call_meta)
        confidence = 0.78 if "待补充" not in json.dumps(draft, ensure_ascii=False) else 0.58
        source_call_id = ""

    draft.setdefault("customerId", call_meta.get("customerId") or "")
    draft.setdefault("assignee", call_meta.get("agent") or body.operator_id or "坐席 A1027")
    draft.setdefault("department", "信用卡运营组")
    draft.setdefault("channel", call_meta.get("channel") or "客服热线发单")
    missing_fields = _missing_draft_fields(draft)
    response = GenerateTicketDraftResponse(
        ticket_draft=CreateTicketRequest(**draft),
        call_summary=summary,
        detected_scenario=draft.get("scene", ""),
        detected_ticket_type=detected_type,
        key_fields=key_fields,
        missing_fields=missing_fields,
        confidence=confidence,
        source_call_id=source_call_id,
        page_task_hints=_build_page_task_hints(draft, missing_fields),
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
