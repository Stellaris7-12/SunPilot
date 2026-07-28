"""Row/DTO → JSON response serializers shared across routers.

Pure transformation helpers. They map DB rows and internal objects onto the
Pydantic response schemas and dump them with camelCase aliases.
"""

import json

from ticket_agent.models.schemas.api_schemas import (
    AgentExecutionLogResponse,
    PageActionLogResponse,
    TicketOperationLogResponse,
    TicketResponse,
)
from ticket_agent.orchestrator.orchestrator import orchestrator
from ticket_agent.orchestrator.trace import TraceCollector


def parse_json_object(value) -> dict:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        data = json.loads(value)
        return data if isinstance(data, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {}


def ticket_response(row) -> dict:
    row = dict(row)
    ext_json = parse_json_object(row.get("ext_json"))
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
        ext_json=ext_json,
        order_prefix=row.get("order_prefix") or "",
        biz_type=row.get("biz_type") or "",
        biz_sub_type=row.get("biz_sub_type") or "",
        priority=row.get("priority") or "normal",
        channel=row.get("channel") or "",
        assignee=row.get("assignee") or "",
        department=row.get("department") or "",
        created_at=row["created_at"],
        due_at=row.get("due_at") or "",
        deadline=row.get("deadline") or row.get("due_at") or "",
        updated_at=row.get("updated_at") or "",
        risk_label=row["risk_label"],
        risk_level=row["risk_level"],
        receive_unit=row.get("receive_unit") or "",
        need_reply=bool(row.get("need_reply", 1)),
        status=row["status"],
        content=row["content"],
        closed_at=row.get("closed_at") or "",
        final_reply=row.get("final_reply") or "",
        cancel_reason=row.get("cancel_reason") or "",
    ).model_dump(by_alias=True)


def operation_log_response(row) -> dict:
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


def page_action_log_response(row) -> dict:
    return PageActionLogResponse(
        id=row["id"],
        ticket_id=row.get("ticket_id") or "",
        task_id=row.get("task_id") or "",
        action_kind=row.get("action_kind") or "",
        tool_name=row.get("tool_name") or "",
        target=row.get("target") or "",
        input=json.loads(row.get("input_json") or "{}"),
        output=json.loads(row.get("output_json") or "{}"),
        status=row.get("status") or "",
        result_summary=row.get("result_summary") or "",
        duration_ms=row.get("duration_ms") or 0,
        risk_level=row.get("risk_level") or "",
        stop_reason=row.get("stop_reason") or "",
        operator=row.get("operator") or "sunpilot",
        created_at=row.get("created_at") or "",
    ).model_dump(by_alias=True)


def agent_execution_response(row) -> dict:
    return AgentExecutionLogResponse(
        id=row["id"],
        ticket_id=row["ticket_id"],
        run_id=row["run_id"],
        agent_id=row["agent_id"],
        agent_name=row["agent_name"],
        input=json.loads(row.get("input_json") or "{}"),
        output=json.loads(row.get("output_json") or "{}"),
        error_message=row.get("error_message") or "",
        status=row.get("status") or "",
        duration_ms=row.get("duration_ms") or 0,
        created_at=row.get("created_at") or "",
    ).model_dump(by_alias=True)


def trace_response(trace: TraceCollector) -> list[dict]:
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


def public_result(result: dict) -> dict:
    return orchestrator.public_result(result)
