"""VerifyAgent — risk assessment, field completeness check, routing decision."""

import logging
from models.ticket import RiskLevel
from agents.base import BaseAgent
from models.agent_card import AgentCard

logger = logging.getLogger(__name__)

# Required fields per intent type
_REQUIRED_FIELDS = {
    "COUPON_REISSUE": ["customerId", "couponType", "reason"],
    "CUSTOMER_ADDRESS_UPDATE": ["customerId", "newAddress", "verifyStatus"],
    "TRANSACTION_DISPUTE": ["customerId", "transactionDate", "amount", "merchantName"],
    "UNKNOWN": [],
}

VERIFY_SYSTEM_PROMPT = """你是一个信用卡风控审核专家。根据工单信息、意图识别、字段抽取和工具执行结果，评估工单的风险等级和处理建议。

请以JSON格式返回：
{
  "risk_level": "low" | "medium" | "high",
  "risk_decision": "风险判断说明（一句话）",
  "can_auto_proceed": true | false,
  "additional_checks": [{"label": "检查项", "status": "通过" | "待确认" | "需复核" | "已拦截"}]
}

风险判断标准：
- low: 常规业务操作（补券、简单信息修改），字段完整，无异常
- medium: 涉及客户敏感信息修改、身份核验、金额操作
- high: 涉及交易争议、盗刷嫌疑、大额操作，需要人工介入

只返回JSON。"""


class VerifyAgent(BaseAgent):
    """Verify field completeness and assess risk level.

    Dual execution path:
    1. Rule-based: Check required fields, inherited ticket risk
    2. LLM-based: Nuanced risk assessment for medium/high cases

    Input: {"ticket": {...}, "intent": {...}, "fields": [...], "tool_result": {...}}
    Output: {"checks": [...], "risk_level": "low", "risk_decision": "...", "can_auto_proceed": true}
    """

    async def run(self, input_data: dict, context: dict = None) -> dict:
        ticket = input_data.get("ticket", {})
        intent = input_data.get("intent", {})
        fields = input_data.get("fields", [])
        tool_result = input_data.get("tool_result")

        intent_type = intent.get("type", "UNKNOWN")
        ticket_risk = ticket.get("risk_level", "low")

        # === Rule-based checks (always runs first) ===
        checks = []

        # Check 1: Required fields completeness
        required = _REQUIRED_FIELDS.get(intent_type, [])
        fields_dict = {f["name"]: f["value"] for f in fields}
        missing = [
            name for name in required
            if fields_dict.get(name, "未提及") == "未提及"
        ]
        if missing:
            checks.append({
                "label": f"必填字段缺失: {', '.join(missing)}",
                "status": "需复核"
            })
        else:
            checks.append({"label": "必填字段完整", "status": "通过"})

        # Check 2: Intent confidence
        confidence = intent.get("confidence", 0)
        if confidence < 0.7:
            checks.append({
                "label": f"意图识别置信度偏低 ({confidence:.0%})",
                "status": "待确认"
            })
        else:
            checks.append({"label": "意图识别可信", "status": "通过"})

        # Check 3: Inherited risk from ticket
        if ticket_risk == "high":
            checks.append({"label": "工单标记为高风险，建议转人工", "status": "已拦截"})
            return {
                "checks": checks,
                "risk_level": "high",
                "risk_decision": "高风险工单，已转人工审核",
                "can_auto_proceed": False,
            }

        # Check 4: Transaction dispute always needs human review
        if intent_type == "TRANSACTION_DISPUTE":
            checks.append({"label": "交易争议需人工复核", "status": "需复核"})
            return {
                "checks": checks,
                "risk_level": "high",
                "risk_decision": "交易争议类工单，建议转人工复核",
                "can_auto_proceed": False,
            }

        # === LLM risk assessment for nuanced cases ===
        if ticket_risk == "medium" or intent_type == "CUSTOMER_ADDRESS_UPDATE":
            logger.info(f"[VerifyAgent] LLM assessment for ticket_risk={ticket_risk}")
            user_prompt = f"""工单风险等级: {ticket_risk}
意图: {intent_type} - {intent.get('label', '')}
字段: {fields_dict}
工具执行结果: {tool_result or '未执行'}
规则检查: {checks}

请评估风险等级。"""
            llm_result = await self.call_llm(VERIFY_SYSTEM_PROMPT, user_prompt)

            # Merge LLM additional checks
            for c in llm_result.get("additional_checks", []):
                checks.append(c)

            risk_level = llm_result.get("risk_level", ticket_risk)
            can_auto = llm_result.get("can_auto_proceed", ticket_risk != "high")
            risk_decision = llm_result.get("risk_decision", "")

            return {
                "checks": checks,
                "risk_level": risk_level,
                "risk_decision": risk_decision,
                "can_auto_proceed": can_auto,
            }

        # Default for low risk
        checks.append({"label": "操作需人工终审确认", "status": "待确认"})
        return {
            "checks": checks,
            "risk_level": ticket_risk,
            "risk_decision": "低风险，可人工确认结单",
            "can_auto_proceed": True,
        }
