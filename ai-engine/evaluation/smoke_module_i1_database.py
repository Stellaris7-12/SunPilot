"""Module I1 smoke test for database schema, seed data, and repositories."""

import asyncio
import importlib
import json
import os
import sys
import tempfile
from pathlib import Path


ENGINE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENGINE_DIR))


def _load_database_modules():
    import config
    import models.database
    import models.repositories

    importlib.reload(config)
    database_module = importlib.reload(models.database)
    repo_module = importlib.reload(models.repositories)
    return database_module, repo_module


async def main():
    original_backend = os.getenv("DB_BACKEND")
    original_database_url = os.getenv("DATABASE_URL")
    await _run_sqlite_smoke()
    if os.getenv("RUN_MYSQL_SMOKE") == "1":
        if original_backend:
            os.environ["DB_BACKEND"] = original_backend
        if original_database_url:
            os.environ["DATABASE_URL"] = original_database_url
        await _run_mysql_smoke()
    print("module I1 database smoke passed")


async def _run_sqlite_smoke():
    with tempfile.TemporaryDirectory() as tmp_dir:
        os.environ["DB_BACKEND"] = "sqlite"
        os.environ["DATABASE_PATH"] = str(Path(tmp_dir) / "tickets.db")

        database_module, repo_module = _load_database_modules()

        await database_module.init_db()

        tickets = await repo_module.ticket_repository.list_tickets()
        assert len(tickets) >= 30, len(tickets)
        assert not {"T-D-FAIL", "T-D-MISSING"} & {ticket["no"] for ticket in tickets}
        assert not {"failure_d", "missing_d"} & {ticket["id"] for ticket in tickets}

        customer_ids = {ticket["customer_id"] for ticket in tickets}
        assert all(customer_id.startswith("C2") for customer_id in customer_ids), customer_ids
        assert len({ticket["subcategory"] for ticket in tickets}) >= 10
        assert {"pending_info", "pending_human_confirm", "pending_human_review", "escalated", "closed"} <= {
            ticket["status"] for ticket in tickets
        }

        created = await repo_module.ticket_repository.create_ticket({
            "id": "smoke_i1",
            "no": "T-I1-SMOKE",
            "title": "I1 smoke ticket",
            "customer_id": "C29999",
            "customer_name": "Smoke",
            "phone": "139****9999",
            "card_last4": "9999",
            "scene": "优惠券补发",
            "category": "权益与活动",
            "subcategory": "优惠券补发",
            "priority": "normal",
            "channel": "smoke",
            "assignee": "system",
            "department": "smoke",
            "risk_label": "低风险",
            "risk_level": "low",
            "content": "客户号C29999反馈优惠券未到账，券类型DINING_100_20。",
        })
        assert created["customer_id"] == "C29999", created

        class Trace:
            run_id = "run_i1"

        public_result = {
            "workflowName": "smoke_flow",
            "notification": {"closureSuggestion": {"canClose": True}},
        }
        await repo_module.ai_result_repository.insert_ai_result(
            "smoke_i1",
            Trace(),
            {
                "_status": "pending_human_review",
                "_total_duration_ms": 12,
                "workflow_name": "smoke_flow",
                "intent": {"type": "COUPON_REISSUE", "label": "优惠券补发", "confidence": 1.0},
                "fields": [],
                "tool_response": {"evidenceId": "EV-I1-001"},
                "reply_draft": "已核实并建议补发。",
                "requires_human_review": True,
            },
            public_result,
        )
        assert json.loads(await repo_module.ai_result_repository.get_latest_result_json("smoke_i1")) == public_result

        class ToolResult:
            success = True
            evidence_id = "EV-I1-001"
            duration_ms = 3
            failure_reason = ""
            message = "ok"

            def model_dump(self, by_alias=False):
                return {"success": True, "evidenceId": self.evidence_id}

        await repo_module.tool_call_repository.insert_tool_call(
            "smoke_i1", "coupon.reissue", {"couponType": "DINING_100_20"}, ToolResult()
        )
        calls = await repo_module.tool_call_repository.list_tool_calls("smoke_i1")
        assert calls and calls[0]["evidence_id"] == "EV-I1-001", calls

        await repo_module.ticket_repository.update_status("smoke_i1", "pending_human_review")
        await repo_module.ticket_repository.close_ticket("smoke_i1", "最终回单")
        closed = await repo_module.ticket_repository.get_ticket("smoke_i1")
        assert closed["status"] == "closed", closed
        assert closed["final_reply"] == "最终回单", closed
        assert closed["closed_at"], closed


async def _run_mysql_smoke():
    if not os.getenv("DATABASE_URL"):
        raise AssertionError("DATABASE_URL must be set for RUN_MYSQL_SMOKE=1")

    database_module, repo_module = _load_database_modules()

    await database_module.init_db()
    tickets = await repo_module.ticket_repository.list_tickets()
    bad = [
        ticket
        for ticket in tickets
        if ticket["id"] in {"failure_d", "missing_d"}
        or ticket["no"] in {"T-D-FAIL", "T-D-MISSING", "T-D-FAIL-01", "T-D-MISSING-01"}
    ]
    assert len(tickets) >= 30, len(tickets)
    assert not bad, bad
    assert len({ticket["subcategory"] for ticket in tickets}) >= 10
    assert all(str(ticket["customer_id"]).startswith("C2") for ticket in tickets)


if __name__ == "__main__":
    asyncio.run(main())
