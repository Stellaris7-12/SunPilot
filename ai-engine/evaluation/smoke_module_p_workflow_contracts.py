"""Module P smoke checks for workflow configuration contracts."""

import json
import sys
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = ENGINE_DIR.parent

from ticket_agent.main import _build_page_task_from_hints, _build_page_task_hints, _detect_call_scenario  # noqa: E402
from ticket_agent.models.domain.workflow import WorkflowConfig, workflow_scenario  # noqa: E402
from ticket_agent.orchestrator.workflow_config import load_workflow_config  # noqa: E402


def _classifier_enum_values(agent_cards: list[dict]) -> set[str]:
    classifier = next(card for card in agent_cards if card["agent_id"] == "classifier_agent")
    return set(classifier["output_schema"]["properties"]["type"]["enum"])


def main():
    workflow_payload = load_workflow_config()
    workflow = WorkflowConfig.model_validate(workflow_payload)
    cards = json.loads((ROOT_DIR / "src" / "ticket_agent" / "data" /  "agent_cards.json").read_text(encoding="utf-8"))

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
        "协商还款": "客户申请协商还款，客户号C20001，希望分期偿还并申请客助方案。",
        "伪冒预防": "客户收到非本人申请信用卡还款提醒，要求登记伪冒预防。",
        "伪冒调查": "客户卡片被系统管制，两核身不过，需调查组核实X-DK。",
        "客户经营": "客户申请汽车分期结清证明和资料借阅，接单单位卡部。",
        "市场企划": "客户反馈麦当劳饭票活动达标后优惠券未到账，含订单号。",
        "调单扣款": "客户反馈流水TXN20260723001需要交易调单扣款核实。",
        "征信": "客户收到贷后历史风险待确认通知，需核实账户逾期状态。",
    }
    expected_types = {
        "协商还款",
        "伪冒预防",
        "伪冒调查",
        "客户经营",
        "市场企划",
        "调单扣款",
        "征信",
    }
    detected_types = {_detect_call_scenario(text)[3] for text in samples.values()}
    assert detected_types == expected_types, detected_types
    assert "COUPON_REISSUE" not in detected_types
    assert "TRANSACTION_DISPUTE" not in detected_types

    scenario = workflow_scenario(workflow_payload, "客户经营")
    assert scenario.requires_human_confirmation is True
    assert scenario.recommended_tool == "customer.lookup"

    draft = {
        "title": "活动达标未收到优惠券",
        "customerId": "C20001",
        "customerName": "王小明",
        "phone": "138****0001",
        "cardLast4": "1001",
        "scene": "市场企划",
        "category": "市场企划",
        "subcategory": "饭票总对总-麦当劳",
        "extJson": {
            "remark": "ORD20260723001",
            "customerFeedback": "客户反馈活动达标后优惠券未到账。",
            "receiveUnit": "市场[020营销管理团队]",
            "bizSubType": "饭票总对总-麦当劳"
        },
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
