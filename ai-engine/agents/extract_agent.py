"""ExtractAgent — intent-aware structured field extraction."""

import logging
from agents.base import BaseAgent
from models.agent_card import AgentCard

logger = logging.getLogger(__name__)

# Field schemas per intent type
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


def _build_extract_prompt(intent_type: str, intent_label: str) -> str:
    """Build a system prompt listing the fields to extract for a given intent."""
    fields = _FIELD_SCHEMAS.get(intent_type, _FIELD_SCHEMAS["UNKNOWN"])
    field_descriptions = "\n".join(
        f"- {name}: {label}" for name, label in fields
    )
    field_name_list = ", ".join(f'"{name}"' for name, _ in fields)

    return f"""你是一个信用卡工单字段抽取专家。当前工单意图为：{intent_label}（{intent_type}）。

请从工单内容中抽取以下字段：
{field_descriptions}

以JSON格式返回，包含一个 fields 数组：
{{
  "fields": [
    {{"label": "客户号", "name": "customerId", "value": "C10001"}},
    {{"label": "手机号", "name": "phone", "value": "138****8888"}},
    ...
  ]
}}

对于无法从工单中抽取的字段，value 设为 "未提及"。
只返回JSON，不要包含任何其他文字。"""


class ExtractAgent(BaseAgent):
    """Extract structured business fields from ticket content.

    The extraction schema varies based on the intent type — different
    intents require different fields (e.g. coupon reissue needs couponType,
    address change needs newAddress).

    Input: {"ticket_content": "...", "intent_type": "COUPON_REISSUE"}
    Output: {"fields": [{"label": "...", "name": "...", "value": "..."}, ...]}
    """

    async def run(self, input_data: dict, context: dict = None) -> dict:
        ticket_content = input_data.get("ticket_content", "")
        intent_type = input_data.get("intent_type", "UNKNOWN")
        intent_label = input_data.get("intent_label", "未知场景")

        system_prompt = _build_extract_prompt(intent_type, intent_label)
        user_prompt = f"工单内容：\n\n{ticket_content}"

        logger.info(f"[ExtractAgent] Extracting fields for intent={intent_type}")
        result = await self.call_llm(system_prompt, user_prompt)

        # Ensure fields is present
        if "fields" not in result:
            result["fields"] = []

        logger.info(f"[ExtractAgent] Extracted {len(result['fields'])} fields")
        return result
