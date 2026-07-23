"""Module P smoke tests for AgentCard runtime contract validation."""

import sys
from pathlib import Path


ENGINE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENGINE_DIR))

from orchestrator.schema_validator import (  # noqa: E402
    SchemaValidationError,
    validate_agent_payload,
)
from orchestrator.orchestrator import Orchestrator  # noqa: E402
from orchestrator.state_machine import TicketState  # noqa: E402
from models.agent_contracts import (  # noqa: E402
    ClassifierInput,
    IntakeInput,
    RiskDecision,
    TicketContext,
    ToolPlan,
)
from models.ai_result import FieldEnrichmentResult, IntentResult  # noqa: E402
from models.ticket import Ticket, TicketStatus  # noqa: E402


CLASSIFIER_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "ticket_content": {"type": "string"},
        "workflow_config": {"type": "object"},
    },
    "required": ["ticket_content"],
}

CLASSIFIER_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "type": {
            "type": "string",
            "enum": [
                "COUPON_REISSUE",
                "CUSTOMER_ADDRESS_UPDATE",
                "TRANSACTION_DISPUTE",
                "BENEFIT_QUERY",
                "APPLICATION_PROGRESS_QUERY",
                "UNKNOWN",
            ],
        },
        "label": {"type": "string"},
        "confidence": {"type": "number"},
    },
}

INTAKE_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "fields": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "name": {"type": "string"},
                    "value": {"type": "string"},
                },
                "required": ["name", "value"],
            },
        },
    },
    "required": ["fields"],
}


def _assert_invalid(payload: dict, schema: dict, expected: str):
    try:
        validate_agent_payload(
            payload,
            schema,
            agent_id="contract_smoke_agent",
            direction="output",
        )
    except SchemaValidationError as exc:
        assert expected in str(exc), str(exc)
        return
    raise AssertionError(f"Expected schema validation to fail with: {expected}")


def main():
    ticket = Ticket(
        id="contract_ticket",
        no="TK202607230001",
        title="客户反馈优惠券未到账",
        customer_id="C20001",
        customer_name="张三",
        phone="138****8888",
        card_last4="1234",
        scene="优惠券补发",
        category="权益",
        subcategory="优惠券",
        priority="normal",
        channel="95588",
        created_at="2026-07-23 12:00:00",
        risk_label="低风险",
        risk_level="low",
        status=TicketStatus.OPEN,
        content="客户反馈优惠券未到账，客户号 C20001",
    )
    ticket_context = TicketContext.from_ticket(ticket)
    classifier_payload = ClassifierInput(
        ticket_content=ticket_context.to_summary_text(),
        workflow_config={},
    ).to_agent_dict()
    intake_payload = IntakeInput(
        ticket_content=ticket_context.to_summary_text(),
        intent_type="COUPON_REISSUE",
        intent_label="优惠券补发",
        workflow_config={},
    ).to_agent_dict()
    tool_plan_payload = ToolPlan(
        tool_name="coupon.reissue",
        tool_params={"customerId": "C20001"},
        available_tool_names=["coupon.reissue"],
    ).to_agent_dict()
    risk_payload = RiskDecision(
        risk_level="low",
        risk_decision="低风险，可进入人工终审结单",
        can_auto_proceed=True,
    ).to_agent_dict()

    assert classifier_payload["ticket_content"].startswith("标题:")
    assert intake_payload["intent_type"] == "COUPON_REISSUE"
    assert ticket_context.to_resolution_ticket()["customerId"] == "C20001"
    assert tool_plan_payload["available_tool_names"] == ["coupon.reissue"]
    assert risk_payload["can_auto_proceed"] is True

    validate_agent_payload(
        classifier_payload,
        CLASSIFIER_INPUT_SCHEMA,
        agent_id="classifier_agent",
        direction="input",
    )
    validate_agent_payload(
        {"type": "COUPON_REISSUE", "label": "优惠券补发", "confidence": 0.95},
        CLASSIFIER_OUTPUT_SCHEMA,
        agent_id="classifier_agent",
        direction="output",
    )
    validate_agent_payload(
        {"fields": [{"label": "客户号", "name": "customerId", "value": "C20001"}]},
        INTAKE_OUTPUT_SCHEMA,
        agent_id="intake_agent",
        direction="output",
    )

    _assert_invalid(
        {"workflow_config": {}},
        CLASSIFIER_INPUT_SCHEMA,
        "$.ticket_content is required",
    )
    _assert_invalid(
        {"type": "ADDRESS_CHANGE", "label": "地址修改", "confidence": 0.8},
        CLASSIFIER_OUTPUT_SCHEMA,
        "$.type expected one of",
    )
    _assert_invalid(
        {"fields": [{"label": "客户号", "name": "customerId", "value": 20001}]},
        INTAKE_OUTPUT_SCHEMA,
        "$.fields[0].value expected string",
    )

    page_task = Orchestrator._build_reply_page_task(
        ticket=ticket,
        intent=IntentResult(
            type="COUPON_REISSUE",
            label="优惠券补发",
            confidence=0.95,
            workflow_name="coupon_reissue_flow",
        ),
        status=TicketState.PENDING_HUMAN_REVIEW.value,
        verify_result={
            "risk_level": "low",
            "risk_decision": "低风险，可进入人工终审结单",
        },
        reply_draft="已完成处理，证据编号：TEXT-ONLY-SHOULD-NOT-BE-PARSED。",
        tool_response={
            "success": True,
            "evidenceId": "EV-STRUCT-1",
            "message": "工具返回文本里也可能出现证据编号 TEXT-ONLY-SHOULD-NOT-BE-PARSED",
        },
        field_enrichment=FieldEnrichmentResult(evidence_ids=["EV-ENRICH-1"]),
        missing_fields=[],
        failure_reason="",
    )
    assert page_task.business_payload["evidenceIds"] == ["EV-STRUCT-1", "EV-ENRICH-1"]
    locate_values = [action.value for action in page_task.actions if action.kind == "locateEvidence"]
    assert locate_values == ["EV-STRUCT-1", "EV-ENRICH-1"]
    assert "TEXT-ONLY-SHOULD-NOT-BE-PARSED" not in locate_values

    print("module P agent contract smoke passed")


if __name__ == "__main__":
    main()
