"""TraceCollector — collects trace steps during agent pipeline execution.

Provides both in-memory collection (for SSE streaming) and
persistence to SQLite (for historical lookup).
"""

import logging
import uuid
from datetime import datetime
from models.agent_trace import TraceStep, TraceStatus
from models.database import get_db

logger = logging.getLogger(__name__)


class TraceCollector:
    """Collects agent execution steps and persists them.

    Usage:
        trace = TraceCollector(ticket_id="coupon")
        trace.start()  # generates run_id
        trace.add_step(agent="Classifier Agent / 分类与优先级判定", agent_id="classifier_agent", ...)
        # ... more steps ...
        steps = trace.to_list()
    """

    def __init__(self, ticket_id: str):
        self.ticket_id = ticket_id
        self.run_id: str = ""
        self._steps: list[TraceStep] = []
        self._start_time: float = 0.0

    @property
    def steps(self) -> list[TraceStep]:
        return list(self._steps)

    def start(self):
        """Generate a new run_id and start tracking."""
        self.run_id = uuid.uuid4().hex[:12]
        self._steps = []
        self._start_time = datetime.now().timestamp()
        logger.info(f"[TraceCollector] Started run {self.run_id} for ticket {self.ticket_id}")

    def add_step(
        self,
        agent: str,
        agent_id: str,
        summary: str,
        duration: str = "0ms",
        status: TraceStatus = TraceStatus.RUNNING,
        result: dict | None = None,
    ) -> TraceStep:
        """Add a trace step and return it."""
        step = TraceStep(
            agent=agent,
            agent_id=agent_id,
            summary=summary,
            duration=duration,
            status=status,
            result=result,
        )
        self._steps.append(step)
        return step

    def update_last(self, summary: str, duration: str, status: TraceStatus):
        """Update the most recently added step (used when agent completes)."""
        if self._steps:
            step = self._steps[-1]
            step.summary = summary
            step.duration = duration
            step.status = status

    def to_list(self) -> list[dict]:
        """Return all steps as dicts for API serialization."""
        return [s.model_dump() for s in self._steps]

    async def persist(self):
        """Write all collected steps to the SQLite trace_steps table."""
        if not self._steps:
            return
        async with get_db() as db:
            for i, step in enumerate(self._steps):
                await db.execute(
                    """INSERT INTO trace_steps
                       (ticket_id, run_id, agent, agent_id, summary, duration, status, step_order)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (self.ticket_id, self.run_id, step.agent, step.agent_id,
                     step.summary, step.duration, step.status.value, i + 1),
                )
            await db.commit()
        logger.info(
            f"[TraceCollector] Persisted {len(self._steps)} steps for "
            f"ticket {self.ticket_id}, run {self.run_id}"
        )
