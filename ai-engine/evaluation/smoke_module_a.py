"""Module A smoke tests.

Runs the orchestrator against a temporary SQLite database with deterministic
fake agents, so it does not require an LLM API key and does not touch the
developer's local runtime database.
"""

import asyncio
import importlib
import os
import sqlite3
import sys
import tempfile
from pathlib import Path


ENGINE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENGINE_DIR))


class FakeIntentAgent:
    async def run(self, input_data: dict, context: dict = None) -> dict:
        content = input_data.get("ticket_content", "")
        if "地址" in content or "address" in content:
            return {
                "type": "CUSTOMER_ADDRESS_UPDATE",
                "label": "资料修改",
                "confidence": 0.91,
                "workflow_name": "address_update_flow",
                "reason": "地址修改诉求",
            }
        return {
            "type": "COUPON_REISSUE",
            "label": "补发优惠券",
            "confidence": 0.95,
            "workflow_name": "coupon_reissue_flow",
            "reason": "优惠券补发诉求",
        }


class FakeExtractAgent:
    async def run(self, input_data: dict, context: dict = None) -> dict:
        content = input_data.get("ticket_content", "")
        intent_type = input_data.get("intent_type")
        if "MISSING_INFO" in content:
            return {
                "fields": [
                    {"label": "客户号", "name": "customerId", "value": "C10001"},
                    {"label": "券类型", "name": "couponType", "value": "未提供"},
                    {"label": "原因", "name": "reason", "value": "未提供"},
                ]
            }
        if intent_type == "CUSTOMER_ADDRESS_UPDATE":
            return {
                "fields": [
                    {"label": "客户号", "name": "customerId", "value": "C20002"},
                    {"label": "新地址", "name": "newAddress", "value": "上海市测试路1号"},
                    {"label": "核验状态", "name": "verifyStatus", "value": "已通过"},
                ]
            }
        return {
            "fields": [
                {"label": "客户号", "name": "customerId", "value": "C10001"},
                {"label": "券类型", "name": "couponType", "value": "DINING_100_20"},
                {"label": "原因", "name": "reason", "value": "活动达标未到账"},
            ]
        }


class FakeVerifyAgent:
    async def run(self, input_data: dict, context: dict = None) -> dict:
        fields = input_data.get("fields", [])
        fields_dict = {field["name"]: field["value"] for field in fields}
        missing = [
            name for name in ("customerId", "couponType", "reason")
            if fields_dict.get(name) == "未提供"
        ]
        if missing:
            return {
                "checks": [{"label": f"必填字段缺失: {', '.join(missing)}", "status": "待补充"}],
                "risk_level": "low",
                "risk_decision": "信息不足，需补充必填字段后继续处理",
                "can_auto_proceed": False,
                "missing_fields": missing,
                "needs_more_info": True,
            }
        if input_data.get("intent", {}).get("type") == "CUSTOMER_ADDRESS_UPDATE":
            return {
                "checks": [{"label": "敏感资料修改", "status": "待确认"}],
                "risk_level": "medium",
                "risk_decision": "中风险，需人工确认后执行",
                "can_auto_proceed": True,
                "missing_fields": [],
                "needs_more_info": False,
            }
        return {
            "checks": [{"label": "必填字段完整", "status": "通过"}],
            "risk_level": "low",
            "risk_decision": "低风险，可进入人工终审结单",
            "can_auto_proceed": True,
            "missing_fields": [],
            "needs_more_info": False,
        }


class FakeToolAgent:
    async def run(self, input_data: dict, context: dict = None) -> dict:
        fields = {field["name"]: field["value"] for field in input_data.get("fields", [])}
        intent_type = input_data.get("intent", {}).get("type")
        if intent_type == "CUSTOMER_ADDRESS_UPDATE":
            return {
                "tool_name": "customer.update-address",
                "tool_params": fields,
                "skip": False,
                "skip_reason": "",
            }
        return {
            "tool_name": "coupon.reissue",
            "tool_params": fields,
            "skip": False,
            "skip_reason": "",
        }


class FakeReplyAgent:
    async def run(self, input_data: dict, context: dict = None) -> dict:
        return {"reply_draft": "已核实并完成处理，请客户留意后续状态。"}


class FailingExecutor:
    async def execute(self, tool_name: str, params: dict):
        from models.tool_schemas import ToolResult

        return ToolResult(
            success=False,
            tool_name=tool_name,
            evidence_id="",
            data={"reason": "simulated failure"},
            message="模拟工具失败",
            duration_ms=1,
        )


async def main():
    with tempfile.TemporaryDirectory() as tmp_dir:
        os.environ["DATABASE_PATH"] = str(Path(tmp_dir) / "tickets.db")

        import aiosqlite

        from models.database import get_db, init_db, _migrate_ticket_status_check
        from models.api_schemas import ConfirmActionRequest, ProcessTicketResponse
        from orchestrator.trace import TraceCollector
        from main import confirm_action

        orchestrator_module = importlib.import_module("orchestrator.orchestrator")
        orchestrator = orchestrator_module.orchestrator

        await init_db()

        orchestrator.intent_agent = FakeIntentAgent()
        orchestrator.extract_agent = FakeExtractAgent()
        orchestrator.verify_agent = FakeVerifyAgent()
        orchestrator.tool_agent = FakeToolAgent()
        orchestrator.reply_agent = FakeReplyAgent()

        async def run(ticket_id: str, *, confirmed: bool = False):
            trace = TraceCollector(ticket_id)
            trace.start()
            queue: asyncio.Queue = asyncio.Queue()
            result = await orchestrator.process_ticket(
                ticket_id, trace, queue, confirmed=confirmed
            )
            events = []
            while not queue.empty():
                events.append((await queue.get())["event"])
            return result, events

        async with get_db() as db:
            await db.execute(
                """INSERT INTO tickets
                   (id, no, title, customer_name, phone, card_last4, scene,
                    created_at, risk_label, risk_level, status, content)
                   VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'), ?, ?, ?, ?)""",
                (
                    "missing_info",
                    "T-MISSING",
                    "信息不足优惠券补发",
                    "测试客户",
                    "138****0000",
                    "0000",
                    "补发优惠券",
                    "低风险",
                    "low",
                    "open",
                    "MISSING_INFO",
                ),
            )
            await db.execute(
                """INSERT INTO tickets
                   (id, no, title, customer_name, phone, card_last4, scene,
                    created_at, risk_label, risk_level, status, content)
                   VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'), ?, ?, ?, ?)""",
                (
                    "address_reject",
                    "T-REJECT",
                    "地址修改拒绝",
                    "测试客户",
                    "138****0001",
                    "0001",
                    "资料修改",
                    "中风险",
                    "medium",
                    "open",
                    "地址修改 address",
                ),
            )
            await db.commit()

        result, events = await run("coupon")
        assert result["_status"] == "pending_human_review", result
        assert "workflow_complete" in events, events
        assert result["reply_draft"], result
        assert result["tool_response"].get("evidenceId"), result

        result, events = await run("missing_info")
        assert result["_status"] == "pending_info", result
        assert result["_pause_type"] == "missing_info", result
        assert "workflow_paused" in events, events
        assert result["missing_fields"], result

        result, events = await run("address")
        assert result["_status"] == "pending_human_confirm", result
        assert result["_pause_type"] == "human_confirm", result
        assert "workflow_paused" in events, events

        result, events = await run("address", confirmed=True)
        assert result["_status"] == "pending_human_review", result
        assert "workflow_complete" in events, events

        trace_response = ProcessTicketResponse(
            ticket_id="trace_contract",
            status="pending_human_review",
            trace=[{
                "agent": "测试Agent",
                "agent_id": "test_agent",
                "summary": "ok",
                "duration": "1ms",
                "status": "SUCCESS",
            }],
        ).model_dump(by_alias=True)
        assert trace_response["trace"][0]["agentId"] == "test_agent", trace_response

        result, events = await run("address_reject")
        assert result["_status"] == "pending_human_confirm", result
        reject_response = await confirm_action(
            "address_reject",
            ConfirmActionRequest(ticket_id="address_reject", approved=False),
        )
        assert reject_response["status"] == "escalated", reject_response
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT status, failure_reason FROM ai_results WHERE ticket_id = ? ORDER BY id DESC LIMIT 1",
                ("address_reject",),
            )
            row = await cursor.fetchone()
        assert row["status"] == "escalated", row
        assert row["failure_reason"], row

        original_executor = orchestrator_module.mock_executor
        orchestrator_module.mock_executor = FailingExecutor()
        try:
            result, events = await run("coupon")
            assert result["_status"] == "escalated", result
            assert "workflow_escalated" in events, events
            async with get_db() as db:
                cursor = await db.execute(
                    "SELECT success, failure_reason FROM tool_call_log ORDER BY id DESC LIMIT 1"
                )
                row = await cursor.fetchone()
            assert row["success"] == 0, row
            assert row["failure_reason"], row
        finally:
            orchestrator_module.mock_executor = original_executor

        result, events = await run("dispute")
        assert result["_status"] == "escalated", result
        assert "workflow_escalated" in events, events

        legacy_path = Path(tmp_dir) / "legacy.db"
        legacy = sqlite3.connect(legacy_path)
        legacy.execute(
            """CREATE TABLE tickets (
                id TEXT PRIMARY KEY,
                no TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                customer_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                card_last4 TEXT NOT NULL,
                scene TEXT NOT NULL,
                created_at TEXT NOT NULL,
                risk_label TEXT NOT NULL,
                risk_level TEXT NOT NULL CHECK(risk_level IN ('low','medium','high')),
                status TEXT NOT NULL DEFAULT 'open'
                    CHECK(status IN ('open','in_progress','pending_human_confirm','pending_human_review','escalated','closed')),
                content TEXT NOT NULL
            )"""
        )
        legacy.execute(
            """INSERT INTO tickets
               (id, no, title, customer_name, phone, card_last4, scene,
                created_at, risk_label, risk_level, status, content)
               VALUES ('legacy', 'T-LEGACY', 'legacy', 'legacy', '138****1111',
                       '1111', 'legacy', '2026-07-17 00:00:00', '低风险',
                       'low', 'open', 'legacy')"""
        )
        legacy.commit()
        legacy.close()

        async with aiosqlite.connect(legacy_path) as legacy_db:
            await _migrate_ticket_status_check(legacy_db)
            await legacy_db.execute(
                "UPDATE tickets SET status = 'pending_info' WHERE id = 'legacy'"
            )
            await legacy_db.commit()

        print("module A smoke passed")


if __name__ == "__main__":
    asyncio.run(main())
