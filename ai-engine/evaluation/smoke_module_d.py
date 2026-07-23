"""Module D smoke tests for notification and reply closure loop."""

import asyncio
import importlib
import os
import sys
import tempfile
from pathlib import Path


ENGINE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENGINE_DIR))

from evaluation.mysql_smoke_utils import configure_mysql_test_database, reset_mysql_test_data  # noqa: E402


class FakeClassifierAgent:
    async def run(self, input_data: dict, context: dict = None) -> dict:
        content = input_data.get("ticket_content", "")
        if "address" in content or "地址" in content:
            return {
                "type": "CUSTOMER_ADDRESS_UPDATE",
                "label": "资料修改",
                "confidence": 0.91,
                "workflow_name": "address_update_flow",
                "reason": "地址修改诉求",
            }
        return {
            "type": "COUPON_REISSUE",
            "label": "优惠券补发",
            "confidence": 0.95,
            "workflow_name": "coupon_reissue_flow",
            "reason": "优惠券补发诉求",
        }


class FakeIntakeAgent:
    async def run(self, input_data: dict, context: dict = None) -> dict:
        content = input_data.get("ticket_content", "")
        intent_type = input_data.get("intent_type")
        if "MISSING_D" in content:
            return {
                "fields": [
                    {"label": "客户号", "name": "customerId", "value": "C-D-MISSING"},
                    {"label": "券类型", "name": "couponType", "value": "未提供"},
                    {"label": "原因", "name": "reason", "value": "未提供"},
                ]
            }
        if intent_type == "CUSTOMER_ADDRESS_UPDATE":
            return {
                "fields": [
                    {"label": "客户号", "name": "customerId", "value": "C-D-ADDR"},
                    {"label": "新地址", "name": "newAddress", "value": "上海市测试路8号"},
                    {"label": "核验状态", "name": "verifyStatus", "value": "已通过"},
                ]
            }
        return {
            "fields": [
                {"label": "客户号", "name": "customerId", "value": "C-D-COUPON"},
                {"label": "券类型", "name": "couponType", "value": "DINING_100_20"},
                {"label": "原因", "name": "reason", "value": "活动达标未到账"},
            ]
        }

    def build_follow_up_prompt(self, missing_params: list[dict]) -> str:
        details = "、".join(item.get("description") or item["name"] for item in missing_params)
        return f"请补充{details}后继续处理。"


class FakeEscalationAgent:
    async def run(self, input_data: dict, context: dict = None) -> dict:
        fields = {field["name"]: field["value"] for field in input_data.get("fields", [])}
        missing = [
            name for name in ("customerId", "couponType", "reason")
            if fields.get(name) == "未提供"
        ]
        if missing:
            return {
                "checks": [{"label": f"必填字段缺失: {', '.join(missing)}", "status": "待补充"}],
                "risk_level": "low",
                "risk_decision": "信息不足，需要客户补充后继续处理",
                "can_auto_proceed": False,
                "missing_fields": missing,
                "needs_more_info": True,
            }

        tool_result = input_data.get("tool_result")
        if tool_result:
            payload = tool_result.model_dump() if hasattr(tool_result, "model_dump") else tool_result
            if not payload.get("success", False) or payload.get("requires_human"):
                return {
                    "checks": [{"label": "工具结果需要人工处理", "status": "需复核"}],
                    "risk_level": "high",
                    "risk_decision": payload.get("failure_reason") or "工具失败或要求人工复核",
                    "can_auto_proceed": False,
                    "missing_fields": [],
                    "needs_more_info": False,
                }

        if input_data.get("intent", {}).get("type") == "CUSTOMER_ADDRESS_UPDATE":
            return {
                "checks": [{"label": "敏感资料修改", "status": "待确认"}],
                "risk_level": "medium",
                "risk_decision": "中风险资料修改，需要人工确认后执行",
                "can_auto_proceed": True,
                "missing_fields": [],
                "needs_more_info": False,
            }

        return {
            "checks": [{"label": "字段完整", "status": "通过"}],
            "risk_level": "low",
            "risk_decision": "低风险，可自动处理并进入人工终审",
            "can_auto_proceed": True,
            "missing_fields": [],
            "needs_more_info": False,
        }


class FakeResolutionAgent:
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


class BundleNotificationAgent:
    async def run(self, input_data: dict, context: dict = None) -> dict:
        status = input_data.get("status", "pending_human_review")
        tool_result = input_data.get("tool_result") or {}
        evidence_id = tool_result.get("evidence_id", "")
        missing = input_data.get("missing_fields", [])
        risk_decision = input_data.get("verify_result", {}).get("risk_decision", "")
        can_close = status == "pending_human_review" and bool(tool_result.get("success"))
        if status == "pending_info":
            body = f"请补充{'、'.join(missing)}后继续处理。"
        elif status == "escalated":
            body = f"该工单已升级人工处理，原因：{input_data.get('failure_reason') or risk_decision}。"
        elif status == "pending_human_confirm":
            body = "该工单需要人工确认后再执行敏感业务动作。"
        else:
            body = f"已完成处理，证据编号：{evidence_id}，请客户留意后续状态。"

        evidence_ids = [evidence_id] if evidence_id else []
        notification = {
            "standard_reply": {
                "title": "标准回单",
                "body": body,
                "status": {
                    "pending_info": "needs_info",
                    "pending_human_confirm": "needs_review",
                    "pending_human_review": "ready",
                    "escalated": "escalated",
                }.get(status, "needs_review"),
                "evidence_ids": evidence_ids,
                "next_owner": "customer" if status == "pending_info" else "human",
            },
            "internal_notice": {
                "title": "内部通知",
                "body": f"状态={status}；下一步按复核摘要处理。",
                "status": "ready" if can_close else "needs_review",
                "evidence_ids": evidence_ids,
                "next_owner": "human",
            },
            "review_summary": {
                "reason": input_data.get("failure_reason") or risk_decision,
                "risk_decision": risk_decision,
                "missing_fields": missing,
                "tool_evidence_ids": evidence_ids,
                "suggested_action": "复核后结案" if can_close else "人工处理或补充信息",
            },
            "closure_suggestion": {
                "can_close": can_close,
                "reason": "具备处理结果和证据编号" if can_close else "当前状态不建议直接结案",
                "final_reply": body,
                "requires_human_review": not can_close,
            },
            "follow_up": {
                "enabled": can_close,
                "template": "结案后发起满意度回访" if can_close else "",
                "trigger_status": "closed" if can_close else "",
            },
        }
        return {"reply_draft": body, "notification": notification}


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
            duration_ms=1,
        )


async def main():
    with tempfile.TemporaryDirectory() as tmp_dir:
        os.environ["DATABASE_PATH"] = str(Path(tmp_dir) / "tickets.db")
        configure_mysql_test_database()

        import config
        import models.database
        import models.repositories

        importlib.reload(config)
        database_module = importlib.reload(models.database)
        importlib.reload(models.repositories)
        await reset_mysql_test_data(database_module)

        from agents.notification_agent import NotificationAgent
        from models.api_schemas import CloseTicketRequest, ConfirmActionRequest
        from models.agent_card import AgentCard
        from models.database import get_db
        from orchestrator.trace import TraceCollector
        from main import close_ticket, confirm_action, get_ai_result, trigger_ai_process

        class MaliciousNotificationAgent(NotificationAgent):
            async def call_llm(self, system_prompt: str, user_prompt: str) -> dict:
                return {
                    "reply_draft": "已完成处理，证据编号：FAKE-EVIDENCE，可以直接结案。",
                    "notification": {
                        "standard_reply": {
                            "title": "伪造成功",
                            "body": "已完成处理，证据编号：FAKE-EVIDENCE，可以直接结案。",
                            "status": "ready",
                            "evidence_ids": ["FAKE-EVIDENCE"],
                            "next_owner": "system",
                        },
                        "internal_notice": {
                            "title": "伪造内部通知",
                            "body": "系统已自动处理。",
                            "status": "ready",
                            "evidence_ids": ["FAKE-EVIDENCE"],
                            "next_owner": "system",
                        },
                        "review_summary": {
                            "reason": "无风险",
                            "risk_decision": "可结案",
                            "missing_fields": [],
                            "tool_evidence_ids": ["FAKE-EVIDENCE"],
                            "suggested_action": "直接结案",
                        },
                        "closure_suggestion": {
                            "can_close": True,
                            "reason": "伪造可结案",
                            "final_reply": "已完成处理，证据编号：FAKE-EVIDENCE，可以直接结案。",
                            "requires_human_review": False,
                        },
                        "follow_up": {
                            "enabled": True,
                            "template": "伪造回访",
                            "trigger_status": "closed",
                        },
                    },
                }

        orchestrator_module = importlib.import_module("orchestrator.orchestrator")
        orchestrator = orchestrator_module.orchestrator

        orchestrator.classifier_agent = FakeClassifierAgent()
        orchestrator.intake_agent = FakeIntakeAgent()
        orchestrator.escalation_agent = FakeEscalationAgent()
        orchestrator.resolution_agent = FakeResolutionAgent()
        orchestrator.notification_agent = BundleNotificationAgent()

        async with get_db() as db:
            await db.execute(
                """INSERT INTO tickets
                   (id, no, title, customer_id, customer_name, phone, card_last4, scene,
                    created_at, risk_label, risk_level, status, content)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?)""",
                (
                    "missing_d",
                    "T-D-MISSING-01",
                    "模块D缺字段",
                    "C-D-MISSING",
                    "测试客户",
                    "138****0000",
                    "0000",
                    "优惠券补发",
                    "低风险",
                    "low",
                    "open",
                    "MISSING_D",
                ),
            )
            await db.execute(
                """INSERT INTO tickets
                   (id, no, title, customer_id, customer_name, phone, card_last4, scene,
                    created_at, risk_label, risk_level, status, content)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?)""",
                (
                    "failure_d",
                    "T-D-FAIL-01",
                    "模块D工具失败",
                    "C-D-COUPON",
                    "测试客户",
                    "138****0002",
                    "0002",
                    "优惠券补发",
                    "低风险",
                    "low",
                    "open",
                    "优惠券补发",
                ),
            )
            await db.execute(
                """INSERT INTO tickets
                   (id, no, title, customer_id, customer_name, phone, card_last4, scene,
                    created_at, risk_label, risk_level, status, content)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?)""",
                (
                    "address_reject_d",
                    "T-D-REJECT-01",
                    "模块D人工拒绝",
                    "C-D-ADDR",
                    "测试客户",
                    "138****0003",
                    "0003",
                    "资料修改",
                    "中风险",
                    "medium",
                    "open",
                    "地址修改 address",
                ),
            )
            await db.commit()

        async def run_ticket(ticket_id: str):
            return await trigger_ai_process(ticket_id)

        coupon_response = await run_ticket("coupon")
        coupon_result = coupon_response["result"]
        assert coupon_response["status"] == "pending_human_review", coupon_response
        assert coupon_result["replyDraft"], coupon_result
        assert coupon_result["notification"]["standardReply"]["body"] == coupon_result["replyDraft"]
        assert coupon_result["notification"]["closureSuggestion"]["canClose"] is True
        assert coupon_result["notification"]["standardReply"]["evidenceIds"], coupon_result

        latest = await get_ai_result("coupon")
        assert latest["notification"]["closureSuggestion"]["canClose"] is True
        close = await close_ticket(
            "coupon",
            CloseTicketRequest(ticket_id="coupon", final_reply=coupon_result["replyDraft"]),
        )
        assert close["status"] == "closed", close

        async with get_db() as db:
            cursor = await db.execute(
                "SELECT notification_json, final_reply, closed_at FROM ai_results WHERE ticket_id = ? ORDER BY id DESC LIMIT 1",
                ("coupon",),
            )
            row = await cursor.fetchone()
        assert row["notification_json"] and "closureSuggestion" in row["notification_json"], row
        assert row["final_reply"] == coupon_result["replyDraft"], row
        assert row["closed_at"], row

        missing_response = await run_ticket("missing_d")
        missing_result = missing_response["result"]
        assert missing_response["status"] == "pending_info", missing_response
        assert missing_result["notification"]["standardReply"]["status"] == "needs_info"
        assert "reason" in missing_result["notification"]["reviewSummary"]["missingFields"], missing_result["notification"]["reviewSummary"]
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT COUNT(*) AS count_value FROM tool_call_log WHERE ticket_id = ?",
                ("missing_d",),
            )
            assert (await cursor.fetchone())["count_value"] == 0

        address_response = await run_ticket("address")
        address_result = address_response["result"]
        assert address_response["status"] == "pending_human_confirm", address_response
        assert address_result["notification"]["closureSuggestion"]["canClose"] is False
        assert address_result["notification"]["reviewSummary"]["suggestedAction"]
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT COUNT(*) AS count_value FROM tool_call_log WHERE ticket_id = ?",
                ("address",),
            )
            assert (await cursor.fetchone())["count_value"] == 0

        confirmed = await confirm_action(
            "address",
            ConfirmActionRequest(ticket_id="address", approved=True),
        )
        assert confirmed["status"] == "pending_human_review", confirmed
        assert confirmed["result"]["notification"]["closureSuggestion"]["canClose"] is True
        assert confirmed["result"]["notification"]["standardReply"]["evidenceIds"], confirmed

        await run_ticket("address_reject_d")
        rejected = await confirm_action(
            "address_reject_d",
            ConfirmActionRequest(ticket_id="address_reject_d", approved=False),
        )
        assert rejected["status"] == "escalated", rejected
        assert rejected["result"]["replyDraft"], rejected
        assert rejected["result"]["notification"]["standardReply"]["status"] == "escalated", rejected
        assert rejected["result"]["notification"]["closureSuggestion"]["canClose"] is False, rejected

        original_executor = orchestrator_module.mock_executor
        orchestrator_module.mock_executor = FailingExecutor()
        try:
            failure_response = await run_ticket("failure_d")
            failure_result = failure_response["result"]
            assert failure_response["status"] == "escalated", failure_response
            assert failure_result["notification"]["standardReply"]["status"] == "escalated"
            assert failure_result["notification"]["closureSuggestion"]["canClose"] is False
            assert "已完成处理" not in failure_result["replyDraft"], failure_result
        finally:
            orchestrator_module.mock_executor = original_executor

        malicious_agent = MaliciousNotificationAgent(
            AgentCard(agent_id="notification_agent", name="Notification Agent", description="test")
        )
        malicious_result = await malicious_agent.run({
            "intent": {
                "type": "COUPON_REISSUE",
                "label": "优惠券补发",
                "confidence": 0.95,
                "workflow_name": "coupon_reissue_flow",
            },
            "fields": [
                {"label": "客户号", "name": "customerId", "value": "C-D-MAL"},
                {"label": "券类型", "name": "couponType", "value": "未提供"},
            ],
            "tool_result": None,
            "verify_result": {
                "risk_level": "low",
                "risk_decision": "信息不足，需要客户补充后继续处理",
                "can_auto_proceed": False,
                "missing_fields": ["couponType"],
                "needs_more_info": True,
                "checks": [],
            },
            "workflow_config": {},
            "status": "pending_info",
            "missing_fields": ["couponType"],
            "failure_reason": "信息不足，需要客户补充后继续处理",
        })
        assert malicious_result["notification"]["closure_suggestion"]["can_close"] is False
        assert malicious_result["notification"]["standard_reply"]["status"] == "needs_info"
        assert malicious_result["notification"]["standard_reply"]["evidence_ids"] == []
        assert "FAKE-EVIDENCE" not in malicious_result["reply_draft"]

        trace = TraceCollector("dispute")
        trace.start()
        queue: asyncio.Queue = asyncio.Queue()
        high_risk = await orchestrator.process_ticket("dispute", trace, queue)
        assert high_risk["_status"] == "escalated", high_risk
        assert high_risk["notification"]["closure_suggestion"]["can_close"] is False
        assert [step.agent_id for step in trace.steps] == ["escalation_agent", "notification_agent"]

        print("module D smoke passed")


if __name__ == "__main__":
    asyncio.run(main())
