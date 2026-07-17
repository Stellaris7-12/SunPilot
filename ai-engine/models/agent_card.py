"""Agent Card models — A2A-lite self-describing agent metadata."""

from pydantic import BaseModel, Field
from typing import Optional


class AgentSkill(BaseModel):
    """A single capability description for an agent."""
    id: str                                     # "intent_recognition"
    name: str                                   # "意图识别"
    description: str
    examples: list[str] = []


class AgentCard(BaseModel):
    """A2A-lite Agent Card — inspired by Google's A2A protocol.

    Each agent self-describes its capabilities, I/O schema, risk profile,
    and operational constraints. The orchestrator uses these cards for
    discovery and routing decisions.
    """
    agent_id: str                               # "intent_agent"
    name: str                                   # "意图识别Agent"
    description: str
    version: str = "1.0.0"
    skills: list[AgentSkill] = []
    input_schema: dict = {}
    output_schema: dict = {}
    requires_human_review: bool = False
    max_risk_level: str = "high"                # "low" | "medium" | "high"
    timeout_seconds: int = 30
    retry_policy: str = "no_retry"              # "no_retry" | "retry_on_error" | "escalate_to_human"
    dependencies: list[str] = []                # agent_ids this agent depends on
