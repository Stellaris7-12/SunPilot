"""Module K MySQL smoke test for deterministic workflow routing."""

import asyncio
import importlib
import json
import sys
from pathlib import Path


ENGINE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENGINE_DIR))

from agents.classifier_agent import ClassifierAgent  # noqa: E402
from agents.escalation_agent import EscalationAgent  # noqa: E402
from evaluation.mysql_smoke_utils import configure_mysql_test_database, reset_mysql_test_data  # noqa: E402
from models.agent_card import AgentCard  # noqa: E402
from orchestrator.workflow_config import load_workflow_config  # noqa: E402


def _load_database_modules():
    import config
    import models.database
    import models.repositories

    importlib.reload(config)
    database_module = importlib.reload(models.database)
    repositories_module = importlib.reload(models.repositories)
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
        for ticket in json.loads((ENGINE_DIR / "data" / "tickets.json").read_text(encoding="utf-8"))
    }

    classifier = ClassifierAgent(
        AgentCard(agent_id="classifier_agent", name="Classifier Agent", description="")
    )
    points = await classifier.run({
        "ticket_content": _ticket_context(tickets["demo_points_001"]),
        "workflow_config": config,
    })
    assert points["type"] == "BENEFIT_QUERY", points
    assert points["workflow_name"] == "benefit_query_flow", points

    activity = await classifier.run({
        "ticket_content": _ticket_context(tickets["demo_activity_001"]),
        "workflow_config": config,
    })
    assert activity["type"] == "BENEFIT_QUERY", activity

    installment = await classifier.run({
        "ticket_content": _ticket_context(tickets["demo_installment_002"]),
        "workflow_config": config,
    })
    assert installment["type"] == "UNKNOWN", installment
    assert "未接入自动工具" in installment["reason"], installment

    card_loss = await classifier.run({
        "ticket_content": _ticket_context(tickets["demo_card_loss_001"]),
        "workflow_config": config,
    })
    assert card_loss["type"] == "UNKNOWN", card_loss
    assert "挂失" in card_loss["reason"] or "补卡" in card_loss["reason"], card_loss

    escalation = EscalationAgent(
        AgentCard(agent_id="escalation_agent", name="Escalation Agent", description="")
    )
    transaction_gate = await escalation.run({
        "ticket": {"risk_level": "medium", "risk_label": "中风险", "scene": "交易核查"},
        "intent": {"type": "TRANSACTION_DISPUTE", "confidence": 0.95},
        "fields": [
            {"name": "customerId", "value": "C20027"},
            {"name": "transactionDate", "value": "2026-07-20"},
            {"name": "amount", "value": "68.0"},
            {"name": "merchantName", "value": "某电商平台"},
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
