"""P2-10: 配置驱动的字段抽取引擎，替换硬编码的 elif 链。"""

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def extract_field_by_rule(
    field_name: str,
    field_config: dict[str, Any],
    transcript: str,
    context: dict[str, Any],
) -> str | None:
    """根据字段配置的 extractRule 从 transcript 中抽取值。

    支持的 extractRule 类型：
    - {"type": "regex", "pattern": "..."}  — 正则抽取
    - {"type": "context", "source": "key"} — 从 context 字典获取
    - {"type": "keyword", "keyword": "x", "trueValue": "y", "falseValue": "z"} — 关键词判断
    - {"type": "literal", "value": "..."} — 固定值
    - null / 不存在 — 返回 None，依赖 LLM merge
    """
    extract_rule = field_config.get("extractRule")
    if not extract_rule:
        return None

    rule_type = extract_rule.get("type")

    if rule_type == "regex":
        pattern = extract_rule.get("pattern")
        if not pattern:
            return None
        try:
            match = re.search(pattern, transcript, flags=re.IGNORECASE)
            if match:
                # 如果正则有捕获组，返回第一个捕获组；否则返回整个匹配
                return match.group(1) if match.groups() else match.group(0)
        except re.error as e:
            logger.warning("Invalid regex pattern for field %s: %s (%s)", field_name, pattern, e)
        return None

    elif rule_type == "context":
        source_key = extract_rule.get("source", field_name)
        value = context.get(source_key)
        if value:
            # 支持 formatter（如 "尾号{value}"）
            formatter = extract_rule.get("formatter")
            if formatter and "{value}" in formatter:
                return formatter.replace("{value}", str(value))
        return value

    elif rule_type == "keyword":
        keyword = extract_rule.get("keyword", "")
        true_value = extract_rule.get("trueValue", "是")
        false_value = extract_rule.get("falseValue", "否")
        return true_value if keyword and keyword in transcript else false_value

    elif rule_type == "literal":
        return extract_rule.get("value")

    else:
        logger.warning("Unknown extractRule type for field %s: %s", field_name, rule_type)
        return None


def extract_specific_fields(
    scenario_name: str,
    scenario_config: dict[str, Any],
    transcript: str,
    context: dict[str, Any],
) -> dict[str, str]:
    """P2-10: 配置驱动的字段抽取，替换 main.py 的巨型 elif 链。

    Args:
        scenario_name: 场景名称（如"伪冒预防"）
        scenario_config: 该场景的 workflow_config
        transcript: 通话记录
        context: 上下文（如 draft、call_meta）

    Returns:
        抽取的字段 dict
    """
    specific_fields = scenario_config.get("specificFields", [])
    extracted = {}

    for field_config in specific_fields:
        field_name = field_config.get("name")
        if not field_name:
            continue

        # 先尝试配置驱动抽取
        value = extract_field_by_rule(field_name, field_config, transcript, context)

        # 如果配置未抽取到，且 context 中有该字段，使用 context 值（兜底）
        if value is None and field_name in context:
            value = context[field_name]

        # 如果还是没有，使用字段的 default（如果配置了）
        if value is None:
            value = field_config.get("default", "")

        extracted[field_name] = str(value) if value is not None else ""

    return extracted


def extract_common_fields(
    workflow_config: dict[str, Any],
    transcript: str,
    context: dict[str, Any],
) -> dict[str, str]:
    """从 workflow_config.commonFields 提取通用字段。

    Args:
        workflow_config: 完整的 workflow_config
        transcript: 通话记录
        context: 上下文（如 call_meta）

    Returns:
        提取的通用字段 dict
    """
    common_fields = workflow_config.get("commonFields", [])
    extracted = {}

    for field_config in common_fields:
        field_name = field_config.get("name")
        if not field_name:
            continue

        # 先尝试配置驱动抽取
        value = extract_field_by_rule(field_name, field_config, transcript, context)

        # 如果配置未抽取到，且 context 中有该字段，使用 context 值（兜底）
        if value is None and field_name in context:
            value = context[field_name]

        # 如果还是没有，使用字段的 default（如果配置了）
        if value is None:
            value = field_config.get("default", "")

        extracted[field_name] = str(value) if value is not None else ""

    return extracted
