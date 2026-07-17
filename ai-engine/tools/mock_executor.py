"""Mock tool executor — simulates external system calls with configurable delay.

Generates realistic business evidence IDs and replaces template variables
in canned response data.
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime

from models.tool_schemas import ToolResult
from tools.registry import tool_registry

logger = logging.getLogger(__name__)

# Category → evidence ID prefix mapping
_PREFIX_MAP = {
    "coupon": "CP",
    "customer": "ADDR",
    "transaction": "TXN",
}


class MockExecutor:
    """Simulates external API/business system calls.

    Each tool definition specifies mock_delay_ms (simulated latency)
    and mock_response (canned JSON with {{TIMESTAMP}} placeholders).
    """

    def __init__(self, registry=None):
        self._registry = registry or tool_registry

    async def execute(self, tool_name: str, params: dict) -> ToolResult:
        """Execute a tool in mock mode.

        Args:
            tool_name: Fully qualified tool name (e.g. 'coupon.reissue')
            params: Tool parameters (validated before execution)

        Returns:
            ToolResult with success status, evidence_id, and response data.
        """
        tool_def = self._registry.get(tool_name)
        if tool_def is None:
            return ToolResult(
                success=False,
                tool_name=tool_name,
                evidence_id="",
                message=f"工具 '{tool_name}' 不存在",
                duration_ms=0,
            )

        # Validate params
        is_valid, msg = self._registry.validate_params(tool_name, params)
        if not is_valid:
            return ToolResult(
                success=False,
                tool_name=tool_name,
                evidence_id="",
                message=msg,
                duration_ms=0,
            )

        # Simulate execution delay
        start = time.time()
        await asyncio.sleep(tool_def.mock_delay_ms / 1000)

        # Build response from mock template
        evidence_id = self._generate_evidence_id(tool_def.category)
        response = json.loads(json.dumps(tool_def.mock_response))

        # Replace template placeholders
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        for key, val in response.items():
            if isinstance(val, str):
                val = val.replace("{{TIMESTAMP}}", timestamp)
                response[key] = val
        response["evidenceId"] = evidence_id

        elapsed_ms = int((time.time() - start) * 1000)

        logger.info(
            f"[MockExecutor] {tool_name} executed — "
            f"evidence_id={evidence_id}, duration={elapsed_ms}ms"
        )

        return ToolResult(
            success=True,
            tool_name=tool_name,
            evidence_id=evidence_id,
            data=response,
            message=f"工具 {tool_def.display_name} 执行成功",
            duration_ms=elapsed_ms,
        )

    def _generate_evidence_id(self, category: str) -> str:
        """Generate a business-meaningful evidence ID.

        Format: {PREFIX}{YYYYMMDD}{8-char UUID}
        Example: CP20260716A3F8B2C1
        """
        prefix = _PREFIX_MAP.get(category, "EV")
        date_str = datetime.now().strftime("%Y%m%d")
        suffix = str(uuid.uuid4())[:8].upper()
        return f"{prefix}{date_str}{suffix}"


# Module-level singleton
from tools.registry import tool_registry as _registry

mock_executor = MockExecutor(_registry)
