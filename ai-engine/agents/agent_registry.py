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

    Provides discovery by agent_id and dependency-order sorting for
    the orchestrator to determine execution order.
    """

    def __init__(self):
        with open(AGENT_CARDS_JSON, "r", encoding="utf-8") as f:
            cards_data = json.load(f)
        self._cards: dict[str, AgentCard] = {
            c["agent_id"]: AgentCard(**c) for c in cards_data
        }
        logger.info(
            f"AgentRegistry loaded {len(self._cards)} agents: "
            f"{list(self._cards.keys())}"
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

    def get_execution_order(self) -> list[str]:
        """Return agent_ids in topological dependency order.

        Uses a simple approach: agents with no dependencies come first,
        followed by agents whose dependencies are already in the list.
        """
        ordered = []
        remaining = set(self._cards.keys())

        while remaining:
            added = False
            for agent_id in sorted(remaining):
                card = self._cards[agent_id]
                if all(dep in ordered for dep in card.dependencies):
                    ordered.append(agent_id)
                    remaining.remove(agent_id)
                    added = True
                    break
            if not added:
                # Circular dependency or missing dep — add remaining in any order
                logger.warning(f"Could not resolve dependencies for: {remaining}")
                ordered.extend(sorted(remaining))
                break

        logger.info(f"Agent execution order: {ordered}")
        return ordered


# Module-level singleton
agent_registry = AgentRegistry()
