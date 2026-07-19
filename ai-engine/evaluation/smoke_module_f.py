"""Module F smoke tests for Agent evaluation metrics."""

import asyncio
import importlib
import sys
from pathlib import Path


ENGINE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENGINE_DIR))


def _sample(sample_id: str, status: str, requires_human: bool, *, missing_coupon: bool = False) -> dict:
    expected_fields = {
        "customerId": f"C9{sample_id[-3:]}",
        "couponType": "UNPROVIDED" if missing_coupon else "DINING_100_20",
        "reason": "campaign qualified",
    }
    if missing_coupon:
        expected_fields["couponType"] = "\u672a\u63d0\u4f9b"
    return {
        "id": sample_id,
        "ticket": {"riskLevel": "high" if requires_human else "low"},
        "expected": {
            "intentType": "COUPON_REISSUE",
            "workflowName": "coupon_reissue_flow",
            "requiredFields": ["customerId", "couponType", "reason"],
            "expectedFields": expected_fields,
            "expectedTool": "coupon.reissue",
            "expectedStatus": status,
            "replyPoints": ["handled", "evidence"],
            "requiresHuman": requires_human,
        },
    }


def _record(sample: dict, *, status: str, tool_success: bool, requires_human: bool) -> dict:
    expected = sample["expected"]
    fields = [
        {"name": name, "label": name, "value": value}
        for name, value in expected["expectedFields"].items()
    ]
    params = {
        name: value
        for name, value in expected["expectedFields"].items()
        if value != "\u672a\u63d0\u4f9b"
    }
    return {
        "sample": sample,
        "ticket": sample["ticket"],
        "expected": expected,
        "outputs": {
            "intent": {
                "type": expected["intentType"],
                "workflowName": expected["workflowName"],
            },
            "fields": fields,
            "resolution": {
                "toolName": expected["expectedTool"],
                "toolParams": params,
            },
            "toolResult": {
                "success": tool_success,
                "evidenceId": "EV-001" if tool_success else "",
            },
            "notification": {
                "standardReply": {
                    "body": "handled with evidence EV-001",
                    "status": "ready",
                    "evidenceIds": ["EV-001"] if tool_success else [],
                    "nextOwner": "human",
                },
                "internalNotice": {},
                "reviewSummary": {},
                "closureSuggestion": {"requiresHumanReview": requires_human},
                "followUp": {},
            },
            "escalation": {
                "needsMoreInfo": status == "pending_info",
                "canAutoProceed": not requires_human,
            },
            "status": status,
            "durationMs": 2500,
            "requiresHumanReview": requires_human,
        },
    }


async def main():
    evaluator_module = importlib.import_module("evaluation.evaluator")
    evaluator_module.evaluator.reload()

    auto_sample = _sample("eval-f-001", "pending_human_review", False)
    info_sample = _sample("eval-f-002", "pending_info", False, missing_coupon=True)
    escalated_sample = _sample("eval-f-003", "escalated", True)
    records = [
        _record(auto_sample, status="pending_human_review", tool_success=True, requires_human=False),
        _record(info_sample, status="pending_info", tool_success=False, requires_human=False),
        _record(escalated_sample, status="escalated", tool_success=False, requires_human=True),
    ]

    metrics = evaluator_module.evaluator.compute_records(records, source="module_f_smoke")
    assert metrics.evaluated_samples == 3, metrics
    assert metrics.intent_accuracy == 1.0, metrics
    assert metrics.field_completeness == 1.0, metrics
    assert metrics.closed_loop_success_rate == 1.0, metrics
    assert metrics.source == "module_f_smoke", metrics
    assert set(metrics.agents) == {
        "classifier",
        "intake",
        "resolution",
        "notification",
        "escalation",
    }, metrics.agents
    assert metrics.agents["intake"]["missingFieldAccuracy"]["score"] == 1.0, metrics.agents
    assert metrics.agents["escalation"]["humanInterventionAccuracy"]["score"] == 1.0, metrics.agents

    main_module = importlib.import_module("main")
    response = await main_module.get_evaluation_metrics()
    assert response["totalSamples"] == evaluator_module.evaluator.total_samples(), response
    assert response["evaluatedSamples"] == evaluator_module.evaluator.total_samples(), response
    assert response["source"] == "labeled_samples_reference", response
    assert "agents" in response and "classifier" in response["agents"], response
    assert "closedLoopSuccessRate" in response, response

    print("module F smoke passed")


if __name__ == "__main__":
    asyncio.run(main())
