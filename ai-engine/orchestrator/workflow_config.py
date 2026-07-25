"""Workflow configuration loader for business-agent orchestration."""

import json
import logging
from functools import lru_cache
from pathlib import Path

from models.workflow import WorkflowConfig


WORKFLOW_CONFIG_JSON = Path(__file__).resolve().parent.parent / "data" / "workflow_config.json"

logger = logging.getLogger(__name__)

# workflow_config.json 是场景配置的唯一权威来源（single source of truth）。
# 这里仅保留一个最小空壳，作为“文件缺失/损坏时可辨识的结构参考”，
# 而**不再**作为静默回退：任何加载/校验失败都会 fail-fast 抛出，
# 以免运行在一份与 JSON 漂移的内置副本上。
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


@lru_cache(maxsize=1)
def load_workflow_config() -> dict:
    """Load and validate the workflow config from disk (fail-fast).

    ``workflow_config.json`` is the authoritative source of scenario config.
    If the file is missing, malformed, or fails schema validation we raise
    immediately rather than silently falling back to a built-in copy that may
    have drifted from the JSON — a drifted config would corrupt field maps,
    gating, and closure suggestions in ways that are hard to diagnose.
    """
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


def get_scenario_config(intent_type: str) -> dict:
    """Return scenario config, falling back to UNKNOWN."""
    config = load_workflow_config()
    scenarios = config.get("scenarios", {})
    return scenarios.get(intent_type) or scenarios.get("UNKNOWN", {})
