"""ToolCallingAgent — select and invoke business tools based on intent + fields."""

import json
import logging
from agents.base import BaseAgent
from models.agent_card import AgentCard

logger = logging.getLogger(__name__)

# Intent → default tool mapping (fallback when LLM selection fails)
_INTENT_TOOL_MAP = {
    "COUPON_REISSUE": "coupon.reissue",
    "CUSTOMER_ADDRESS_UPDATE": "customer.update-address",
    "TRANSACTION_DISPUTE": "transaction.query",
}

TOOL_AGENT_SYSTEM_PROMPT = """你是一个信用卡业务工具调用专家。根据意图识别结果和已抽取的字段，选择合适的工具并生成调用参数。

你需要返回一个JSON对象：
{
  "tool_name": "要调用的工具名称",
  "tool_params": {参数名: 参数值},
  "skip": false,
  "skip_reason": ""
}

规则：
1. 如果意图是 TRANSACTION_DISPUTE（交易争议），且风险较高，可以设置 skip=true，理由为"高风险争议需转人工处理"
2. 工具名称必须从可用工具列表中选择（见下方可用工具）
3. tool_params 中的参数值从已抽取字段中获取
4. 只返回JSON，不要包含任何其他文字"""


class ToolCallingAgent(BaseAgent):
    """Select the appropriate business tool and build invocation parameters.

    Uses LLM function-calling pattern: the system prompt lists available
    tools (from ToolRegistry summaries), the LLM selects the best match
    and fills in parameters from extracted fields.

    Input: {"intent": {...}, "fields": [...], "available_tools": "..."}
    Output: {"tool_name": "coupon.reissue", "tool_params": {...}, "skip": false, "skip_reason": ""}
    """

    async def run(self, input_data: dict, context: dict = None) -> dict:
        intent = input_data.get("intent", {})
        fields = input_data.get("fields", [])
        available_tools = input_data.get("available_tools", "")
        intent_type = intent.get("type", "UNKNOWN")

        # Convert fields array to dict for easier param building
        fields_dict = {f["name"]: f["value"] for f in fields}

        user_prompt = f"""可用工具列表：
{available_tools}

意图识别结果：
{json.dumps(intent, ensure_ascii=False, indent=2)}

已抽取字段：
{json.dumps(fields, ensure_ascii=False, indent=2)}

请选择合适的工具并生成调用参数。"""

        # For high-risk transaction disputes, skip tool calling entirely
        if intent_type == "TRANSACTION_DISPUTE":
            logger.info("[ToolCallingAgent] TRANSACTION_DISPUTE detected — skipping tool")
            return {
                "tool_name": "",
                "tool_params": {},
                "skip": True,
                "skip_reason": "交易争议类工单需转人工复核，不自动执行工具"
            }

        logger.info(f"[ToolCallingAgent] Selecting tool for intent={intent_type}")
        result = await self.call_llm(TOOL_AGENT_SYSTEM_PROMPT, user_prompt)

        # Fallback: if LLM returns empty tool_name, use intent→tool mapping
        if not result.get("tool_name"):
            fallback_tool = _INTENT_TOOL_MAP.get(intent_type)
            if fallback_tool:
                logger.warning(
                    f"[ToolCallingAgent] LLM returned no tool — "
                    f"falling back to {fallback_tool}"
                )
                result["tool_name"] = fallback_tool
                result["tool_params"] = {
                    k: v for k, v in fields_dict.items()
                    if v != "未提及"
                }
                result["skip"] = False
                result["skip_reason"] = ""

        logger.info(
            f"[ToolCallingAgent] Selected: {result.get('tool_name')}, "
            f"skip={result.get('skip')}"
        )
        return result
