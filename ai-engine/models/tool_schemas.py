"""Tool registry models."""

from typing import Optional

from pydantic import Field

from .ai_result import ApiModel


class ToolParameter(ApiModel):
    name: str
    type: str
    description: str
    required: bool = True
    example: str = ""


class ToolDefinition(ApiModel):
    name: str
    display_name: str
    description: str
    category: str
    parameters: list[ToolParameter] = Field(default_factory=list)
    requires_confirmation: bool = False
    risk_level: str = "low"
    mock_enabled: bool = True
    mock_response: dict = Field(default_factory=dict)
    mock_delay_ms: int = 500
    mcp_server_name: Optional[str] = None
    mcp_tool_path: Optional[str] = None


class ToolResult(ApiModel):
    success: bool
    tool_name: str
    evidence_id: str
    action: str = ""
    business_result: str = ""
    next_step: str = ""
    requires_human: bool = False
    failure_reason: str = ""
    data: dict = Field(default_factory=dict)
    message: str = ""
    duration_ms: int = 0
