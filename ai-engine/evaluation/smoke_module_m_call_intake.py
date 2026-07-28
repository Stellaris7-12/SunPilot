"""Module M smoke test for call-intake draft generation."""

import sys
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ENGINE_DIR))

import asyncio
import importlib
import sys
from pathlib import Path

from fastapi.testclient import TestClient


from evaluation.mysql_smoke_utils import configure_mysql_test_database, reset_mysql_test_data  # noqa: E402


def _load_app():
    import ticket_agent.config
    import ticket_agent.models.database
    import ticket_agent.repositories.repositories
    import ticket_agent.main

    importlib.reload(ticket_agent.config)
    database_module = importlib.reload(ticket_agent.models.database)
    importlib.reload(ticket_agent.repositories.repositories)
    return importlib.reload(ticket_agent.main).app, database_module


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
        assert payload["detectedTicketType"] == "市场企划"
        assert payload["missingFields"] == []
        assert any(item["target"] == "draft-submit" for item in payload["pageTaskHints"])

        created = client.post("/api/tickets", json=payload["ticketDraft"])
        assert created.status_code == 200, created.text
        assert created.json()["scene"] == "市场企划"

        custom = client.post(
            "/api/call-records/generate-ticket-draft",
            json={
                "transcript": "客户：我看到流水TXN20260721009有一笔星河商场消费需要调单扣款核实，客户号C20009，卡尾3409。",
                "callMeta": {"customerName": "林琪", "phone": "131****2009"},
            },
        )
        assert custom.status_code == 200, custom.text
        custom_payload = custom.json()
        assert custom_payload["ticketDraft"]["customerId"] == "C20009"
        assert custom_payload["ticketDraft"]["cardLast4"] == "3409"
        assert custom_payload["detectedTicketType"] == "调单扣款"

    assert "ticket_agent_test" in database_url
    print("module M call-intake smoke passed")


if __name__ == "__main__":
    main()
