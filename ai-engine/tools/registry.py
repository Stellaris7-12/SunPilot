"""Tool Registry — centralized tool discovery, validation, and execution.

Design reference:
- Anthropic MCP: Tool standardization via JSON Schema
- OpenAI Function Calling: Tool selection via LLM

Future: swap MockExecutor for real MCP Server connections via mcp_server_name/mcp_tool_path.
"""

import logging
from models.tool_schemas import ToolDefinition
from models.ticket import RiskLevel
from tools.definitions import load_tool_definitions

logger = logging.getLogger(__name__)

# Risk level ordering for filtering
_RISK_ORDER = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2}


class ToolRegistry:
    """Central registry of all available business tools.

    Tools are loaded from data/tools.json at initialization.
    The registry supports discovery, filtering by risk level,
    parameter validation, and execution via MockExecutor.
    """

    def __init__(self):
        definitions = load_tool_definitions()
        self._tools: dict[str, ToolDefinition] = {t.name: t for t in definitions}
        logger.info(f"ToolRegistry initialized with {len(self._tools)} tools: {list(self._tools.keys())}")

    def get_all(self) -> list[ToolDefinition]:
        """Return all registered tools."""
        return list(self._tools.values())

    def get(self, name: str) -> ToolDefinition | None:
        """Look up a tool by its fully qualified name (e.g. 'coupon.reissue')."""
        return self._tools.get(name)

    def get_all_summaries(self) -> str:
        """Generate a Markdown summary of all tools for LLM prompt context.

        The LLM uses this to select the right tool and build correct parameters.
        """
        lines = ["## 可用工具列表\n"]
        for tool in self._tools.values():
            lines.append(f"### {tool.name} — {tool.display_name}")
            lines.append(f"- **描述**: {tool.description}")
            lines.append(f"- **分类**: {tool.category}")
            lines.append(f"- **风险等级**: {tool.risk_level}")
            lines.append(f"- **需要确认**: {'是' if tool.requires_confirmation else '否'}")
            lines.append(f"- **参数**:")
            for p in tool.parameters:
                req = "必填" if p.required else "可选"
                lines.append(f"  - `{p.name}` ({p.type}, {req}): {p.description}")
            lines.append("")
        return "\n".join(lines)

    def list_for_risk_level(self, max_risk: str) -> list[ToolDefinition]:
        """Filter tools whose risk level does not exceed max_risk.

        Example: list_for_risk_level('low') returns only LOW-risk tools.
        """
        max_order = _RISK_ORDER.get(RiskLevel(max_risk), 2)
        return [
            t for t in self._tools.values()
            if _RISK_ORDER.get(RiskLevel(t.risk_level), 2) <= max_order
        ]

    def validate_params(self, tool_name: str, params: dict) -> tuple[bool, str]:
        """Validate that all required parameters are present.

        Returns:
            (is_valid, error_message). If valid, error_message is "OK".
        """
        tool = self._tools.get(tool_name)
        if tool is None:
            return False, f"工具 '{tool_name}' 不在注册表中"
        for p in tool.parameters:
            if p.required and p.name not in params:
                return False, f"缺少必填参数: {p.name} ({p.description})"
        return True, "OK"


# Module-level singleton
tool_registry = ToolRegistry()
