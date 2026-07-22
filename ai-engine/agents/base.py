"""
Base agent module - provides LLMClient and BaseAgent abstract class.

All business agents (Classifier, Intake, Escalation, Resolution, Notification)
inherit from BaseAgent.
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
    async def call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        tools: list[dict] | None = None,
        tool_choice: str | dict | None = None,
    ) -> dict:
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
            "temperature": LLM_TEMPERATURE,
            "max_tokens": LLM_MAX_TOKENS,
            "timeout": LLM_TIMEOUT,
        }
        if tools:
            payload["tools"] = tools
            if tool_choice is not None:
                payload["tool_choice"] = tool_choice
        else:
            payload["response_format"] = {"type": "json_object"}

        logger.info(
            "Calling LLM (model=%s, agent=%s, temperature=%.2f, max_tokens=%d, timeout=%ds, tools=%d)",
            LLM_MODEL,
            self._agent_card.agent_id,
            LLM_TEMPERATURE,
            LLM_MAX_TOKENS,
            LLM_TIMEOUT,
            len(tools or []),
        )

        for attempt in range(2):  # initial call + 1 retry
            response = await client.chat.completions.create(**payload)
            message = response.choices[0].message
            raw_text = message.content or ""
            normalized_tool_calls = _normalize_llm_tool_calls(
                getattr(message, "tool_calls", None)
            )

            if tools:
                content_json = _try_parse_json(raw_text)
                if normalized_tool_calls or content_json is not None:
                    return {
                        "tool_calls": normalized_tool_calls,
                        "content_json": content_json or {},
                        "raw_content": raw_text,
                    }
                if attempt == 0:
                    logger.warning(
                        "Tool call parse failed for agent '%s' - retrying once. "
                        "Raw response (first 200 chars): %.200s",
                        self._agent_card.agent_id,
                        raw_text,
                    )
                    continue
                logger.error(
                    "Tool call parse failed again for agent '%s' after retry. "
                    "Raw response: %s",
                    self._agent_card.agent_id,
                    raw_text,
                )
                return {"tool_calls": [], "content_json": {}, "raw_content": raw_text}

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
            The primary input payload for this business agent.
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


def _try_parse_json(raw_text: str) -> dict | None:
    if not raw_text:
        return None
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else {"value": parsed}


def _normalize_llm_tool_calls(tool_calls) -> list[dict]:
    normalized = []
    for call in tool_calls or []:
        function = getattr(call, "function", None)
        name = getattr(function, "name", "") if function else ""
        arguments = getattr(function, "arguments", "") if function else ""
        parsed_arguments = _try_parse_json(arguments) if isinstance(arguments, str) else None
        normalized.append({
            "id": getattr(call, "id", ""),
            "type": getattr(call, "type", "function"),
            "function": {
                "name": name,
                "arguments": parsed_arguments if parsed_arguments is not None else arguments,
            },
        })
    return normalized
