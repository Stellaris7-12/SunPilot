"""PageAgent/SunPilot LLM proxy client.

Holds the module-level ``AsyncOpenAI`` client used exclusively by the
``/api/llm/proxy/*`` endpoints (Ali/Qwen gateway, ``PAGE_AGENT_LLM_*`` config).
Kept distinct from the business-agent ``LLM_*`` client per project boundaries.

The client is a reassignable module global; callers must fetch it via
``get_llm_proxy_client()`` at request time rather than importing the binding
directly, so a later ``reset_llm_proxy_client()`` is observed.
"""

from openai import AsyncOpenAI

from ticket_agent.config import (
    PAGE_AGENT_LLM_ALLOWED_MODELS,
    PAGE_AGENT_LLM_API_KEY,
    PAGE_AGENT_LLM_BASE_URL,
    PAGE_AGENT_LLM_MODEL,
)

page_agent_llm_config = {
    "api_key": PAGE_AGENT_LLM_API_KEY,
    "model": PAGE_AGENT_LLM_MODEL,
}

llm_proxy_client = AsyncOpenAI(
    base_url=PAGE_AGENT_LLM_BASE_URL,
    api_key=page_agent_llm_config["api_key"] or "missing-ali-api-key",
)


def get_llm_proxy_client() -> AsyncOpenAI:
    """Return the current proxy client (observes ``reset_llm_proxy_client``)."""
    return llm_proxy_client


def reset_llm_proxy_client(api_key: str) -> None:
    """Rebuild the proxy client with a new API key (currently unused)."""
    global llm_proxy_client
    llm_proxy_client = AsyncOpenAI(
        base_url=PAGE_AGENT_LLM_BASE_URL,
        api_key=api_key or "missing-ali-api-key",
    )


def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "***"
    return f"{value[:3]}***{value[-4:]}"


def llm_proxy_config_response() -> dict:
    api_key = page_agent_llm_config["api_key"]
    return {
        "baseUrl": PAGE_AGENT_LLM_BASE_URL,
        "model": page_agent_llm_config["model"],
        "allowedModels": PAGE_AGENT_LLM_ALLOWED_MODELS,
        "apiKeyConfigured": bool(api_key),
        "apiKeyPreview": mask_secret(api_key),
    }
