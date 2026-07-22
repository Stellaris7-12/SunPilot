"""Module M smoke test for call-intake draft generation."""

import asyncio
import importlib
import sys
from pathlib import Path

from fastapi.testclient import TestClient


ENGINE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENGINE_DIR))

from evaluation.mysql_smoke_utils import configure_mysql_test_database, reset_mysql_test_data  # noqa: E402


def _load_app():
    import config
    import models.database
    import models.repositories
    import main

    importlib.reload(config)
    database_module = importlib.reload(models.database)
    importlib.reload(models.repositories)
    return importlib.reload(main).app, database_module


def main():
    database_url = configure_mysql_test_database()
    app, database_module = _load_app()
    asyncio.run(reset_mysql_test_data(database_module))

    with TestClient(app) as client:
        samples = client.get("/api/call-records")
        assert samples.status_code == 200, samples.text
        assert any(item["id"] == "call-001" for item in samples.json())

        draft = client.post(
            "/api/call-records/generate-ticket-draft",
            json={"sampleId": "call-001", "operatorId": "qa"},
        )
        assert draft.status_code == 200, draft.text
        payload = draft.json()
        assert payload["sourceCallId"] == "call-001"
        assert payload["ticketDraft"]["customerId"] == "C20001"
        assert payload["detectedTicketType"] == "COUPON_REISSUE"
        assert payload["missingFields"] == []
        assert any(item["target"] == "draft-submit" for item in payload["pageTaskHints"])

        created = client.post("/api/tickets", json=payload["ticketDraft"])
        assert created.status_code == 200, created.text
        assert created.json()["scene"] == "优惠券补发"

        custom = client.post(
            "/api/call-records/generate-ticket-draft",
            json={
                "transcript": "客户：我看到流水TXN20260721009有一笔星河商场消费，客户号C20009，卡尾3409。",
                "callMeta": {"customerName": "林琪", "phone": "131****2009"},
            },
        )
        assert custom.status_code == 200, custom.text
        custom_payload = custom.json()
        assert custom_payload["ticketDraft"]["customerId"] == "C20009"
        assert custom_payload["ticketDraft"]["cardLast4"] == "3409"
        assert custom_payload["detectedTicketType"] == "TRANSACTION_DISPUTE"

    assert "ticket_agent_test" in database_url
    print("module M call-intake smoke passed")


if __name__ == "__main__":
    main()
