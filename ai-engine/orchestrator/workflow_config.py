"""Workflow configuration loader for business-agent orchestration."""

import json
import logging
from pathlib import Path
from threading import Lock

from models.workflow import WorkflowConfig


WORKFLOW_CONFIG_JSON = Path(__file__).resolve().parent.parent / "data" / "workflow_config.json"

logger = logging.getLogger(__name__)

# P2-12: Remove @lru_cache, use manual cache + thread-safe reload
_config_cache: dict | None = None
_config_lock = Lock()

MINIMAL_WORKFLOW_CONFIG = {
    "default_workflow": "unknown_flow",
    "scenarios": {
        "UNKNOWN": {
            "workflow_name": "unknown_flow",
            "label": "未知场景",
            "fields": [
                {"name": "customerId", "label": "客户号"},
                {"name": "phone", "label": "手机号"},
                {"name": "summary", "label": "诉求摘要"},
            ],
            "required_fields": [],
            "recommended_tool": "",
            "candidateTools": ["customer.lookup", "ticket.history-search", "knowledge.policy-search"],
            "classifierHint": "",
            "requires_human_confirmation": True,
            "notification_template": "当前诉求无法稳定识别，建议补充信息或转人工处理。",
        },
    },
}


def _load_and_validate() -> dict:
    """Load and validate config file (internal, no cache)."""
    try:
        with open(WORKFLOW_CONFIG_JSON, "r", encoding="utf-8") as file:
            payload = json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("Failed to read workflow config at %s: %s", WORKFLOW_CONFIG_JSON, exc)
        raise RuntimeError(
            f"无法读取工作流配置文件 {WORKFLOW_CONFIG_JSON}: {exc}"
        ) from exc

    try:
        return WorkflowConfig.model_validate(payload).to_runtime_dict()
    except ValueError as exc:
        logger.error("Workflow config validation failed: %s", exc)
        raise RuntimeError(f"工作流配置校验失败: {exc}") from exc


def load_workflow_config() -> dict:
    """Load and validate the workflow config from disk (with cache).

    P2-12: Support hot reload, cache after first call, use reload_workflow_config() to refresh.
    """
    global _config_cache
    if _config_cache is not None:
        return _config_cache

    with _config_lock:
        if _config_cache is not None:
            return _config_cache
        _config_cache = _load_and_validate()
        return _config_cache


def reload_workflow_config() -> dict:
    """P2-12: Reload config file, clear cache.

    Keep old cache on failure to avoid service unavailable.
    """
    global _config_cache
    with _config_lock:
        try:
            new_config = _load_and_validate()
            _config_cache = new_config
            logger.info("Workflow config reloaded successfully from %s", WORKFLOW_CONFIG_JSON)
            return new_config
        except Exception as exc:
            logger.error("Failed to reload workflow config, keeping old cache: %s", exc)
            raise


def get_scenario_config(intent_type: str) -> dict:
    """Return scenario config, falling back to UNKNOWN."""
    config = load_workflow_config()
    scenarios = config.get("scenarios", {})
    return scenarios.get(intent_type) or scenarios.get("UNKNOWN", {})
