"""
Base agent module — provides LLMClient and BaseAgent abstract class.

All 5 specialised agents (IntentAgent, FieldExtractionAgent, VerificationAgent,
DecisionAgent, HumanReviewAgent) inherit from BaseAgent.
"""

import json
import logging
from abc import ABC, abstractmethod

from openai import AsyncOpenAI

from config import (
    LLM_BASE_URL,
    LLM_API_KEY,
    LLM_MODEL,
    LLM_MAX_TOKENS,
    LLM_TEMPERATURE,
    LLM_TIMEOUT,
)
from models.agent_card import AgentCard

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LLM Client (module-level singleton)
# ---------------------------------------------------------------------------
client = AsyncOpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY)


# ===================================================================
# BaseAgent
# ===================================================================
class BaseAgent(ABC):
    """Abstract base class for all agents in the multi-agent system.

    Each agent receives its own AgentCard at construction time and uses it
    to self-describe its capabilities.  Subclasses must implement ``run()``.
    """

    # ------------------------------------------------------------------
    def __init__(self, agent_card: AgentCard) -> None:
        """Initialise the agent with its A2A-lite agent card.

        Parameters
        ----------
        agent_card : AgentCard
            The self-describing metadata card for this agent.
        """
        self._agent_card = agent_card

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------
    @property
    def agent_card(self) -> AgentCard:
        """Read-only access to the agent's A2A-lite card."""
        return self._agent_card

    # ------------------------------------------------------------------
    # LLM helpers
    # ------------------------------------------------------------------
    async def call_llm(self, system_prompt: str, user_prompt: str) -> dict:
        """Call the LLM with a system + user prompt and return parsed JSON.

        The call is made with ``response_format={"type": "json_object"}`` so
        the model is instructed to return valid JSON.  If the initial JSON
        parse fails, the LLM is retried **once** before giving up.

        Parameters
        ----------
        system_prompt : str
            Instructions that set the model's behaviour.
        user_prompt : str
            The concrete task / input data for this invocation.

        Returns
        -------
        dict
            Parsed JSON response from the model.

        Raises
        ------
        json.JSONDecodeError
            If JSON parsing fails after the single retry.
        """
        payload = {
            "model": LLM_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": LLM_TEMPERATURE,
            "max_tokens": LLM_MAX_TOKENS,
            "timeout": LLM_TIMEOUT,
        }

        logger.info(
            "Calling LLM (model=%s, agent=%s, temperature=%.2f, max_tokens=%d, timeout=%ds)",
            LLM_MODEL,
            self._agent_card.agent_id,
            LLM_TEMPERATURE,
            LLM_MAX_TOKENS,
            LLM_TIMEOUT,
        )

        for attempt in range(2):  # initial call + 1 retry
            response = await client.chat.completions.create(**payload)
            raw_text = response.choices[0].message.content

            try:
                result: dict = json.loads(raw_text)
                return result  # success — bail out
            except json.JSONDecodeError:
                if attempt == 0:
                    logger.warning(
                        "JSON parse failed for agent '%s' — retrying once. "
                        "Raw response (first 200 chars): %.200s",
                        self._agent_card.agent_id,
                        raw_text,
                    )
                else:
                    # Second failure — let it propagate so callers can handle it
                    logger.error(
                        "JSON parse failed again for agent '%s' after retry. "
                        "Raw response: %s",
                        self._agent_card.agent_id,
                        raw_text,
                    )
                    raise

        # Should never reach here, but keep the type checker happy
        raise RuntimeError("Unexpected: call_llm exceeded retry limit")

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------
    @abstractmethod
    async def run(self, input_data: dict, context: dict = None) -> dict:
        """Execute the agent's core logic.

        Every concrete agent **must** override this method.

        Parameters
        ----------
        input_data : dict
            The primary input payload for this agent (e.g. ticket fields).
        context : dict, optional
            Additional context such as upstream agent results, by default None.

        Returns
        -------
        dict
            Agent-specific output dict (see each agent's docstring).

        Raises
        ------
        NotImplementedError
            If the subclass does not provide an implementation.
        """
        raise NotImplementedError(
            f"Agent '{self._agent_card.agent_id}' must implement run()"
        )

    # ------------------------------------------------------------------
    # Helpers for subclasses
    # ------------------------------------------------------------------
    def _build_user_prompt(self, input_data: dict) -> str:
        """Format ``input_data`` as a human-readable JSON user-prompt string.

        Subclasses may override this to inject extra formatting or
        domain-specific instructions.

        Parameters
        ----------
        input_data : dict
            The data to serialise.

        Returns
        -------
        str
            Pretty-printed JSON string.
        """
        return json.dumps(input_data, ensure_ascii=False, indent=2)
