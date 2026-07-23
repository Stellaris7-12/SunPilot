"""IntakeAgent - receive ticket text and extract required business fields."""

import logging

from agents.base import BaseAgent
from models.workflow import workflow_scenario

logger = logging.getLogger(__name__)

_FIELD_SCHEMAS = {
    "COUPON_REISSUE": [
        ("customerId", "客户号"),
        ("phone", "手机号（脱敏后）"),
        ("couponType", "券类型描述"),
        ("reason", "补发原因"),
    ],
    "CUSTOMER_ADDRESS_UPDATE": [
        ("customerId", "客户号"),
        ("phone", "手机号（脱敏后）"),
        ("newAddress", "新地址"),
        ("verifyStatus", "身份核验状态"),
    ],
    "TRANSACTION_DISPUTE": [
        ("customerId", "客户号"),
        ("transactionDate", "交易日期"),
        ("amount", "交易金额"),
        ("merchantName", "商户名称"),
        ("disputeReason", "争议原因"),
    ],
    "BENEFIT_QUERY": [
        ("customerId", "客户号"),
        ("phone", "手机号（脱敏后）"),
        ("benefitCode", "权益或活动编码"),
        ("queryReason", "查询原因"),
    ],
    "APPLICATION_PROGRESS_QUERY": [
        ("customerId", "客户号"),
        ("phone", "手机号（脱敏后）"),
        ("applicationNo", "申请单号或业务流水号"),
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

        system_prompt = _build_intake_prompt(intent_type, intent_label, workflow_config)
        user_prompt = f"工单内容：\n\n{ticket_content}"

        logger.info("[IntakeAgent] Extracting fields for intent=%s", intent_type)
        result = await self.call_llm(system_prompt, user_prompt)

        if "fields" not in result:
            result["fields"] = []

        logger.info("[IntakeAgent] Extracted %s fields", len(result["fields"]))
        return result
