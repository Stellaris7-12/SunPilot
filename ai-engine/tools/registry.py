"""Tool Registry - centralized tool discovery and validation.

Future: swap MockExecutor for real MCP Server connections via
``mcp_server_name`` / ``mcp_tool_path`` without changing the orchestrator.
"""

import logging

from models.ticket import RiskLevel
from models.tool_schemas import ToolDefinition
from tools.definitions import load_tool_definitions

logger = logging.getLogger(__name__)

_RISK_ORDER = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2}
_MISSING_VALUES = {"", "未提取", "未提供", "N/A", "UNKNOWN", None}


class ToolRegistry:
    """Central registry of all available business tools."""

    def __init__(self):
        definitions = load_tool_definitions()
        self._tools: dict[str, ToolDefinition] = {tool.name: tool for tool in definitions}
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

    def get_all_summaries(self) -> str:
        """Generate a Markdown summary of all tools for the Resolution Agent."""
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
                    f"  - `{param.name}` ({param.type}, {req}): {param.description}"
                )
            lines.append("")
        return "\n".join(lines)

    def list_for_risk_level(self, max_risk: str) -> list[ToolDefinition]:
        """Filter tools whose risk level does not exceed max_risk."""
        max_order = _RISK_ORDER.get(RiskLevel(max_risk), 2)
        return [
            tool for tool in self._tools.values()
            if _RISK_ORDER.get(RiskLevel(tool.risk_level), 2) <= max_order
        ]

    def validate_params(self, tool_name: str, params: dict) -> tuple[bool, str]:
        """Validate required parameters and return a human-readable result."""
        if tool_name not in self._tools:
            return False, f"工具 '{tool_name}' 不在注册表中"
        missing = self.get_missing_required_params(tool_name, params)
        if missing:
            labels = [
                f"{item['name']} ({item['description']})"
                for item in missing
            ]
            return False, f"缺少必填参数: {', '.join(labels)}"
        return True, "OK"

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


def _is_missing_value(value) -> bool:
    if value in _MISSING_VALUES:
        return True
    text = str(value).strip()
    return (
        not text
        or text.lower() in {"none", "null"}
        or text in {"未提供", "未提取", "未填写", "未知"}
        or text.startswith("鏈")
    )


tool_registry = ToolRegistry()
