"""Module I3 MySQL smoke test for mock tools and field enrichment."""

import asyncio
import importlib
import sys
from pathlib import Path
from types import SimpleNamespace


ENGINE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENGINE_DIR))

from evaluation.mysql_smoke_utils import configure_mysql_test_database, reset_mysql_test_data  # noqa: E402


def _load_modules():
    import config
    import models.database
    import models.repositories
    import tools.definitions
    import tools.registry
    import tools.mock_executor

    importlib.reload(config)
    database_module = importlib.reload(models.database)
    importlib.reload(models.repositories)
    importlib.reload(tools.definitions)
    registry_module = importlib.reload(tools.registry)
    executor_module = importlib.reload(tools.mock_executor)
    return database_module, registry_module, executor_module


async def main():
    database_url = configure_mysql_test_database()
    database_module, registry_module, executor_module = _load_modules()
    await reset_mysql_test_data(database_module)

    registry = registry_module.tool_registry
    executor = executor_module.mock_executor
    assert len(registry.get_all()) >= 10
    assert registry.get("customer.lookup") is not None
    assert registry.get("dispute.case-create") is not None

    customer = await executor.execute("customer.lookup", {"customerId": "C20001"})
    assert customer.success, customer
    assert customer.data["auditPayload"]["customer"]["customer_id"] == "C20001"

    benefit = await executor.execute(
        "benefit.entitlement-query",
        {"customerId": "C20003", "benefitCode": "AIRPORT_LOUNGE_2026"},
    )
    assert benefit.success, benefit
    assert benefit.evidence_id.startswith("BEN")

    mall_cashback = await executor.execute(
        "benefit.query",
        {"customerId": "C20029", "benefitCode": "MALL_CASHBACK_2026", "queryReason": "campaign status"},
    )
    assert mall_cashback.success, mall_cashback

    concierge = await executor.execute(
        "benefit.query",
        {"customerId": "C20030", "benefitCode": "CONCIERGE_2026", "queryReason": "service availability"},
    )
    assert concierge.success, concierge

    application = await executor.execute(
        "application.progress-query",
        {"customerId": "C20005", "applicationNo": "APP20260718005"},
    )
    assert application.success, application
    assert application.data["auditPayload"]["application"]["application_no"] == "APP20260718005"

    transaction = await executor.execute(
        "transaction.detail-query",
        {"customerId": "C20011", "transactionId": "TXN20260721011", "amount": 899.0, "merchant": "GLOBAL SHOP"},
    )
    assert transaction.success, transaction
    assert transaction.requires_human
    assert transaction.data["auditPayload"]["transaction"]["transaction_id"] == "TXN20260721011"

    first_coupon = await executor.execute(
        "coupon.reissue",
        {
            "ticketId": "smoke_i3",
            "customerId": "C20001",
            "couponType": "DINING_100_20",
            "reason": "campaign reached",
        },
    )
    second_coupon = await executor.execute(
        "coupon.reissue",
        {
            "ticketId": "smoke_i3",
            "customerId": "C20001",
            "couponType": "DINING_100_20",
            "reason": "campaign reached again",
        },
    )
    assert first_coupon.success and second_coupon.success
    assert first_coupon.evidence_id
    assert second_coupon.data["businessCode"] == "IDEMPOTENT_REPLAY"
    assert second_coupon.evidence_id == first_coupon.evidence_id

    address_blocked = await executor.execute(
        "customer.update-address",
        {"customerId": "C20001", "newAddress": "New Address", "verifyStatus": "FAILED"},
    )
    assert not address_blocked.success
    assert address_blocked.requires_human

    dispute = await executor.execute(
        "dispute.case-create",
        {"customerId": "C20011", "transactionId": "TXN20260721011", "reason": "not recognized"},
    )
    assert dispute.success
    assert dispute.requires_human
    assert dispute.evidence_id.startswith("TXN")

    fake_ticket = SimpleNamespace(
        customer_id="",
        card_last4="1234",
        content="customer says coupon DINING_100_20 was missing",
    )
    enriched, enrichment = await executor.enrich_params(
        "coupon.reissue",
        {"customerId": "未提供", "couponType": "未提供", "reason": "missing coupon"},
        fake_ticket,
    )
    assert enriched["customerId"] == "C20001", enriched
    assert enriched["couponType"] == "DINING_100_20", enriched
    assert enrichment["filledFields"]["customerId"] == "C20001"
    assert enrichment["unresolvedFields"] == []
    assert {"customer.lookup", "coupon.status-query"} <= set(enrichment["sourceTools"])

    assert "ticket_agent_test" in database_url
    print("module I3 MySQL mock tools smoke passed")


if __name__ == "__main__":
    asyncio.run(main())
