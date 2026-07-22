"""Tool Registry - centralized tool discovery, schema, and validation."""

import difflib
import json
import logging
import re
from typing import Any

from models.ticket import RiskLevel
from models.tool_schemas import ToolDefinition
from tools.definitions import load_tool_definitions

logger = logging.getLogger(__name__)

_RISK_ORDER = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2}
_MISSING_VALUES = {
    "",
    "未提取",
    "未提供",
    "未填写",
    "未知",
    "N/A",
    "UNKNOWN",
    None,
}

_INTENT_CANDIDATE_TOOLS = {
    "COUPON_REISSUE": [
        "coupon.reissue",
        "coupon.status-query",
        "campaign.eligibility-check",
        "customer.lookup",
        "ticket.history-search",
        "knowledge.policy-search",
    ],
    "CUSTOMER_ADDRESS_UPDATE": [
        "customer.update-address",
        "customer.profile-query",
        "customer.lookup",
        "card.account-status-query",
        "ticket.history-search",
        "knowledge.policy-search",
    ],
    "TRANSACTION_DISPUTE": [
        "transaction.query",
        "transaction.detail-query",
        "merchant.info-query",
        "dispute.case-create",
        "card.account-status-query",
        "customer.lookup",
        "ticket.history-search",
        "knowledge.policy-search",
    ],
    "BENEFIT_QUERY": [
        "benefit.query",
        "benefit.entitlement-query",
        "campaign.eligibility-check",
        "customer.lookup",
        "knowledge.policy-search",
    ],
    "APPLICATION_PROGRESS_QUERY": [
        "application.progress-query",
        "customer.lookup",
        "ticket.history-search",
        "knowledge.policy-search",
    ],
    "UNKNOWN": [
        "customer.lookup",
        "ticket.history-search",
        "knowledge.policy-search",
    ],
}

_PARAM_ALIASES = {
    "merchant": "merchantName",
    "merchant_name": "merchantName",
    "transaction_id": "transactionId",
    "transactionid": "transactionId",
    "card_last4": "cardLast4",
    "customer_id": "customerId",
    "customer_name": "customerName",
    "coupon_type": "couponType",
    "benefit_code": "benefitCode",
    "application_no": "applicationNo",
    "verify_status": "verifyStatus",
    "new_address": "newAddress",
    "query_reason": "queryReason",
    "ticket_id": "ticketId",
    "final_reply": "finalReply",
}


class ToolRegistry:
    """Central registry of all available business tools."""

    def __init__(self):
        definitions = load_tool_definitions()
        self._tools: dict[str, ToolDefinition] = {tool.name: tool for tool in definitions}
        self._tool_to_function_name = {
            tool_name: _to_function_name(tool_name)
            for tool_name in self._tools
        }
        self._function_name_to_tool = {
            function_name: tool_name
            for tool_name, function_name in self._tool_to_function_name.items()
        }
        logger.info(
            "ToolRegistry initialized with %s tools: %s",
            len(self._tools),
            list(self._tools.keys()),
        )

    def get_all(self) -> list[ToolDefinition]:
        """Return all registered tools."""
        return list(self._tools.values())

    def get(self, name: str) -> ToolDefinition | None:
        """Look up a tool by its fully qualified name."""
        return self._tools.get(name)

    def resolve_tool_name(self, name: str) -> str | None:
        """Resolve either canonical tool name or OpenAI function name."""
        if not name:
            return None
        if name in self._tools:
            return name
        return self._function_name_to_tool.get(name)

    def function_name_for(self, tool_name: str) -> str:
        """Return the OpenAI-compatible function name for a canonical tool."""
        return self._tool_to_function_name[tool_name]

    def get_all_summaries(self) -> str:
        """Generate a Markdown summary of all tools for legacy prompts."""
        lines = ["## 可用工具列表\n"]
        for tool in self._tools.values():
            lines.append(f"### {tool.name} - {tool.display_name}")
            lines.append(f"- 描述: {tool.description}")
            lines.append(f"- 分类: {tool.category}")
            lines.append(f"- 风险等级: {tool.risk_level}")
            lines.append(f"- 需要确认: {'是' if tool.requires_confirmation else '否'}")
            lines.append("- 参数:")
            for param in tool.parameters:
                req = "必填" if param.required else "可选"
                lines.append(
                    f"  - `{param.name}` ({param.type}, {req}): "
                    f"{param.description} 示例: {param.example}"
                )
            lines.append("")
        return "\n".join(lines)

    def list_for_risk_level(self, max_risk: str) -> list[ToolDefinition]:
        """Filter tools whose risk level does not exceed max_risk."""
        max_order = _risk_order(max_risk)
        return [
            tool for tool in self._tools.values()
            if _risk_order(tool.risk_level) <= max_order
        ]

    def list_for_intent(
        self,
        intent_type: str,
        workflow_config: dict | None = None,
    ) -> list[ToolDefinition]:
        """Return the narrow tool set exposed to the LLM for one intent."""
        workflow_config = workflow_config or {}
        candidates = list(_INTENT_CANDIDATE_TOOLS.get(intent_type, []))
        recommended = (
            workflow_config.get("scenarios", {})
            .get(intent_type, {})
            .get("recommended_tool")
        )
        if recommended:
            candidates.insert(0, recommended)

        seen = set()
        tools = []
        for name in candidates:
            if name in seen:
                continue
            seen.add(name)
            tool = self.get(name)
            if tool is not None:
                tools.append(tool)
        return tools

    def to_openai_tools(self, tool_names: list[str]) -> list[dict]:
        """Generate OpenAI-compatible function tool schemas."""
        schemas = []
        for tool_name in tool_names:
            tool = self.get(tool_name)
            if tool is None:
                continue
            properties = {}
            required = []
            for param in tool.parameters:
                properties[param.name] = {
                    "type": _json_schema_type(param.type),
                    "description": _parameter_description(param),
                }
                if param.example not in {"", None}:
                    properties[param.name]["examples"] = [str(param.example)]
                if param.required:
                    required.append(param.name)
            schemas.append({
                "type": "function",
                "function": {
                    "name": self.function_name_for(tool.name),
                    "description": (
                        f"{tool.display_name}。{tool.description} "
                        f"风险等级: {tool.risk_level}; "
                        f"需要人工确认: {'是' if tool.requires_confirmation else '否'}。"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                        "additionalProperties": False,
                    },
                },
            })
        return schemas

    def closest_tool_name(self, name: str, candidates: list[str]) -> str | None:
        """Correct slight tool-name drift inside a pre-approved candidate set."""
        if not name or not candidates:
            return None
        resolved = self.resolve_tool_name(name)
        if resolved in candidates:
            return resolved

        aliases = {}
        for candidate in candidates:
            aliases[candidate] = candidate
            aliases[self.function_name_for(candidate)] = candidate
            aliases[_compact_name(candidate)] = candidate
        compact = _compact_name(name)
        if compact in aliases:
            return aliases[compact]
        match = difflib.get_close_matches(name, list(aliases.keys()), n=1, cutoff=0.84)
        return aliases[match[0]] if match else None

    def validate_params(self, tool_name: str, params: dict) -> tuple[bool, str]:
        """Validate required parameters and return a human-readable result."""
        if tool_name not in self._tools:
            return False, f"工具 '{tool_name}' 不在注册表中"
        params = self.normalize_params(tool_name, params)
        missing = self.get_missing_required_params(tool_name, params)
        if missing:
            labels = [
                f"{item['name']} ({item['description']})"
                for item in missing
            ]
            return False, f"缺少必填参数: {', '.join(labels)}"
        type_errors = self.get_type_errors(tool_name, params)
        if type_errors:
            return False, f"参数类型不匹配: {', '.join(type_errors)}"
        return True, "OK"

    def validate_tool_call(
        self,
        tool_name: str,
        params: dict,
        *,
        allowed_tool_names: list[str] | None = None,
        max_risk: str | None = None,
        allow_missing_required: bool = False,
    ) -> tuple[bool, str, dict]:
        """Validate one tool call and return normalized params."""
        canonical_name = self.resolve_tool_name(tool_name) or tool_name
        if canonical_name not in self._tools:
            return False, f"Tool {tool_name} is not registered.", {}
        if allowed_tool_names is not None and canonical_name not in set(allowed_tool_names):
            return False, f"Tool {canonical_name} is not allowed for current intent.", {}
        if max_risk is not None and not self.is_risk_allowed(canonical_name, max_risk):
            return False, f"Tool {canonical_name} exceeds max risk {max_risk}.", {}
        normalized = self.normalize_params(canonical_name, params)
        if allow_missing_required:
            type_errors = self.get_type_errors(canonical_name, normalized)
            if type_errors:
                return False, f"参数类型不匹配: {', '.join(type_errors)}", normalized
            return True, "OK", normalized
        is_valid, message = self.validate_params(canonical_name, normalized)
        return is_valid, message, normalized

    def is_risk_allowed(self, tool_name: str, max_risk: str) -> bool:
        tool = self.get(tool_name)
        if tool is None:
            return False
        return _risk_order(tool.risk_level) <= _risk_order(max_risk)

    def normalize_params(self, tool_name: str, params: Any) -> dict:
        """Normalize LLM-produced params to canonical camelCase tool params."""
        tool = self.get(tool_name)
        if tool is None:
            return {}
        payload = _unwrap_params(params)
        canonical_by_lower = {param.name.lower(): param.name for param in tool.parameters}
        normalized = {}
        for key, value in payload.items():
            canonical_name = canonical_by_lower.get(str(key).lower())
            if canonical_name is None:
                alias = _PARAM_ALIASES.get(str(key))
                canonical_name = canonical_by_lower.get(str(alias).lower()) if alias else None
            if canonical_name is None:
                canonical_name = canonical_by_lower.get(_snake_to_camel(str(key)).lower())
            if canonical_name is None:
                continue
            param_type = next(param.type for param in tool.parameters if param.name == canonical_name)
            normalized[canonical_name] = _coerce_type(value, param_type)
        return normalized

    def get_missing_required_params(self, tool_name: str, params: dict) -> list[dict]:
        """Return missing required parameter metadata for a tool call."""
        tool = self._tools.get(tool_name)
        if tool is None:
            return []
        params = params or {}
        missing = []
        for param in tool.parameters:
            value = params.get(param.name)
            if param.required and _is_missing_value(value):
                missing.append({
                    "name": param.name,
                    "description": param.description,
                    "example": param.example,
                })
        return missing

    def get_type_errors(self, tool_name: str, params: dict) -> list[str]:
        tool = self._tools.get(tool_name)
        if tool is None:
            return []
        errors = []
        params = params or {}
        for param in tool.parameters:
            value = params.get(param.name)
            if _is_missing_value(value):
                continue
            if param.type == "number" and not isinstance(value, (int, float)):
                errors.append(f"{param.name} expected number")
            elif param.type == "integer" and not isinstance(value, int):
                errors.append(f"{param.name} expected integer")
            elif param.type == "boolean" and not isinstance(value, bool):
                errors.append(f"{param.name} expected boolean")
            elif param.type == "string" and not isinstance(value, str):
                errors.append(f"{param.name} expected string")
        return errors


def _is_missing_value(value) -> bool:
    try:
        if value in _MISSING_VALUES:
            return True
    except TypeError:
        return False
    text = str(value).strip()
    return (
        not text
        or text.lower() in {"none", "null"}
        or text in _MISSING_VALUES
        or text.startswith("请")
    )


def _to_function_name(tool_name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", tool_name)


def _compact_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _snake_to_camel(value: str) -> str:
    parts = value.split("_")
    return parts[0] + "".join(part.capitalize() for part in parts[1:])


def _json_schema_type(param_type: str) -> str:
    if param_type in {"number", "integer", "boolean", "array", "object"}:
        return param_type
    return "string"


def _parameter_description(param) -> str:
    example = f" 示例: {param.example}。" if param.example else ""
    required = "必填。" if param.required else "可选。"
    return f"{param.description} {required}{example}"


def _unwrap_params(params: Any) -> dict:
    if params is None:
        return {}
    if isinstance(params, str):
        text = params.strip()
        parsed = _parse_json_object(text)
        if parsed is not None:
            return _unwrap_params(parsed)
        match = re.search(r"\{.*\}", text, flags=re.S)
        if match:
            parsed = _parse_json_object(match.group(0))
            if parsed is not None:
                return _unwrap_params(parsed)
        return {}
    if not isinstance(params, dict):
        return {}
    for wrapper_key in ("arguments", "tool_params", "toolParams", "params", "parameters"):
        wrapped = params.get(wrapper_key)
        if isinstance(wrapped, (dict, str)):
            return _unwrap_params(wrapped)
    return params


def _parse_json_object(text: str) -> dict | None:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _coerce_type(value: Any, param_type: str) -> Any:
    if _is_missing_value(value):
        return value
    if param_type == "number" and isinstance(value, str):
        text = value.strip().replace(",", "")
        try:
            return float(text)
        except ValueError:
            return value
    if param_type == "integer" and isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return value
    if param_type == "boolean" and isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "y"}:
            return True
        if lowered in {"false", "0", "no", "n"}:
            return False
    if param_type == "string" and not isinstance(value, str):
        return str(value)
    return value


def _risk_order(value: str) -> int:
    try:
        return _RISK_ORDER.get(RiskLevel(value), 2)
    except ValueError:
        return 2


tool_registry = ToolRegistry()
