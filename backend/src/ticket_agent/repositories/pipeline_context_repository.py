"""Repository for pipeline_context_snapshots table."""

import json
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import text
from ticket_agent.models.database import _get_engine

logger = logging.getLogger(__name__)


class PipelineContextRepository:
    """Manage pipeline context snapshots for re-entrancy support."""

    async def save_snapshot(
        self,
        ticket_id: str,
        intent_result: dict[str, Any],
        extract_result: dict[str, Any],
        status: str,
        tool_params: dict[str, Any] | None = None,
        verify_result: dict[str, Any] | None = None,
    ) -> None:
        """Save pipeline context snapshot when pausing (PENDING_INFO/PENDING_HUMAN_CONFIRM)."""
        engine = _get_engine()
        async with engine.begin() as conn:
            await conn.execute(
                text("""
                    INSERT INTO pipeline_context_snapshots
                    (ticket_id, intent_result, extract_result, tool_params, verify_result, snapshot_at, status)
                    VALUES (:ticket_id, :intent_result, :extract_result, :tool_params, :verify_result, :snapshot_at, :status)
                    ON DUPLICATE KEY UPDATE
                      intent_result = VALUES(intent_result),
                      extract_result = VALUES(extract_result),
                      tool_params = VALUES(tool_params),
                      verify_result = VALUES(verify_result),
                      snapshot_at = VALUES(snapshot_at),
                      status = VALUES(status)
                """),
                {
                    "ticket_id": ticket_id,
                    "intent_result": json.dumps(intent_result, ensure_ascii=False),
                    "extract_result": json.dumps(extract_result, ensure_ascii=False),
                    "tool_params": json.dumps(tool_params, ensure_ascii=False) if tool_params else None,
                    "verify_result": json.dumps(verify_result, ensure_ascii=False) if verify_result else None,
                    "snapshot_at": datetime.now(),
                    "status": status,
                },
            )
            logger.info("Saved pipeline context snapshot for ticket %s (status=%s)", ticket_id, status)

    async def get_snapshot(self, ticket_id: str) -> dict[str, Any] | None:
        """Load pipeline context snapshot for re-entry."""
        engine = _get_engine()
        async with engine.connect() as conn:
            result = await conn.execute(
                text("""
                    SELECT intent_result, extract_result, tool_params, verify_result, snapshot_at, status
                    FROM pipeline_context_snapshots
                    WHERE ticket_id = :ticket_id
                """),
                {"ticket_id": ticket_id},
            )
            row = result.fetchone()
            if row is None:
                return None

            return {
                "intent_result": json.loads(row[0]) if row[0] else {},
                "extract_result": json.loads(row[1]) if row[1] else {},
                "tool_params": json.loads(row[2]) if row[2] else None,
                "verify_result": json.loads(row[3]) if row[3] else None,
                "snapshot_at": row[4],
                "status": row[5],
            }

    async def delete_snapshot(self, ticket_id: str) -> None:
        """Delete snapshot after ticket is closed or escalated."""
        engine = _get_engine()
        async with engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM pipeline_context_snapshots WHERE ticket_id = :ticket_id"),
                {"ticket_id": ticket_id},
            )
            logger.info("Deleted pipeline context snapshot for ticket %s", ticket_id)


pipeline_context_repository = PipelineContextRepository()
