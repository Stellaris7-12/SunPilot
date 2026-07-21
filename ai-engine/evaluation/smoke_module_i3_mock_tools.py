"""Module I3 smoke test for production-like mock tools and field enrichment."""

import asyncio
import importlib
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace


ENGINE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENGINE_DIR))


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
    with tempfile.TemporaryDirectory() as tmp_dir:
        os.environ["DB_BACKEND"] = "sqlite"
        os.environ["DATABASE_PATH"] = str(Path(tmp_dir) / "tickets.db")
        database_module, registry_module, executor_module = _load_modules()
        await database_module.init_db()

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
        assert second_coupon.data["businessCode"] == "IDEMPOTENT_REPLAY"
        assert second_coupon.evidence_id == first_coupon.evidence_id

        address_blocked = await executor.execute(
            "customer.update-address",
            {"customerId": "C20001", "newAddress": "New Address", "verifyStatus": "FAILED"},
        )
        assert not address_blocked.success
        assert address_blocked.requires_human

        address_ok = await executor.execute(
            "customer.update-address",
            {"customerId": "C20001", "newAddress": "New Address", "verifyStatus": "PASSED"},
        )
        assert address_ok.success
        assert not address_ok.requires_human

        dispute = await executor.execute(
            "dispute.case-create",
            {"customerId": "C20001", "transactionId": "TXN20001", "reason": "not recognized"},
        )
        assert dispute.success
        assert dispute.requires_human

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

    print("module I3 mock tools smoke passed")


if __name__ == "__main__":
    asyncio.run(main())
