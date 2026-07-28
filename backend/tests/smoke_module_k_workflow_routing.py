"""Module K MySQL smoke test for deterministic workflow routing."""

import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
BACKEND_DIR = TESTS_DIR.parent
ROOT_DIR = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR / "tests"))

import asyncio
import importlib
import json
import sys
from pathlib import Path


from ticket_agent.agents.classifier_agent import ClassifierAgent  # noqa: E402
from ticket_agent.agents.escalation_agent import EscalationAgent  # noqa: E402
from mysql_smoke_utils import configure_mysql_test_database, reset_mysql_test_data  # noqa: E402
from ticket_agent.models.domain.agent_card import AgentCard  # noqa: E402
from ticket_agent.orchestrator.workflow_config import load_workflow_config  # noqa: E402


def _load_database_modules():
    import ticket_agent.config
    import ticket_agent.models.database
    import ticket_agent.repositories.repositories

    importlib.reload(ticket_agent.config)
    database_module = importlib.reload(ticket_agent.models.database)
    repositories_module = importlib.reload(ticket_agent.repositories.repositories)
    return database_module, repositories_module


def _ticket_context(ticket: dict) -> str:
    parts = [
        ("标题", ticket.get("title", "")),
        ("场景", ticket.get("scene", "")),
        ("类目", ticket.get("category", "")),
        ("子类目", ticket.get("subcategory", "")),
        ("客户号", ticket.get("customer_id", "")),
        ("手机号", ticket.get("phone", "")),
        ("卡尾号", ticket.get("card_last4", "")),
        ("风险等级", ticket.get("risk_level", "")),
        ("正文", ticket.get("content", "")),
    ]
    return "\n".join(f"{label}: {value}" for label, value in parts if value)


async def main():
    configure_mysql_test_database()
    database_module, repositories_module = _load_database_modules()
    await reset_mysql_test_data(database_module)

    config = load_workflow_config()
    tickets = {
        ticket["id"]: ticket
        for ticket in json.loads((BACKEND_DIR / "src" / "ticket_agent" / "data" /  "tickets.json").read_text(encoding="utf-8"))
    }

    classifier = ClassifierAgent(
        AgentCard(agent_id="classifier_agent", name="Classifier Agent", description="")
    )
    market = await classifier.run({
        "ticket_content": "场景: 市场企划\n客户号: C20037\n正文: 客户反馈麦当劳饭票活动达标后优惠券未到账，订单号ORD20260723001。",
        "workflow_config": config,
    })
    assert market["type"] == "市场企划", market
    assert market["workflow_name"] == "marketing_planning_dispatch_flow", market

    fraud = await classifier.run({
        "ticket_content": "客户卡片被系统管制，两核身不过，需伪冒调查组核实X-DK。",
        "workflow_config": config,
    })
    assert fraud["type"] == "伪冒调查", fraud

    credit = await classifier.run({
        "ticket_content": "客户收到贷后历史风险待确认通知，要求核实征信账户逾期状态。",
        "workflow_config": config,
    })
    assert credit["type"] == "征信", credit

    unknown = await classifier.run({
        "ticket_content": "客户咨询网点停车券领取规则。",
        "workflow_config": config,
    })
    assert unknown["type"] == "UNKNOWN", unknown

    escalation = EscalationAgent(
        AgentCard(agent_id="escalation_agent", name="Escalation Agent", description="")
    )
    transaction_gate = await escalation.run({
        "ticket": {"risk_level": "medium", "risk_label": "中风险", "scene": "调单扣款"},
        "intent": {"type": "调单扣款", "confidence": 0.95},
        "fields": [
            {"name": "customerId", "value": "C20027"},
            {"name": "customerName", "value": "测试客户"},
            {"name": "phone", "value": "138****2027"},
            {"name": "content", "value": "客户要求交易调单扣款核实"},
            {"name": "workOrderCategory", "value": "交易调单扣款"},
            {"name": "callPurpose", "value": "交易调单扣款核实"},
        ],
        "tool_result": None,
        "workflow_config": config,
    })
    assert transaction_gate["can_auto_proceed"], transaction_gate

    transaction = await repositories_module.mock_business_repository.get_transaction({
        "customerId": "C20027",
        "amount": "未提供",
    })
    assert transaction is not None, transaction
    assert transaction["customer_id"] == "C20027", transaction

    print("module K workflow routing smoke passed")


if __name__ == "__main__":
    asyncio.run(main())
