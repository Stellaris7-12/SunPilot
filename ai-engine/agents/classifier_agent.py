"""ClassifierAgent - classify ticket business scenario and workflow."""

import logging

from agents.base import BaseAgent

logger = logging.getLogger(__name__)

CLASSIFIER_SYSTEM_PROMPT = """你是一个信用卡工单分类与优先级判定专家。
请分析工单内容，判断客户诉求属于以下哪类场景：
1. COUPON_REISSUE - 优惠券/权益补发：客户反馈优惠券未到账、过期或活动达标未收到券
2. CUSTOMER_ADDRESS_UPDATE - 资料修改：客户要求修改账单地址、联系电话、个人信息等
3. TRANSACTION_DISPUTE - 交易争议/交易核查：客户质疑交易、声称非本人消费或要求核查交易
4. BENEFIT_QUERY - 权益资格查询：客户咨询活动资格、权益可用状态、贵宾厅/积分/权益资格
5. APPLICATION_PROGRESS_QUERY - 申请进度查询：客户查询办卡、资料补充、调额或业务办理进度
6. UNKNOWN - 无法识别：不属于以上任何场景

请以 JSON 格式返回：
{
  "type": "COUPON_REISSUE | CUSTOMER_ADDRESS_UPDATE | TRANSACTION_DISPUTE | BENEFIT_QUERY | APPLICATION_PROGRESS_QUERY | UNKNOWN",
  "label": "场景中文名称",
  "confidence": 0.0,
  "workflow_name": "对应流程名",
  "reason": "一句话说明分类依据"
}

只返回 JSON，不要包含其他文字。"""


class ClassifierAgent(BaseAgent):
    """Classify ticket content into predefined business scenarios."""

    async def run(self, input_data: dict, context: dict = None) -> dict:
        ticket_content = input_data.get("ticket_content", "")
        workflow_config = input_data.get("workflow_config", {})
        if not ticket_content:
            return {
                "type": "UNKNOWN",
                "label": "无法识别",
                "confidence": 0.0,
                "workflow_name": workflow_config.get("default_workflow", "unknown_flow"),
                "reason": "工单内容为空",
            }

        user_prompt = f"请分析以下工单内容，识别业务场景和处理路径：\n\n{ticket_content}"

        logger.info("[ClassifierAgent] Analyzing ticket content (%s chars)", len(ticket_content))
        result = await self.call_llm(CLASSIFIER_SYSTEM_PROMPT, user_prompt)

        scenarios = workflow_config.get("scenarios", {})
        intent_type = result.get("type") or "UNKNOWN"
        if intent_type not in scenarios:
            intent_type = "UNKNOWN"
        scenario_config = scenarios.get(intent_type) or scenarios.get("UNKNOWN", {})

        result["type"] = intent_type
        result["label"] = result.get("label") or scenario_config.get("label", "未知")
        result["confidence"] = result.get("confidence", 0.0) or 0.0
        result["workflow_name"] = (
            result.get("workflow_name")
            or scenario_config.get("workflow_name")
            or workflow_config.get("default_workflow", "unknown_flow")
        )
        result["reason"] = result.get("reason", "")

        logger.info(
            "[ClassifierAgent] Result: type=%s, confidence=%s",
            result.get("type"),
            result.get("confidence"),
        )
        return result
