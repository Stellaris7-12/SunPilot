"""ResolutionAgent - choose business tools and build invocation parameters."""

import json
import logging
import re

from agents.base import BaseAgent

logger = logging.getLogger(__name__)

_INTENT_TOOL_MAP = {
    "COUPON_REISSUE": "coupon.reissue",
    "CUSTOMER_ADDRESS_UPDATE": "customer.update-address",
    "TRANSACTION_DISPUTE": "transaction.query",
    "BENEFIT_QUERY": "benefit.query",
    "APPLICATION_PROGRESS_QUERY": "application.progress-query",
}

RESOLUTION_SYSTEM_PROMPT = """你是一个信用卡工单解决方案与业务执行专家。
根据分类结果和已抽取字段，选择合适的业务工具并生成调用参数。
你需要返回一个 JSON 对象：
{
  "tool_name": "要调用的工具名称",
  "tool_params": {"参数名": "参数值"},
  "skip": false,
  "skip_reason": ""
}

规则：
1. 工具名称必须从可用工具列表中选择。
2. tool_params 中的参数值从已抽取字段中获取，不要编造关键业务参数。
3. 高风险交易争议可以 skip=true，并说明需要人工复核。
4. 只返回 JSON。"""


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

        fields_dict = {
            field["name"]: field["value"]
            for field in fields
            if field.get("value") not in {"", "未提取", "未提供", None}
        }

        user_prompt = f"""可用工具列表：
{available_tools}

分类结果：
{json.dumps(intent, ensure_ascii=False, indent=2)}

已抽取字段：
{json.dumps(fields, ensure_ascii=False, indent=2)}

请选择最合适的工具并生成调用参数。"""

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
                result["tool_params"] = dict(fields_dict)
                result["skip"] = False
                result["skip_reason"] = ""

        result["tool_params"] = result.get("tool_params") or {}
        result["tool_params"] = _normalize_tool_params(result["tool_params"])
        result["skip"] = bool(result.get("skip", False))
        result["skip_reason"] = result.get("skip_reason", "")

        logger.info(
            "[ResolutionAgent] Selected: %s, skip=%s",
            result.get("tool_name"),
            result.get("skip"),
        )
        return result


def _normalize_tool_params(tool_params: dict) -> dict:
    normalized = dict(tool_params or {})
    for key in ("couponType", "benefitCode", "applicationNo"):
        value = normalized.get(key)
        if isinstance(value, str):
            match = re.search(r"[A-Z][A-Z0-9]+(?:_[A-Z0-9]+)+", value)
            if match:
                normalized[key] = match.group(0)
    verify_status = normalized.get("verifyStatus")
    if isinstance(verify_status, str):
        upper_value = verify_status.upper()
        if "PASSED" in upper_value:
            normalized["verifyStatus"] = "PASSED"
        elif "FAILED" in upper_value:
            normalized["verifyStatus"] = "FAILED"
    return normalized
