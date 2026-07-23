"""Module P smoke checks for workflow configuration contracts."""

import json
import sys
from pathlib import Path


ENGINE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENGINE_DIR))

from main import _build_page_task_from_hints, _build_page_task_hints, _detect_call_scenario  # noqa: E402
from models.workflow import WorkflowConfig, workflow_scenario  # noqa: E402
from orchestrator.workflow_config import load_workflow_config  # noqa: E402


def _classifier_enum_values(agent_cards: list[dict]) -> set[str]:
    classifier = next(card for card in agent_cards if card["agent_id"] == "classifier_agent")
    return set(classifier["output_schema"]["properties"]["type"]["enum"])


def main():
    workflow_payload = load_workflow_config()
    workflow = WorkflowConfig.model_validate(workflow_payload)
    cards = json.loads((ENGINE_DIR / "data" / "agent_cards.json").read_text(encoding="utf-8"))

    scenario_names = set(workflow.scenarios.keys())
    classifier_enums = _classifier_enum_values(cards)
    assert scenario_names == classifier_enums, {
        "workflow_only": sorted(scenario_names - classifier_enums),
        "classifier_only": sorted(classifier_enums - scenario_names),
    }

    for scenario_name, scenario in workflow.scenarios.items():
        assert scenario.workflow_name, scenario_name
        assert scenario.label, scenario_name
        field_names = {field.name for field in scenario.fields}
        assert set(scenario.required_fields).issubset(field_names), scenario_name
        if scenario_name != "UNKNOWN":
            assert scenario.recommended_tool, scenario_name

    samples = {
        "优惠券补发": "客户参加DINING活动达标，客户号C20001，未收到优惠券。",
        "权益资格": "客户咨询AIRPORT贵宾厅权益资格，客户号C20002。",
        "申请进度": "客户查询申请单APP20260723001办理进度，客户号C20003。",
        "资料变更": "客户要求地址变更，客户号C20004，新地址已核验。",
        "交易争议": "客户反馈流水TXN20260723001非本人交易，客户号C20005。",
    }
    expected_types = {
        "COUPON_REISSUE",
        "BENEFIT_QUERY",
        "APPLICATION_PROGRESS_QUERY",
        "CUSTOMER_ADDRESS_UPDATE",
        "TRANSACTION_DISPUTE",
    }
    detected_types = {_detect_call_scenario(text)[3] for text in samples.values()}
    assert detected_types == expected_types, detected_types
    assert "CUSTOMER_INFO_UPDATE" not in detected_types
    assert "TRANSACTION_QUERY" not in detected_types

    scenario = workflow_scenario(workflow_payload, "CUSTOMER_ADDRESS_UPDATE")
    assert scenario.requires_human_confirmation is True
    assert scenario.recommended_tool == "customer.update-address"

    draft = {
        "title": "活动达标未收到优惠券",
        "customerId": "C20001",
        "customerName": "王小明",
        "phone": "138****0001",
        "cardLast4": "1001",
        "scene": "优惠券补发",
        "category": "权益与活动",
        "subcategory": "优惠券补发",
        "priority": "normal",
        "riskLabel": "低风险",
        "riskLevel": "low",
        "content": "客户反馈优惠券未到账。",
    }
    hints = _build_page_task_hints(draft, [])
    page_task = _build_page_task_from_hints(draft, hints, [], "contract-call")
    assert page_task.source == "call_intake"
    assert page_task.scene == "call-intake"
    assert page_task.mode == "auto"
    assert page_task.requires_human_before_submit is False
    assert {action.kind for action in page_task.actions} >= {"fillForm", "clickSemantic"}

    print("module P workflow contracts smoke passed")


if __name__ == "__main__":
    main()
