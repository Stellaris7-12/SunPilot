"""IntakeAgent - receive ticket text and extract required business fields."""

import logging

from agents.base import BaseAgent

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
    "UNKNOWN": [
        ("customerId", "客户号"),
        ("phone", "手机号"),
        ("summary", "诉求摘要"),
    ],
}


def _fields_from_config(intent_type: str, workflow_config: dict) -> list[tuple[str, str]]:
    scenarios = workflow_config.get("scenarios", {})
    scenario_config = scenarios.get(intent_type, {})
    configured_fields = scenario_config.get("fields", [])
    if configured_fields:
        return [
            (field["name"], field.get("label", field["name"]))
            for field in configured_fields
            if "name" in field
        ]
    return _FIELD_SCHEMAS.get(intent_type, _FIELD_SCHEMAS["UNKNOWN"])


def _build_intake_prompt(intent_type: str, intent_label: str, workflow_config: dict) -> str:
    fields = _fields_from_config(intent_type, workflow_config)
    field_descriptions = "\n".join(f"- {name}: {label}" for name, label in fields)

    return f"""你是一个信用卡工单接单与信息提取专家。当前工单场景为：{intent_label}（{intent_type}）。
请从工单内容中抽取以下字段：
{field_descriptions}

以JSON格式返回，包含一个 fields 数组：
{{
  "fields": [
    {{"label": "客户号", "name": "customerId", "value": "C10001"}},
    {{"label": "手机号", "name": "phone", "value": "138****8888"}}
  ]
}}

对于无法从工单中抽取的字段，value 设为 "未提供"。只返回JSON，不要包含任何其他文字。"""


class IntakeAgent(BaseAgent):
    """Extract structured business fields from ticket content."""

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
