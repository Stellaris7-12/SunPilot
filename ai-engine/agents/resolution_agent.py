"""ResolutionAgent - choose business tools and build invocation parameters."""

import json
import logging
import re
from typing import Any

from agents.base import BaseAgent
from tools.registry import tool_registry

logger = logging.getLogger(__name__)

_INTENT_TOOL_MAP = {
    "COUPON_REISSUE": [
        "coupon.reissue",
        "coupon.status-query",
        "campaign.eligibility-check",
    ],
    "CUSTOMER_ADDRESS_UPDATE": [
        "customer.update-address",
        "customer.profile-query",
        "customer.lookup",
    ],
    "TRANSACTION_DISPUTE": [
        "transaction.query",
        "transaction.detail-query",
        "merchant.info-query",
        "dispute.case-create",
    ],
    "BENEFIT_QUERY": [
        "benefit.query",
        "benefit.entitlement-query",
        "campaign.eligibility-check",
    ],
    "APPLICATION_PROGRESS_QUERY": [
        "application.progress-query",
        "ticket.history-search",
    ],
}

RESOLUTION_SYSTEM_PROMPT = """你是信用卡工单解决方案与业务工具选择专家。
请根据工单原文、结构化工单、分类结果和已抽取字段，在提供的 tools 中选择最合适的一个工具。

规则：
1. 必须优先返回原生 tool call，不要编造不存在的工具名。
2. 参数必须来自工单、结构化字段或已抽取字段；不要编造客户号、金额、券码、交易号。
3. 交易争议类工具只用于查询取证或准备人工复核，不能表示已经完成结案。
4. 如果无法确定工具或关键参数不足，可以返回 JSON：{"skip": true, "skip_reason": "..."}。
"""


class ResolutionAgent(BaseAgent):
    """Select the appropriate business tool and build invocation parameters."""

    async def run(self, input_data: dict, context: dict = None) -> dict:
        intent = input_data.get("intent", {})
        fields = input_data.get("fields", [])
        workflow_config = input_data.get("workflow_config", {})
        intent_type = intent.get("type", "UNKNOWN")
        candidate_tool_names = _candidate_tool_names(input_data, intent_type, workflow_config)
        openai_tools = tool_registry.to_openai_tools(candidate_tool_names)

        fields_dict = _fields_dict(fields)
        user_prompt = self._build_user_prompt({
            "intent": intent,
            "fields": fields,
            "field_values": fields_dict,
            "ticket_content": input_data.get("ticket_content", ""),
            "ticket": input_data.get("ticket", {}),
            "available_tool_names": candidate_tool_names,
            "workflow_config_for_intent": (
                workflow_config.get("scenarios", {}).get(intent_type, {})
            ),
        })

        logger.info(
            "[ResolutionAgent] Selecting tool for intent=%s candidates=%s",
            intent_type,
            candidate_tool_names,
        )
        llm_result = await self.call_llm(
            RESOLUTION_SYSTEM_PROMPT,
            user_prompt,
            tools=openai_tools,
            tool_choice="auto",
        )

        result = _result_from_llm(llm_result, candidate_tool_names)
        if not result.get("tool_name"):
            result = _fallback_result(intent_type, workflow_config, candidate_tool_names, fields_dict)

        result = _finalize_result(result, candidate_tool_names, fields_dict)

        logger.info(
            "[ResolutionAgent] Selected: %s, skip=%s",
            result.get("tool_name"),
            result.get("skip"),
        )
        return result


def _candidate_tool_names(input_data: dict, intent_type: str, workflow_config: dict) -> list[str]:
    provided = input_data.get("available_tool_names") or []
    if isinstance(provided, str):
        provided = [item.strip() for item in provided.split(",") if item.strip()]
    registry_candidates = [tool.name for tool in tool_registry.list_for_intent(intent_type, workflow_config)]
    mapped = _INTENT_TOOL_MAP.get(intent_type, [])
    recommended = (
        workflow_config.get("scenarios", {})
        .get(intent_type, {})
        .get("recommended_tool")
    )
    names = []
    for name in [recommended, *provided, *registry_candidates, *mapped]:
        if name and name not in names and tool_registry.get(name):
            names.append(name)
    return names


def _fields_dict(fields: list[dict]) -> dict:
    values = {}
    for field in fields:
        value = field.get("value")
        if value not in {"", "未提取", "未提供", "未填写", None}:
            values[field.get("name")] = value
    return values


def _result_from_llm(llm_result: dict, candidate_tool_names: list[str]) -> dict:
    for tool_call in llm_result.get("tool_calls", []) if isinstance(llm_result, dict) else []:
        function = tool_call.get("function", {})
        raw_name = function.get("name", "")
        corrected_name = tool_registry.closest_tool_name(raw_name, candidate_tool_names)
        if corrected_name:
            return {
                "tool_name": corrected_name,
                "tool_params": function.get("arguments", {}),
                "skip": False,
                "skip_reason": "",
            }

    content_json = {}
    if isinstance(llm_result, dict):
        content_json = llm_result.get("content_json") or llm_result
    if not isinstance(content_json, dict):
        return {}
    if content_json.get("skip"):
        return {
            "tool_name": "",
            "tool_params": {},
            "skip": True,
            "skip_reason": content_json.get("skip_reason", "LLM skipped tool selection"),
        }
    raw_name = (
        content_json.get("tool_name")
        or content_json.get("toolName")
        or content_json.get("name")
        or ""
    )
    corrected_name = tool_registry.closest_tool_name(raw_name, candidate_tool_names)
    if corrected_name:
        return {
            "tool_name": corrected_name,
            "tool_params": (
                content_json.get("tool_params")
                or content_json.get("toolParams")
                or content_json.get("arguments")
                or {}
            ),
            "skip": False,
            "skip_reason": "",
        }
    return {}


def _fallback_result(
    intent_type: str,
    workflow_config: dict,
    candidate_tool_names: list[str],
    fields_dict: dict,
) -> dict:
    recommended = (
        workflow_config.get("scenarios", {})
        .get(intent_type, {})
        .get("recommended_tool")
    )
    fallback_tool = recommended if recommended in candidate_tool_names else None
    fallback_tool = fallback_tool or (candidate_tool_names[0] if candidate_tool_names else "")
    if fallback_tool:
        logger.warning(
            "[ResolutionAgent] Falling back to candidate tool %s for intent=%s",
            fallback_tool,
            intent_type,
        )
        return {
            "tool_name": fallback_tool,
            "tool_params": dict(fields_dict),
            "skip": False,
            "skip_reason": "",
        }
    return {
        "tool_name": "",
        "tool_params": {},
        "skip": True,
        "skip_reason": "No candidate tools are available for current intent.",
    }


def _finalize_result(result: dict, candidate_tool_names: list[str], fields_dict: dict) -> dict:
    tool_name = result.get("tool_name", "")
    if tool_name and tool_name not in candidate_tool_names:
        corrected = tool_registry.closest_tool_name(tool_name, candidate_tool_names)
        if corrected:
            tool_name = corrected
        else:
            return {
                "tool_name": "",
                "tool_params": {},
                "skip": True,
                "skip_reason": f"Tool {tool_name} is not allowed for current intent.",
            }

    params = result.get("tool_params") or {}
    if tool_name:
        params = tool_registry.normalize_params(tool_name, params)
        if not params:
            params = tool_registry.normalize_params(tool_name, fields_dict)
        params = _cleanup_business_values(params)

    return {
        "tool_name": tool_name,
        "tool_params": params,
        "skip": bool(result.get("skip", False)),
        "skip_reason": result.get("skip_reason", ""),
        "available_tool_names": candidate_tool_names,
    }


def _cleanup_business_values(tool_params: dict[str, Any]) -> dict:
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
        if "PASSED" in upper_value or "通过" in verify_status:
            normalized["verifyStatus"] = "PASSED"
        elif "FAILED" in upper_value or "未通过" in verify_status:
            normalized["verifyStatus"] = "FAILED"
    return normalized
