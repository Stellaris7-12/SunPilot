"""Simple API Key authentication for sensitive endpoints."""

import logging
import os
from typing import Annotated

from fastapi import Header, HTTPException, status

logger = logging.getLogger(__name__)

# P0-2: API Key 鉴权 - 从环境变量加载
# 生产环境必须设置 ADMIN_API_KEY，否则管理端点拒绝访问
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")

if not ADMIN_API_KEY:
    logger.warning(
        "ADMIN_API_KEY not set. Admin endpoints (/close, /config/reload) will reject all requests. "
        "Set ADMIN_API_KEY environment variable in production."
    )


def verify_admin_key(x_api_key: Annotated[str | None, Header()] = None) -> None:
    """Verify admin API key for sensitive operations.

    P0-2: 鉴权依赖 - 用于 /close 和 /config/reload 等管理端点。

    Usage in FastAPI:
        @app.post("/api/admin/...")
        async def admin_endpoint(auth: None = Depends(verify_admin_key)):
            ...

    Raises:
        HTTPException: 401 if key is missing or invalid
    """
    if not ADMIN_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin API key not configured. Set ADMIN_API_KEY environment variable.",
        )

    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if x_api_key != ADMIN_API_KEY:
        logger.warning("Invalid admin API key attempt: %s", x_api_key[:8] + "...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
