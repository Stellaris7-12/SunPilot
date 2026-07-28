"""PageAgent/SunPilot LLM proxy endpoints (``/api/llm/proxy/*``).

Thin transport layer over the Ali/Qwen gateway. Never mixes with the
business-agent ``LLM_*`` client. The upstream model is forced from server
config so the browser cannot pick an arbitrary model.
"""

import json
import logging

from fastapi import APIRouter, HTTPException, Request

from ticket_agent.config import PAGE_AGENT_LLM_TIMEOUT
from ticket_agent.core.llm_clients import get_llm_proxy_client, llm_proxy_config_response, page_agent_llm_config

logger = logging.getLogger(__name__)

router = APIRouter(tags=["llm-proxy"])


async def _proxy_llm_chat_completion(request: Request) -> dict:
    try:
        payload = await request.json()
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON body") from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Request body must be a JSON object")

    payload = dict(payload)
    payload["model"] = page_agent_llm_config["model"]
    extra_body = dict(payload.pop("extra_body", {}) or {})
    for provider_field in ("enable_thinking",):
        if provider_field in payload:
            extra_body[provider_field] = payload.pop(provider_field)
    if extra_body:
        payload["extra_body"] = extra_body

    try:
        response = await get_llm_proxy_client().chat.completions.create(
            **payload,
            timeout=PAGE_AGENT_LLM_TIMEOUT,
        )
    except Exception as exc:
        logger.exception("PageAgent LLM proxy request failed")
        upstream_message = getattr(getattr(exc, "response", None), "text", "") or str(exc)
        raise HTTPException(
            status_code=502,
            detail=f"LLM proxy request failed: {type(exc).__name__}: {upstream_message[:500]}",
        ) from exc

    return response.model_dump(mode="json", exclude_none=True)


@router.post("/api/llm/proxy/chat/completions")
async def proxy_llm_chat_completion(request: Request):
    return await _proxy_llm_chat_completion(request)


@router.post("/api/llm/proxy")
async def proxy_llm_chat_completion_compat(request: Request):
    return await _proxy_llm_chat_completion(request)


@router.get("/api/llm/proxy/config")
async def get_llm_proxy_config():
    return llm_proxy_config_response()
