"""FastAPI router for tool endpoints.

Exposes tool listing and direct tool execution as REST endpoints.
Used by the frontend ToolRegistryPanel and for debugging.
"""

from fastapi import APIRouter, HTTPException

from tools.registry import tool_registry
from tools.mock_executor import mock_executor

router = APIRouter(prefix="/api/tools", tags=["tools"])


@router.get("")
async def list_tools():
    """List all registered tools with their definitions."""
    tools = tool_registry.get_all()
    return [t.model_dump() for t in tools]


@router.post("/{tool_name}/execute")
async def execute_tool(tool_name: str, params: dict):
    """Execute a tool directly with the given parameters.

    This is a demo/debug endpoint. In production, tool execution
    would go through the Orchestrator → ToolCallingAgent path.
    """
    tool_def = tool_registry.get(tool_name)
    if tool_def is None:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

    result = await mock_executor.execute(tool_name, params)
    return result.model_dump()
