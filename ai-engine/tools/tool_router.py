"""FastAPI router for tool endpoints."""

from fastapi import APIRouter, HTTPException

from models.repositories import ticket_repository, tool_call_repository
from tools.mock_executor import mock_executor
from tools.registry import tool_registry

router = APIRouter(prefix="/api/tools", tags=["tools"])


@router.get("")
async def list_tools():
    """List all registered tools with their definitions."""
    tools = tool_registry.get_all()
    return [tool.model_dump(by_alias=True) for tool in tools]


@router.post("/{tool_name}/execute")
async def execute_tool(tool_name: str, body: dict):
    """Execute a tool directly for demos/debugging.

    Accepted bodies:
    - `{...params}`: backward-compatible execution without audit.
    - `{"ticketId": "...", "params": {...}}`: execution plus tool_call_log audit.
    """
    tool_def = tool_registry.get(tool_name)
    if tool_def is None:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

    ticket_id = body.get("ticketId") or body.get("ticket_id")
    params = body.get("params") if isinstance(body.get("params"), dict) else body
    if "ticketId" in params:
        params = {key: value for key, value in params.items() if key != "ticketId"}
    if "ticket_id" in params:
        params = {key: value for key, value in params.items() if key != "ticket_id"}

    result = await mock_executor.execute(tool_name, params)
    if ticket_id:
        await _persist_debug_tool_call(ticket_id, tool_name, params, result)
    return result.model_dump(by_alias=True)


async def _persist_debug_tool_call(ticket_id: str, tool_name: str, request: dict, tool_result):
    if await ticket_repository.get_ticket(ticket_id) is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    await tool_call_repository.insert_tool_call(ticket_id, tool_name, request, tool_result)
