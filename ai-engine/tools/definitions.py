"""Load tool definitions from JSON configuration."""

import json
from pathlib import Path
from models.tool_schemas import ToolDefinition

TOOLS_JSON = Path(__file__).resolve().parent.parent / "data" / "tools.json"


def load_tool_definitions() -> list[ToolDefinition]:
    """Load and parse all tool definitions from data/tools.json."""
    with open(TOOLS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [ToolDefinition(**item) for item in data]
