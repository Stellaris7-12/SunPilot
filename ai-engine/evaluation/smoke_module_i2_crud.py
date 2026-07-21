"""Module I2 smoke test for CRUD, state transitions, and operation logs."""

import importlib
import os
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient


ENGINE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENGINE_DIR))


def _load_app():
    import config
    import models.database
    import models.repositories
    import tools.definitions
    import tools.registry
    import tools.mock_executor
    import main

    importlib.reload(config)
    importlib.reload(models.database)
    importlib.reload(models.repositories)
    importlib.reload(tools.definitions)
    importlib.reload(tools.registry)
    importlib.reload(tools.mock_executor)
    return importlib.reload(main).app


def main():
    with tempfile.TemporaryDirectory() as tmp_dir:
        os.environ["DB_BACKEND"] = "sqlite"
        os.environ["DATABASE_PATH"] = str(Path(tmp_dir) / "tickets.db")
        app = _load_app()

        with TestClient(app) as client:
            create = client.post(
                "/api/tickets",
                json={
                    "id": "smoke_i2",
                    "no": "T-I2-SMOKE",
                    "title": "I2 smoke ticket",
                    "customerId": "C29998",
                    "customerName": "Smoke User",
                    "phone": "138****9998",
                    "cardLast4": "9998",
                    "scene": "coupon reissue",
                    "category": "benefit",
                    "subcategory": "coupon",
                    "priority": "normal",
                    "channel": "smoke",
                    "assignee": "agent-a",
                    "department": "ops-a",
                    "riskLabel": "low",
                    "riskLevel": "low",
                    "content": "customer C29998 did not receive coupon DINING_100_20",
                },
            )
            assert create.status_code == 200, create.text
            assert create.json()["customerId"] == "C29998"

            listed = client.get("/api/tickets", params={"customerId": "C29998"})
            assert listed.status_code == 200, listed.text
            assert [item["id"] for item in listed.json()] == ["smoke_i2"]

            patch = client.patch(
                "/api/tickets/smoke_i2",
                json={"title": "I2 updated", "priority": "urgent", "operator": "qa"},
            )
            assert patch.status_code == 200, patch.text
            assert patch.json()["title"] == "I2 updated"
            assert patch.json()["priority"] == "urgent"

            assign = client.post(
                "/api/tickets/smoke_i2/assign",
                json={"assignee": "agent-b", "department": "ops-b", "operator": "qa"},
            )
            assert assign.status_code == 200, assign.text
            assert assign.json()["assignee"] == "agent-b"

            draft = client.post(
                "/api/tickets/smoke_i2/reply-draft",
                json={"draft": "draft reply", "operator": "qa"},
            )
            assert draft.status_code == 200, draft.text

            cancel = client.post(
                "/api/tickets/smoke_i2/cancel",
                json={"reason": "duplicate ticket", "operator": "qa"},
            )
            assert cancel.status_code == 200, cancel.text
            assert cancel.json()["status"] == "cancelled"
            assert cancel.json()["cancelReason"] == "duplicate ticket"

            edit_cancelled = client.patch("/api/tickets/smoke_i2", json={"title": "bad"})
            assert edit_cancelled.status_code == 400, edit_cancelled.text

            reopen = client.post(
                "/api/tickets/smoke_i2/reopen",
                json={"reason": "customer called again", "operator": "qa"},
            )
            assert reopen.status_code == 200, reopen.text
            assert reopen.json()["status"] == "open"

            close_bad = client.post(
                "/api/tickets/smoke_i2/close",
                json={"ticketId": "smoke_i2", "finalReply": "bad close"},
            )
            assert close_bad.status_code == 400, close_bad.text

            operations = client.get("/api/tickets/smoke_i2/operations")
            assert operations.status_code == 200, operations.text
            operation_names = {item["operation"] for item in operations.json()}
            assert {
                "create_ticket",
                "edit_ticket",
                "assign_ticket",
                "save_reply_draft",
                "cancel_ticket",
                "reopen_ticket",
            } <= operation_names

    print("module I2 CRUD smoke passed")


if __name__ == "__main__":
    main()
