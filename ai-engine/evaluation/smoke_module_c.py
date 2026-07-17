"""Module C smoke tests for Resolution execution and tool audit."""

import asyncio
import importlib
import json
import os
import sys
import tempfile
from pathlib import Path


ENGINE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENGINE_DIR))


class FakeClassifierAgent:
    def __init__(self, intent_type="COUPON_REISSUE"):
        self.intent_type = intent_type

    async def run(self, input_data: dict, context: dict = None) -> dict:
        labels = {
            "COUPON_REISSUE": ("优惠券补发", "coupon_reissue_flow"),
            "BENEFIT_QUERY": ("权益资格查询", "benefit_query_flow"),
            "APPLICATION_PROGRESS_QUERY": ("申请进度查询", "application_progress_query_flow"),
        }
        label, workflow = labels.get(self.intent_type, ("优惠券补发", "coupon_reissue_flow"))
        return {
            "type": self.intent_type,
            "label": label,
            "confidence": 0.95,
            "workflow_name": workflow,
            "reason": "module C deterministic smoke",
        }


class FakeIntakeAgent:
    def __init__(self, fields: list[dict]):
        self.fields = fields

    async def run(self, input_data: dict, context: dict = None) -> dict:
        return {"fields": self.fields}


class PermissiveEscalationAgent:
    async def run(self, input_data: dict, context: dict = None) -> dict:
        tool_result = input_data.get("tool_result")
        if tool_result:
            payload = tool_result.model_dump() if hasattr(tool_result, "model_dump") else tool_result
            if not payload.get("success", False):
                return {
                    "checks": [{"label": "工具失败已拦截", "status": "已拦截"}],
                    "risk_level": "high",
                    "risk_decision": payload.get("failure_reason") or "工具失败，升级人工",
                    "can_auto_proceed": False,
                    "missing_fields": [],
                    "needs_more_info": False,
                }
            business_text = payload.get("business_result", "") or payload.get("businessResult", "")
            if "冲突" in business_text or "权限" in business_text:
                return {
                    "checks": [{"label": "工具结果存在业务异常", "status": "需复核"}],
                    "risk_level": "high",
                    "risk_decision": "工具结果存在冲突或权限异常，升级人工",
                    "can_auto_proceed": False,
                    "missing_fields": [],
                    "needs_more_info": False,
                }
            if payload.get("requires_human"):
                return {
                    "checks": [{"label": "工具要求人工复核", "status": "需复核"}],
                    "risk_level": "medium",
                    "risk_decision": "工具结果要求人工复核，升级人工",
                    "can_auto_proceed": False,
                    "missing_fields": [],
                    "needs_more_info": False,
                }
        return {
            "checks": [{"label": "字段完整", "status": "通过"}],
            "risk_level": "low",
            "risk_decision": "低风险，可自动执行工具",
            "can_auto_proceed": True,
            "missing_fields": [],
            "needs_more_info": False,
        }


class FakeResolutionAgent:
    def __init__(self, tool_name: str, tool_params: dict):
        self.tool_name = tool_name
        self.tool_params = tool_params

    async def run(self, input_data: dict, context: dict = None) -> dict:
        return {
            "tool_name": self.tool_name,
            "tool_params": self.tool_params,
            "skip": False,
            "skip_reason": "",
        }


class FakeNotificationAgent:
    async def run(self, input_data: dict, context: dict = None) -> dict:
        tool_result = input_data.get("tool_result") or {}
        evidence_id = tool_result.get("evidence_id", "")
        return {"reply_draft": f"已完成处理，证据编号：{evidence_id}"}


class FailingExecutor:
    async def execute(self, tool_name: str, params: dict):
        from models.tool_schemas import ToolResult

        return ToolResult(
            success=False,
            tool_name=tool_name,
            evidence_id="",
            action="模拟失败",
            business_result="权限不足，无法执行",
            next_step="转人工处理",
            requires_human=True,
            failure_reason="权限不足，工具执行失败",
            data={"code": "PERMISSION_DENIED"},
            message="权限不足，工具执行失败",
            duration_ms=2,
        )


async def main():
    with tempfile.TemporaryDirectory() as tmp_dir:
        os.environ["DATABASE_PATH"] = str(Path(tmp_dir) / "tickets.db")

        from fastapi.testclient import TestClient

        from models.database import get_db, init_db
        from orchestrator.trace import TraceCollector
        from tools.registry import tool_registry
        from main import app

        orchestrator_module = importlib.import_module("orchestrator.orchestrator")
        orchestrator = orchestrator_module.orchestrator

        await init_db()

        tool_names = {tool.name for tool in tool_registry.get_all()}
        assert {
            "coupon.reissue",
            "customer.update-address",
            "transaction.query",
            "benefit.query",
            "application.progress-query",
        }.issubset(tool_names), tool_names

        async def run(ticket_id: str):
            trace = TraceCollector(ticket_id)
            trace.start()
            queue: asyncio.Queue = asyncio.Queue()
            result = await orchestrator.process_ticket(ticket_id, trace, queue)
            events = []
            while not queue.empty():
                events.append(await queue.get())
            return result, events, trace

        orchestrator.classifier_agent = FakeClassifierAgent("COUPON_REISSUE")
        orchestrator.intake_agent = FakeIntakeAgent([
            {"label": "客户号", "name": "customerId", "value": "C10001"},
            {"label": "券类型", "name": "couponType", "value": "DINING_100_20"},
            {"label": "原因", "name": "reason", "value": "活动达标未到账"},
        ])
        orchestrator.escalation_agent = PermissiveEscalationAgent()
        orchestrator.resolution_agent = FakeResolutionAgent("coupon.reissue", {
            "customerId": "C10001",
            "couponType": "DINING_100_20",
            "reason": "活动达标未到账",
        })
        orchestrator.notification_agent = FakeNotificationAgent()

        result, events, trace = await run("coupon")
        assert result["_status"] == "pending_human_review", result
        assert result["tool_response"]["evidenceId"], result
        assert result["tool_response"]["action"] == "补发优惠券", result
        assert result["tool_response"]["businessResult"], result
        assert "workflow_complete" in [event["event"] for event in events], events

        async with get_db() as db:
            cursor = await db.execute(
                "SELECT response_json, evidence_id, success FROM tool_call_log WHERE ticket_id = ? ORDER BY id DESC LIMIT 1",
                ("coupon",),
            )
            row = await cursor.fetchone()
        persisted_response = json.loads(row["response_json"])
        assert row["success"] == 1, row
        assert persisted_response["evidenceId"] == row["evidence_id"], persisted_response
        assert persisted_response["nextStep"], persisted_response

        with TestClient(app) as client:
            response = client.get("/api/tickets/coupon/tool-calls")
            assert response.status_code == 200, response.text
            calls = response.json()
            assert calls[0]["toolName"] == "coupon.reissue", calls
            assert calls[0]["response"]["businessResult"], calls

            direct = client.post(
                "/api/tools/benefit.query/execute",
                json={
                    "ticketId": "coupon",
                    "params": {
                        "customerId": "C10004",
                        "benefitCode": "AIRPORT_LOUNGE_2026",
                        "queryReason": "debug audit",
                    },
                },
            )
            assert direct.status_code == 200, direct.text
            calls = client.get("/api/tickets/coupon/tool-calls").json()
            assert calls[0]["toolName"] == "benefit.query", calls

        orchestrator.classifier_agent = FakeClassifierAgent("BENEFIT_QUERY")
        orchestrator.intake_agent = FakeIntakeAgent([
            {"label": "客户号", "name": "customerId", "value": "C10004"},
            {"label": "权益编码", "name": "benefitCode", "value": "未提供"},
            {"label": "查询原因", "name": "queryReason", "value": "客户咨询资格"},
        ])
        orchestrator.resolution_agent = FakeResolutionAgent("benefit.query", {
            "customerId": "C10004",
            "queryReason": "客户咨询资格",
        })
        result, events, trace = await run("benefit")
        assert result["_status"] == "pending_info", result
        assert result["_pause_type"] == "missing_info", result
        assert "benefitCode" in result["missing_fields"], result
        assert "请补充" in result["reply_draft"], result
        assert "workflow_paused" in [event["event"] for event in events], events

        original_executor = orchestrator_module.mock_executor
        orchestrator.classifier_agent = FakeClassifierAgent("APPLICATION_PROGRESS_QUERY")
        orchestrator.intake_agent = FakeIntakeAgent([
            {"label": "客户号", "name": "customerId", "value": "C10005"},
            {"label": "申请单号", "name": "applicationNo", "value": "APP20260718001"},
        ])
        orchestrator.resolution_agent = FakeResolutionAgent("application.progress-query", {
            "customerId": "C10005",
            "applicationNo": "APP20260718001",
        })
        orchestrator_module.mock_executor = FailingExecutor()
        try:
            result, events, trace = await run("progress")
            assert result["_status"] == "escalated", result
            assert result["tool_response"]["failureReason"], result
            assert "workflow_escalated" in [event["event"] for event in events], events
            assert trace.steps[-1].agent_id == "escalation_agent", trace.steps
        finally:
            orchestrator_module.mock_executor = original_executor

        orchestrator.resolution_agent = FakeResolutionAgent("transaction.query", {
            "customerId": "C10003",
            "transactionDate": "2026-07-10",
            "amount": "199",
            "merchantName": "某某超市",
        })
        result, events, trace = await run("progress")
        assert result["_status"] == "escalated", result
        assert result["tool_response"]["requiresHuman"] is True, result

        class ConflictExecutor:
            async def execute(self, tool_name: str, params: dict):
                from models.tool_schemas import ToolResult

                return ToolResult(
                    success=True,
                    tool_name=tool_name,
                    evidence_id="EV-CONFLICT",
                    action="模拟冲突",
                    business_result="业务结果冲突，需要人工确认",
                    next_step="转人工复核",
                    requires_human=False,
                    data={"evidenceId": "EV-CONFLICT"},
                    message="工具返回业务冲突",
                    duration_ms=1,
                )

        orchestrator_module.mock_executor = ConflictExecutor()
        try:
            result, events, trace = await run("progress")
            assert result["_status"] == "escalated", result
            assert "冲突" in result["_failure_reason"], result
        finally:
            orchestrator_module.mock_executor = original_executor

        print("module C smoke passed")


if __name__ == "__main__":
    asyncio.run(main())
