"""ResolutionAgent - choose business tools and build invocation parameters."""

import json
import logging

from agents.base import BaseAgent

logger = logging.getLogger(__name__)

_INTENT_TOOL_MAP = {
    "COUPON_REISSUE": "coupon.reissue",
    "CUSTOMER_ADDRESS_UPDATE": "customer.update-address",
    "TRANSACTION_DISPUTE": "transaction.query",
}

RESOLUTION_SYSTEM_PROMPT = """你是一个信用卡工单解决方案与业务执行专家。根据分类结果和已抽取字段，选择合适的业务工具并生成调用参数。
你需要返回一个JSON对象：
{
  "tool_name": "要调用的工具名称",
  "tool_params": {参数名: 参数值},
  "skip": false,
  "skip_reason": ""
}

规则：
1. 如果分类是 TRANSACTION_DISPUTE（交易争议），且风险较高，可以设置 skip=true，理由为"高风险争议需转人工处理"
2. 工具名称必须从可用工具列表中选择
3. tool_params 中的参数值从已抽取字段中获取
4. 只返回JSON，不要包含任何其他文字"""


def _recommended_tool(intent_type: str, workflow_config: dict) -> str | None:
    scenarios = workflow_config.get("scenarios", {})
    return scenarios.get(intent_type, {}).get("recommended_tool") or _INTENT_TOOL_MAP.get(intent_type)


class ResolutionAgent(BaseAgent):
    """Select the appropriate business tool and build invocation parameters."""

    async def run(self, input_data: dict, context: dict = None) -> dict:
        intent = input_data.get("intent", {})
        fields = input_data.get("fields", [])
        available_tools = input_data.get("available_tools", "")
        workflow_config = input_data.get("workflow_config", {})
        intent_type = intent.get("type", "UNKNOWN")

        fields_dict = {f["name"]: f["value"] for f in fields}

        user_prompt = f"""可用工具列表：
{available_tools}

分类结果：
{json.dumps(intent, ensure_ascii=False, indent=2)}

已抽取字段：
{json.dumps(fields, ensure_ascii=False, indent=2)}

请选出最合适的工具并生成调用参数。"""

        if intent_type == "TRANSACTION_DISPUTE":
            logger.info("[ResolutionAgent] TRANSACTION_DISPUTE detected - skipping tool")
            return {
                "tool_name": "",
                "tool_params": {},
                "skip": True,
                "skip_reason": "交易争议类工单需转人工复核，不自动执行业务工具",
            }

        logger.info("[ResolutionAgent] Selecting tool for intent=%s", intent_type)
        result = await self.call_llm(RESOLUTION_SYSTEM_PROMPT, user_prompt)

        if not result.get("tool_name"):
            fallback_tool = _recommended_tool(intent_type, workflow_config)
            if fallback_tool:
                logger.warning(
                    "[ResolutionAgent] LLM returned no tool - falling back to %s",
                    fallback_tool,
                )
                result["tool_name"] = fallback_tool
                result["tool_params"] = {
                    k: v for k, v in fields_dict.items()
                    if v != "未提供"
                }
                result["skip"] = False
                result["skip_reason"] = ""

        logger.info(
            "[ResolutionAgent] Selected: %s, skip=%s",
            result.get("tool_name"),
            result.get("skip"),
        )
        return result
