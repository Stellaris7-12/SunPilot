"""VerifyAgent: field completeness, risk assessment, and routing decision."""

import logging

from agents.base import BaseAgent

logger = logging.getLogger(__name__)


REQUIRED_FIELDS = {
    "COUPON_REISSUE": ["customerId", "couponType", "reason"],
    "CUSTOMER_ADDRESS_UPDATE": ["customerId", "newAddress", "verifyStatus"],
    "TRANSACTION_DISPUTE": ["customerId", "transactionDate", "amount", "merchantName"],
    "UNKNOWN": [],
}

MISSING_VALUES = {"", "未提取", "未提供", "N/A", "UNKNOWN", None}

VERIFY_SYSTEM_PROMPT = """你是信用卡工单风控审核专家。
请根据工单、意图识别和字段抽取结果，以 JSON 返回：
{
  "risk_level": "low" | "medium" | "high",
  "risk_decision": "一句话风险判断",
  "can_auto_proceed": true | false,
  "additional_checks": [{"label": "检查项", "status": "通过" | "待确认" | "需复核" | "已拦截"}]
}

规则：
- low: 常规业务操作，字段完整，无明显异常。
- medium: 涉及敏感信息修改、身份核验或需操作员确认。
- high: 交易争议、疑似盗刷、大额或合规敏感场景，需人工介入。
只返回 JSON。"""


class VerifyAgent(BaseAgent):
    async def run(self, input_data: dict, context: dict = None) -> dict:
        ticket = input_data.get("ticket", {})
        intent = input_data.get("intent", {})
        fields = input_data.get("fields", [])
        tool_result = input_data.get("tool_result")

        intent_type = intent.get("type", "UNKNOWN")
        ticket_risk = ticket.get("risk_level", "low")
        fields_dict = {f.get("name"): f.get("value") for f in fields}

        checks = []
        required = REQUIRED_FIELDS.get(intent_type, [])
        missing = [
            name for name in required
            if fields_dict.get(name) in MISSING_VALUES
        ]
        if missing:
            checks.append({
                "label": f"必填字段缺失: {', '.join(missing)}",
                "status": "待补充",
            })
            return {
                "checks": checks,
                "risk_level": ticket_risk,
                "risk_decision": "信息不足，需补充必填字段后继续处理",
                "can_auto_proceed": False,
                "missing_fields": missing,
                "needs_more_info": True,
            }

        checks.append({"label": "必填字段完整", "status": "通过"})

        confidence = intent.get("confidence", 0)
        if confidence < 0.7:
            checks.append({
                "label": f"意图识别置信度偏低({confidence:.0%})",
                "status": "待确认",
            })
        else:
            checks.append({"label": "意图识别可信", "status": "通过"})

        if ticket_risk == "high":
            checks.append({"label": "工单标记为高风险，建议转人工", "status": "已拦截"})
            return {
                "checks": checks,
                "risk_level": "high",
                "risk_decision": "高风险工单，已转人工审核",
                "can_auto_proceed": False,
                "missing_fields": [],
                "needs_more_info": False,
            }

        if intent_type == "TRANSACTION_DISPUTE":
            checks.append({"label": "交易争议需人工复核", "status": "需复核"})
            return {
                "checks": checks,
                "risk_level": "high",
                "risk_decision": "交易争议类工单，建议转人工复核",
                "can_auto_proceed": False,
                "missing_fields": [],
                "needs_more_info": False,
            }

        if ticket_risk == "medium" or intent_type == "CUSTOMER_ADDRESS_UPDATE":
            logger.info("[VerifyAgent] LLM assessment for ticket_risk=%s", ticket_risk)
            user_prompt = f"""工单风险等级: {ticket_risk}
意图: {intent_type} - {intent.get('label', '')}
字段: {fields_dict}
工具执行结果: {tool_result or '未执行'}
规则检查: {checks}

请评估风险等级。"""
            llm_result = await self.call_llm(VERIFY_SYSTEM_PROMPT, user_prompt)

            for c in llm_result.get("additional_checks", []):
                checks.append(c)

            return {
                "checks": checks,
                "risk_level": llm_result.get("risk_level", ticket_risk),
                "risk_decision": llm_result.get("risk_decision", "中风险，需人工确认后执行"),
                "can_auto_proceed": llm_result.get("can_auto_proceed", ticket_risk != "high"),
                "missing_fields": [],
                "needs_more_info": False,
            }

        checks.append({"label": "操作需人工终审确认", "status": "待确认"})
        return {
            "checks": checks,
            "risk_level": ticket_risk,
            "risk_decision": "低风险，可进入人工终审结单",
            "can_auto_proceed": True,
            "missing_fields": [],
            "needs_more_info": False,
        }
