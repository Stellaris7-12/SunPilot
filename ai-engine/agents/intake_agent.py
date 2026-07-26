"""IntakeAgent - receive ticket text and extract required business fields."""

import logging
import re

from agents.base import BaseAgent
from models.workflow import workflow_scenario

logger = logging.getLogger(__name__)

def _fields_from_config(intent_type: str, workflow_config: dict) -> list[tuple[str, str]]:
    scenario_config = workflow_scenario(workflow_config, intent_type)
    return [
        (field.name, field.label or field.name)
        for field in scenario_config.fields
    ]


def _build_intake_prompt(intent_type: str, intent_label: str, workflow_config: dict) -> str:
    fields = _fields_from_config(intent_type, workflow_config)
    field_descriptions = "\n".join(f"- {name}: {label}" for name, label in fields)

    return f"""你是一个信用卡工单接单与信息提取专家。
当前工单场景为：{intent_label}（{intent_type}）。
请从工单内容中抽取以下字段：
{field_descriptions}

以 JSON 格式返回，包含 fields 数组：
{{
  "fields": [
    {{"label": "客户号", "name": "customerId", "value": "C10001"}},
    {{"label": "手机号", "name": "phone", "value": "138****8888"}}
  ]
}}

对于无法从工单中抽取的字段，value 设为 "未提供"。只返回 JSON。"""


class IntakeAgent(BaseAgent):
    """Extract structured business fields from ticket content."""

    def build_follow_up_prompt(self, missing_fields: list[dict]) -> str:
        """Build a customer-facing prompt for fields needed before tool execution."""
        if not missing_fields:
            return "当前信息不足，请补充关键业务信息后继续处理。"
        lines = []
        for item in missing_fields:
            example = item.get("example", "")
            suffix = f"，示例：{example}" if example else ""
            lines.append(f"- {item.get('description') or item.get('name')}{suffix}")
        return "为继续办理该工单，请补充以下信息：\n" + "\n".join(lines)

    async def run(self, input_data: dict, context: dict = None) -> dict:
        ticket_content = input_data.get("ticket_content", "")
        intent_type = input_data.get("intent_type", "UNKNOWN")
        intent_label = input_data.get("intent_label", "未知场景")
        workflow_config = input_data.get("workflow_config", {})

        deterministic_fields = _deterministic_fields(
            ticket_content,
            _fields_from_config(intent_type, workflow_config),
            workflow_config,
            intent_type,
        )
        required = workflow_scenario(workflow_config, intent_type).required_fields
        missing = _missing_required(deterministic_fields, required)

        # Fast lane: rules extracted every required field (or none are required, e.g. UNKNOWN).
        if deterministic_fields and not missing:
            logger.info(
                "[IntakeAgent] Deterministic fast-lane extracted %s fields (all required present)",
                len(deterministic_fields),
            )
            return {"fields": deterministic_fields, "extraction_mode": "deterministic"}

        # Slow lane: required fields are missing -> let the LLM fill the gaps, then merge.
        system_prompt = _build_intake_prompt(intent_type, intent_label, workflow_config)
        user_prompt = f"工单内容：\n\n{ticket_content}"

        logger.info(
            "[IntakeAgent] Rules missing required fields %s for intent=%s, falling back to LLM",
            missing,
            intent_type,
        )
        result = await self.call_llm(system_prompt, user_prompt)
        llm_fields = result.get("fields") if isinstance(result, dict) else None

        merged = _merge_fields(deterministic_fields, llm_fields or [])
        logger.info("[IntakeAgent] LLM-augmented extraction produced %s fields", len(merged))
        return {"fields": merged, "extraction_mode": "llm_augmented"}


_EMPTY_VALUES = {"", "未提供", "None", "none", "null"}


def _is_present(value) -> bool:
    return bool(value) and str(value).strip() not in _EMPTY_VALUES


def _missing_required(fields: list[dict], required: list[str]) -> list[str]:
    """Return the required field names that were not extracted with a real value."""
    if not required:
        return []
    present = {f["name"] for f in fields if _is_present(f.get("value"))}
    return [name for name in required if name not in present]


def _merge_fields(deterministic: list[dict], llm_fields: list[dict]) -> list[dict]:
    """Merge LLM output into deterministic output; LLM only fills gaps, never overrides real values."""
    by_name = {f["name"]: dict(f) for f in deterministic}
    for item in llm_fields:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not name:
            continue
        llm_value = item.get("value")
        existing = by_name.get(name)
        if existing is None:
            by_name[name] = {
                "label": item.get("label") or name,
                "name": name,
                "value": str(llm_value) if _is_present(llm_value) else "未提供",
            }
        elif not _is_present(existing.get("value")) and _is_present(llm_value):
            existing["value"] = str(llm_value)
    return list(by_name.values())


def _deterministic_fields(
    ticket_content: str,
    fields: list[tuple[str, str]],
    workflow_config: dict = None,
    intent_type: str = None,
) -> list[dict]:
    if not ticket_content or not fields:
        return []

    # Build extractRule map from workflow_config
    extract_rules = {}
    if workflow_config and intent_type:
        scenario_config = workflow_scenario(workflow_config, intent_type)
        for field in scenario_config.fields + scenario_config.specific_fields:
            if field.extract_rule:
                extract_rules[field.name] = field.extract_rule

    values = _structured_values(ticket_content, fields)
    result = []
    for name, label in fields:
        # Priority: structured_values > extractRule-based > fallback (with confidence check)
        value = values.get(name)
        if not value and name in extract_rules:
            value = _extract_by_rule(extract_rules[name], ticket_content, values)
        if not value:
            value = _fallback_extract_with_confidence(name, ticket_content)
        result.append({
            "label": label,
            "name": name,
            "value": str(value or "未提供"),
        })
    return result


_GLOBAL_LABEL_TO_NAME = {
    "标题": "title",
    "场景": "scene",
    "类目": "category",
    "子类目": "subcategory",
    "编号前缀": "orderPrefix",
    "业务类型": "bizType",
    "业务细分类型": "bizSubType",
    "接单单位": "receiveUnit",
    "规定回件日期": "deadline",
    "客户号": "customerId",
    "客户姓名": "customerName",
    "手机号": "phone",
    "卡尾号": "cardLast4",
    "风险等级": "riskLevel",
    "正文": "content",
}

# ASCII and fullwidth colons both delimit "标签：值" lines in real tickets.
_LABEL_SEP = re.compile(r"[:：]")


def _structured_values(
    ticket_content: str, fields: list[tuple[str, str]] | None = None
) -> dict[str, str]:
    # Config-derived labels take precedence so workflow_config stays the single
    # source of truth; the global map only supplements scenario-agnostic labels.
    label_to_name = dict(_GLOBAL_LABEL_TO_NAME)
    for name, label in fields or []:
        if label:
            label_to_name[label.strip()] = name
    values = {}
    for line in ticket_content.splitlines():
        if line.startswith("扩展字段.") and ":" in line:
            key, value = line.split(":", 1)
            values[key.replace("扩展字段.", "", 1).strip()] = value.strip()
            continue
        if not _LABEL_SEP.search(line):
            continue
        label, value = _LABEL_SEP.split(line, 1)
        name = label_to_name.get(label.strip())
        if name:
            values[name] = value.strip()
    return values


def _extract_by_rule(extract_rule: dict, text: str, context_values: dict) -> str:
    """Extract field value using workflow_config's extractRule."""
    rule_type = extract_rule.get("type")

    if rule_type == "regex":
        pattern = extract_rule.get("pattern")
        if not pattern:
            return ""
        match = re.search(pattern, text, flags=re.IGNORECASE)
        return match.group(1).strip() if match else ""

    elif rule_type == "literal":
        return extract_rule.get("value", "")

    elif rule_type == "keyword":
        keyword = extract_rule.get("keyword", "")
        true_value = extract_rule.get("trueValue", "")
        false_value = extract_rule.get("falseValue", "")
        return true_value if keyword and keyword in text else false_value

    elif rule_type == "context":
        source = extract_rule.get("source")
        if not source or source not in context_values:
            return ""
        value = context_values[source]
        formatter = extract_rule.get("formatter", "{value}")
        return formatter.replace("{value}", str(value))

    return ""


def _fallback_extract_with_confidence(name: str, text: str) -> str:
    """Fallback extraction with confidence checks to prevent pollution.

    Only returns a value if the match has contextual support (appears near expected labels).
    This prevents regex from matching garbage numbers in unrelated text.
    """
    # Define patterns WITH required context (labels that should appear nearby)
    patterns_with_context = {
        "customerId": {
            "pattern": r"(C\d{5,})",
            "context": ["客户号", "客户编号", "customerId"],
            "window": 20,  # characters before/after match
        },
        "phone": {
            "pattern": r"(1\d{2}\*{4}\d{4}|1\d{10})",
            "context": ["手机", "电话", "联系", "phone"],
            "window": 20,
        },
        "cardLast4": {
            "pattern": r"卡尾(?:号)?\s*(\d{4})",
            "context": [],  # pattern itself contains context
            "window": 0,
        },
        "caseNo": {
            "pattern": r"案件编号[:：]?\s*([0-9A-Z-]{6,})",
            "context": [],  # pattern itself contains context
            "window": 0,
        },
        "xdk": {
            "pattern": r"X-DK[:：]?\s*([A-Z0-9-]+)",
            "context": [],  # pattern itself contains context
            "window": 0,
        },
        "callId": {
            "pattern": r"CALLID[:：]?\s*([A-Z0-9-]+)",
            "context": [],  # pattern itself contains context
            "window": 0,
        },
    }

    config = patterns_with_context.get(name)
    if not config:
        return ""

    pattern = config["pattern"]
    required_context = config["context"]
    window = config["window"]

    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return ""

    # If no context required (pattern already contains label), return match
    if not required_context:
        return match.group(1).strip()

    # Check if any required context word appears near the match
    match_start = match.start()
    match_end = match.end()
    surrounding = text[max(0, match_start - window):min(len(text), match_end + window)]

    for ctx in required_context:
        if ctx in surrounding:
            return match.group(1).strip()

    # No context support found - likely a false positive, return empty
    logger.debug(
        "[IntakeAgent] Rejected low-confidence match for %s: '%s' (no context support)",
        name,
        match.group(0),
    )
    return ""
