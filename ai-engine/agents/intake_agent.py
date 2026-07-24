"""IntakeAgent - receive ticket text and extract required business fields."""

import logging
import re

from agents.base import BaseAgent
from models.workflow import workflow_scenario

logger = logging.getLogger(__name__)

_FIELD_SCHEMAS = {
    "协商还款": [
        ("customerId", "客户号"),
        ("customerName", "客户姓名"),
        ("phone", "手机号"),
        ("content", "发单内容"),
        ("accountNo", "账户号"),
        ("repaymentPlan", "协商方案"),
    ],
    "伪冒预防": [
        ("customerId", "客户号"),
        ("customerName", "客户姓名"),
        ("phone", "手机号"),
        ("content", "发单内容"),
        ("caseNo", "案件编号"),
        ("workOrderCategory", "工单类别"),
        ("mainDemand", "主体诉求"),
    ],
    "伪冒调查": [
        ("customerId", "客户号"),
        ("customerName", "客户姓名"),
        ("phone", "手机号"),
        ("content", "发单内容"),
        ("cardList", "卡片列表"),
        ("controlReason", "管制原因"),
        ("xdk", "X-DK"),
    ],
    "客户经营": [
        ("customerId", "客户号"),
        ("customerName", "客户姓名"),
        ("phone", "手机号"),
        ("content", "发单内容"),
        ("receiveUnit", "接单单位"),
        ("bizSubType", "业务细类"),
        ("materialType", "资料类型"),
    ],
    "市场企划": [
        ("customerId", "客户号"),
        ("customerName", "客户姓名"),
        ("phone", "手机号"),
        ("content", "发单内容"),
        ("remark", "订单号/备注"),
        ("customerFeedback", "客户反馈情况"),
        ("receiveUnit", "接单单位"),
        ("bizSubType", "业务细类"),
    ],
    "调单扣款": [
        ("customerId", "客户号"),
        ("customerName", "客户姓名"),
        ("phone", "手机号"),
        ("content", "发单内容"),
        ("workOrderCategory", "工单类别"),
        ("callPurpose", "来电目的"),
    ],
    "征信": [
        ("customerId", "客户号"),
        ("customerName", "客户姓名"),
        ("phone", "手机号"),
        ("content", "发单内容"),
        ("accountType", "账户类型"),
        ("accountNo", "账户号"),
        ("isSensitive", "是否敏感"),
        ("overdueStatus", "逾期状态"),
    ],
    "UNKNOWN": [
        ("customerId", "客户号"),
        ("phone", "手机号"),
        ("summary", "诉求摘要"),
    ],
}


def _fields_from_config(intent_type: str, workflow_config: dict) -> list[tuple[str, str]]:
    scenario_config = workflow_scenario(workflow_config, intent_type)
    configured_fields = scenario_config.fields
    if configured_fields:
        return [
            (field.name, field.label or field.name)
            for field in configured_fields
        ]
    return _FIELD_SCHEMAS.get(intent_type, _FIELD_SCHEMAS["UNKNOWN"])


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
        )
        if deterministic_fields:
            logger.info("[IntakeAgent] Deterministically extracted %s fields", len(deterministic_fields))
            return {"fields": deterministic_fields}

        system_prompt = _build_intake_prompt(intent_type, intent_label, workflow_config)
        user_prompt = f"工单内容：\n\n{ticket_content}"

        logger.info("[IntakeAgent] Extracting fields for intent=%s", intent_type)
        result = await self.call_llm(system_prompt, user_prompt)

        if "fields" not in result:
            result["fields"] = []

        logger.info("[IntakeAgent] Extracted %s fields", len(result["fields"]))
        return result


def _deterministic_fields(ticket_content: str, fields: list[tuple[str, str]]) -> list[dict]:
    if not ticket_content or not fields:
        return []
    values = _structured_values(ticket_content)
    result = []
    for name, label in fields:
        value = values.get(name) or _fallback_extract(name, ticket_content)
        result.append({
            "label": label,
            "name": name,
            "value": str(value or "未提供"),
        })
    return result


def _structured_values(ticket_content: str) -> dict[str, str]:
    label_to_name = {
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
    values = {}
    for line in ticket_content.splitlines():
        if line.startswith("扩展字段.") and ":" in line:
            key, value = line.split(":", 1)
            values[key.replace("扩展字段.", "", 1).strip()] = value.strip()
            continue
        if ":" not in line:
            continue
        label, value = line.split(":", 1)
        name = label_to_name.get(label.strip())
        if name:
            values[name] = value.strip()
    return values


def _fallback_extract(name: str, text: str) -> str:
    patterns = {
        "customerId": r"(C\d{5,})",
        "phone": r"(1\d{2}\*{4}\d{4}|1\d{10})",
        "cardLast4": r"卡尾(?:号)?\s*(\d{4})",
        "caseNo": r"案件编号[:：]?\s*([0-9A-Z-]{6,})",
        "xdk": r"X-DK[:：]?\s*([A-Z0-9-]+)",
        "remark": r"订单号[:：]?\s*([0-9A-Z-]{5,})",
        "accountNo": r"账户号[:：]?\s*([0-9A-Z*]{6,})",
        "callId": r"CALLID[:：]?\s*([A-Z0-9-]+)",
    }
    pattern = patterns.get(name)
    if not pattern:
        return ""
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return match.group(1).strip() if match else ""
