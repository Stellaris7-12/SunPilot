"""Tool Registry models — MCP-inspired tool abstraction layer."""

from pydantic import BaseModel, Field
from typing import Optional


class ToolParameter(BaseModel):
    """A single parameter definition for a tool."""
    name: str                                   # "customerId"
    type: str                                   # "string" | "number" | "boolean" | "object"
    description: str
    required: bool = True
    example: str = ""


class ToolDefinition(BaseModel):
    """A tool registered in the Tool Registry.

    Tools self-describe their parameters (JSON Schema style), risk level,
    and execution constraints. The MockExecutor uses mock_response and
    mock_delay_ms for simulation. mcp_server_name/path are reserved for
    future MCP protocol integration.
    """
    name: str                                   # "coupon.reissue"
    display_name: str                           # "优惠券补发"
    description: str
    category: str                               # "coupon" | "customer" | "transaction"
    parameters: list[ToolParameter] = []
    requires_confirmation: bool = False         # Need operator confirm before execution?
    risk_level: str = "low"                     # "low" | "medium" | "high"

    # Mock mode
    mock_enabled: bool = True
    mock_response: dict = {}
    mock_delay_ms: int = 500

    # MCP future integration (reserved)
    mcp_server_name: Optional[str] = None
    mcp_tool_path: Optional[str] = None


class ToolResult(BaseModel):
    """Result from a tool execution (mock or real)."""
    success: bool
    tool_name: str
    evidence_id: str                            # e.g. "CP202607160001"
    data: dict = {}                             # Tool-specific response data
    message: str = ""
    duration_ms: int = 0
