"""Module O smoke tests for native tool calling and registry guards."""

import asyncio
import sys
from pathlib import Path


ENGINE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENGINE_DIR))

from agents.resolution_agent import ResolutionAgent  # noqa: E402
from models.agent_card import AgentCard  # noqa: E402
from tools.mock_executor import MockExecutor  # noqa: E402
from tools.registry import tool_registry  # noqa: E402


WORKFLOW_CONFIG = {
    "scenarios": {
        "COUPON_REISSUE": {"recommended_tool": "coupon.reissue"},
        "CUSTOMER_ADDRESS_UPDATE": {"recommended_tool": "customer.update-address"},
        "TRANSACTION_DISPUTE": {"recommended_tool": "transaction.query"},
        "BENEFIT_QUERY": {"recommended_tool": "benefit.query"},
        "APPLICATION_PROGRESS_QUERY": {"recommended_tool": "application.progress-query"},
    }
}


def _card() -> AgentCard:
    return AgentCard(
        agent_id="resolution_agent",
        name="Resolution Agent",
        description="tool calling smoke",
    )


class ToolCallAgent(ResolutionAgent):
    async def call_llm(self, system_prompt: str, user_prompt: str, **kwargs) -> dict:
        assert kwargs.get("tools"), "ResolutionAgent must expose OpenAI tools schema"
        return {
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "coupon_reissue",
                        "arguments": {
                            "customer_id": "C20001",
                            "coupon_type": "DINING_100_20",
                            "reason": "campaign reached",
                        },
                    },
                }
            ],
            "content_json": {},
            "raw_content": "",
        }


class DriftAgent(ResolutionAgent):
    async def call_llm(self, system_prompt: str, user_prompt: str, **kwargs) -> dict:
        return {
            "tool_calls": [],
            "content_json": {
                "tool_name": "transaction_detail_query",
                "tool_params": {
                    "customer_id": "C20011",
                    "amount": "899.00",
                    "merchant": "GLOBAL SHOP",
                },
            },
            "raw_content": "",
        }


class EmptyAgent(ResolutionAgent):
    async def call_llm(self, system_prompt: str, user_prompt: str, **kwargs) -> dict:
        return {"tool_calls": [], "content_json": {}, "raw_content": ""}


class UnknownToolAgent(ResolutionAgent):
    async def call_llm(self, system_prompt: str, user_prompt: str, **kwargs) -> dict:
        return {
            "tool_calls": [
                {
                    "id": "call_bad",
                    "type": "function",
                    "function": {
                        "name": "ticket_close_now",
                        "arguments": {"ticketId": "T1", "finalReply": "done"},
                    },
                }
            ],
            "content_json": {},
            "raw_content": "",
        }


class NoDispatchExecutor(MockExecutor):
    async def _dispatch(self, tool_name, params, category, requires_confirmation):
        raise AssertionError("unknown tools must not enter dispatch")


async def main():
    assert len(tool_registry.get_all()) == 22
    assert tool_registry.get("dispute.case-create") is not None
    assert tool_registry.function_name_for("customer.update-address") == "customer_update_address"

    tools = tool_registry.to_openai_tools(["coupon.reissue", "customer.update-address"])
    assert tools[0]["type"] == "function"
    assert tools[0]["function"]["name"] == "coupon_reissue"
    assert tools[0]["function"]["parameters"]["properties"]["customerId"]["description"] != "customerId"

    normalized = tool_registry.normalize_params(
        "transaction.detail-query",
        {"customer_id": "C20011", "amount": "899.00", "merchant": "GLOBAL SHOP"},
    )
    assert normalized == {
        "customerId": "C20011",
        "amount": 899.0,
        "merchantName": "GLOBAL SHOP",
    }

    coupon = await ToolCallAgent(_card()).run({
        "intent": {"type": "COUPON_REISSUE"},
        "fields": [],
        "workflow_config": WORKFLOW_CONFIG,
    })
    assert coupon["tool_name"] == "coupon.reissue"
    assert coupon["tool_params"]["customerId"] == "C20001"
    assert coupon["tool_params"]["couponType"] == "DINING_100_20"

    drift = await DriftAgent(_card()).run({
        "intent": {"type": "TRANSACTION_DISPUTE"},
        "fields": [],
        "workflow_config": WORKFLOW_CONFIG,
    })
    assert drift["tool_name"] == "transaction.detail-query"
    assert drift["tool_params"]["amount"] == 899.0
    assert drift["tool_params"]["merchantName"] == "GLOBAL SHOP"

    fallback = await EmptyAgent(_card()).run({
        "intent": {"type": "BENEFIT_QUERY"},
        "fields": [{"name": "customerId", "value": "C20003"}],
        "workflow_config": WORKFLOW_CONFIG,
    })
    assert fallback["tool_name"] == "benefit.query"

    unknown = await UnknownToolAgent(_card()).run({
        "intent": {"type": "COUPON_REISSUE"},
        "fields": [{"name": "customerId", "value": "C20001"}],
        "workflow_config": WORKFLOW_CONFIG,
    })
    assert unknown["tool_name"] == "coupon.reissue"
    assert "ticket.close-request" not in unknown["available_tool_names"]

    missing_ok, missing_message, _ = tool_registry.validate_tool_call(
        "coupon.reissue",
        {"customerId": "C20001"},
        allowed_tool_names=["coupon.reissue"],
    )
    assert not missing_ok
    assert "couponType" in missing_message

    executor = NoDispatchExecutor(tool_registry)
    result = await executor.execute("not.registered", {})
    assert not result.success
    assert result.requires_human
    assert result.failure_reason == "Tool not.registered is not registered."

    print("module O tool-calling smoke passed")


if __name__ == "__main__":
    asyncio.run(main())
