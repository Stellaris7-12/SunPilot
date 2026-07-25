"""Agent Registry — loads and manages A2A-lite Agent Cards.

Provides agent discovery for the orchestrator. Each agent's card
describes its capabilities, dependencies, and operational constraints.
"""

import json
import logging
from pathlib import Path
from models.agent_card import AgentCard

logger = logging.getLogger(__name__)

AGENT_CARDS_JSON = Path(__file__).resolve().parent.parent / "data" / "agent_cards.json"


class AgentRegistry:
    """Registry of all available agents, loaded from agent_cards.json.

    Provides discovery by agent_id and startup validation of declared
    dependencies.  The concrete execution order lives in
    ``Orchestrator.process_ticket``; this registry does not derive it.
    """

    def __init__(self):
        with open(AGENT_CARDS_JSON, "r", encoding="utf-8") as f:
            cards_data = json.load(f)
        self._cards: dict[str, AgentCard] = {
            c["agent_id"]: AgentCard(**c) for c in cards_data
        }
        self._validate_dependencies()
        logger.info(
            f"AgentRegistry loaded {len(self._cards)} agents: "
            f"{list(self._cards.keys())}"
        )

    def _validate_dependencies(self) -> None:
        """Fail fast if any card declares a dependency on an unknown agent.

        The orchestration order is defined explicitly in
        ``Orchestrator.process_ticket``; the ``dependencies`` field is metadata
        used for documentation and integrity checks rather than to derive the
        run order.  We still verify every declared dependency resolves to a
        registered agent so a typo or a removed agent surfaces at startup
        instead of mid-pipeline.
        """
        missing: list[str] = []
        for agent_id, card in self._cards.items():
            for dep in card.dependencies:
                if dep not in self._cards:
                    missing.append(f"{agent_id} -> {dep}")
        if missing:
            raise ValueError(
                "Agent card dependency validation failed; unknown dependencies: "
                + ", ".join(missing)
            )

    def get(self, agent_id: str) -> AgentCard | None:
        """Look up an agent by its id."""
        return self._cards.get(agent_id)

    def get_all(self) -> list[AgentCard]:
        """Return all registered agent cards."""
        return list(self._cards.values())

    def list_for_review(self) -> list[AgentCard]:
        """Return agents that require human review of their output."""
        return [c for c in self._cards.values() if c.requires_human_review]


# Module-level singleton
agent_registry = AgentRegistry()
