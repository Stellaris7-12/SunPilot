"""Module B smoke tests for business-agent naming and workflow config."""

import asyncio
import importlib
import os
import sys
import tempfile
from pathlib import Path


ENGINE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENGINE_DIR))


class FakeClassifierAgent:
    async def run(self, input_data: dict, context: dict = None) -> dict:
        content = input_data.get("ticket_content", "")
        if "address" in content:
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


class FakeIntakeAgent:
    async def run(self, input_data: dict, context: dict = None) -> dict:
        assert "workflow_config" in input_data
        if "MISSING_INFO" in input_data.get("ticket_content", ""):
            return {
                "fields": [
                    {"label": "客户号", "name": "customerId", "value": "C10001"},
                    {"label": "券类型", "name": "couponType", "value": "未提供"},
                    {"label": "原因", "name": "reason", "value": "未提供"},
                ]
            }
        return {
            "fields": [
                {"label": "客户号", "name": "customerId", "value": "C10001"},
                {"label": "券类型", "name": "couponType", "value": "DINING_100_20"},
                {"label": "原因", "name": "reason", "value": "活动达标未到账"},
            ]
        }


class FakeEscalationAgent:
    async def run(self, input_data: dict, context: dict = None) -> dict:
        assert "workflow_config" in input_data
        fields = {field["name"]: field["value"] for field in input_data.get("fields", [])}
        missing = [
            name for name in ("customerId", "couponType", "reason")
            if fields.get(name) == "未提供"
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
        return {
            "checks": [{"label": "必填字段完整", "status": "通过"}],
            "risk_level": "low",
            "risk_decision": "低风险，可进入人工终审结单",
            "can_auto_proceed": True,
            "missing_fields": [],
            "needs_more_info": False,
        }


class FakeResolutionAgent:
    async def run(self, input_data: dict, context: dict = None) -> dict:
        assert "workflow_config" in input_data
        fields = {field["name"]: field["value"] for field in input_data.get("fields", [])}
        return {
            "tool_name": "coupon.reissue",
            "tool_params": fields,
            "skip": False,
            "skip_reason": "",
        }


class FakeNotificationAgent:
    async def run(self, input_data: dict, context: dict = None) -> dict:
        assert "workflow_config" in input_data
        return {"reply_draft": "已核实并完成处理，请客户留意后续状态。"}


class FailingIntakeAgent:
    async def run(self, input_data: dict, context: dict = None) -> dict:
        raise RuntimeError("simulated intake failure")


async def main():
    with tempfile.TemporaryDirectory() as tmp_dir:
        os.environ["DATABASE_PATH"] = str(Path(tmp_dir) / "tickets.db")

        from models.database import get_db, init_db
        from orchestrator.trace import TraceCollector
        import orchestrator.workflow_config as workflow_config_module
        from agents.classifier_agent import ClassifierAgent
        from models.agent_card import AgentCard
        from orchestrator.workflow_config import load_workflow_config

        orchestrator_module = importlib.import_module("orchestrator.orchestrator")
        orchestrator = orchestrator_module.orchestrator

        await init_db()

        orchestrator.classifier_agent = FakeClassifierAgent()
        orchestrator.intake_agent = FakeIntakeAgent()
        orchestrator.escalation_agent = FakeEscalationAgent()
        orchestrator.resolution_agent = FakeResolutionAgent()
        orchestrator.notification_agent = FakeNotificationAgent()

        config = load_workflow_config()
        assert "COUPON_REISSUE" in config["scenarios"], config
        assert config["scenarios"]["COUPON_REISSUE"]["recommended_tool"] == "coupon.reissue"

        original_config_path = workflow_config_module.WORKFLOW_CONFIG_JSON
        workflow_config_module.WORKFLOW_CONFIG_JSON = Path(tmp_dir) / "missing_workflow_config.json"
        workflow_config_module.load_workflow_config.cache_clear()
        try:
            fallback_config = workflow_config_module.load_workflow_config()
            assert fallback_config["scenarios"]["COUPON_REISSUE"]["recommended_tool"] == "coupon.reissue"
        finally:
            workflow_config_module.WORKFLOW_CONFIG_JSON = original_config_path
            workflow_config_module.load_workflow_config.cache_clear()

        class MissingWorkflowNameClassifier(ClassifierAgent):
            async def call_llm(self, system_prompt: str, user_prompt: str) -> dict:
                return {
                    "type": "COUPON_REISSUE",
                    "confidence": 0.88,
                    "reason": "优惠券补发诉求",
                }

        fallback_classifier = MissingWorkflowNameClassifier(
            AgentCard(
                agent_id="classifier_agent",
                name="Classifier Agent / 分类与优先级判定",
                description="test",
            )
        )
        normalized = await fallback_classifier.run({
            "ticket_content": "客户反馈活动达标未收到优惠券",
            "workflow_config": config,
        })
        assert normalized["label"] == "优惠券补发", normalized
        assert normalized["workflow_name"] == "coupon_reissue_flow", normalized

        class InvalidTypeClassifier(ClassifierAgent):
            async def call_llm(self, system_prompt: str, user_prompt: str) -> dict:
                return {
                    "type": "NOT_A_SCENARIO",
                    "confidence": 0.41,
                    "reason": "无法稳定归类",
                }

        invalid_classifier = InvalidTypeClassifier(
            AgentCard(
                agent_id="classifier_agent",
                name="Classifier Agent / 分类与优先级判定",
                description="test",
            )
        )
        invalid = await invalid_classifier.run({
            "ticket_content": "客户表达比较模糊",
            "workflow_config": config,
        })
        assert invalid["type"] == "UNKNOWN", invalid
        assert invalid["workflow_name"] == "unknown_flow", invalid

        async def run(ticket_id: str):
            trace = TraceCollector(ticket_id)
            trace.start()
            queue: asyncio.Queue = asyncio.Queue()
            result = await orchestrator.process_ticket(ticket_id, trace, queue)
            events = []
            while not queue.empty():
                events.append(await queue.get())
            return result, events, trace

        result, events, trace = await run("coupon")
        agent_ids = [step.agent_id for step in trace.steps]
        assert agent_ids == [
            "classifier_agent",
            "intake_agent",
            "escalation_agent",
            "resolution_agent",
            "escalation_agent",
            "notification_agent",
        ], agent_ids
        assert events[0]["data"]["agent_id"] == "classifier_agent", events
        assert result["_terminal_event"] == "workflow_complete", result

        async with get_db() as db:
            await db.execute(
                """INSERT INTO tickets
                   (id, no, title, customer_name, phone, card_last4, scene,
                    created_at, risk_label, risk_level, status, content)
                   VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'), ?, ?, ?, ?)""",
                (
                    "missing_info_b",
                    "T-MISSING-B",
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
            await db.commit()

        result, events, trace = await run("missing_info_b")
        terminal = [event for event in events if event["event"] == "workflow_paused"][-1]
        assert result["_status"] == "pending_info", result
        assert terminal["data"]["pausedAt"] == "escalation_agent", terminal
        assert "escalation_agent" in [step.agent_id for step in trace.steps]

        result, events, trace = await run("dispute")
        assert result["_status"] == "escalated", result
        assert [step.agent_id for step in trace.steps] == ["escalation_agent"], trace.steps

        orchestrator.classifier_agent = FakeClassifierAgent()
        orchestrator.intake_agent = FailingIntakeAgent()
        result, events, trace = await run("coupon")
        assert result["_status"] == "failed", result
        assert trace.steps[-2].agent_id == "intake_agent", trace.steps
        assert trace.steps[-2].status.value == "FAILED", trace.steps
        failed_complete_events = [
            event for event in events
            if event["event"] == "agent_complete"
            and event["data"].get("agent_id") == "intake_agent"
        ]
        assert failed_complete_events[-1]["data"]["status"] == "FAILED", failed_complete_events

        from agents.intent_agent import IntentAgent
        from agents.classifier_agent import ClassifierAgent
        from agents.extract_agent import ExtractAgent
        from agents.intake_agent import IntakeAgent

        assert issubclass(IntentAgent, ClassifierAgent)
        assert issubclass(ExtractAgent, IntakeAgent)

        print("module B smoke passed")


if __name__ == "__main__":
    asyncio.run(main())
