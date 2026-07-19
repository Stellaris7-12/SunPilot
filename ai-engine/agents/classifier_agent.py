"""ClassifierAgent - classify ticket business scenario and workflow."""

import logging
import re

from agents.base import BaseAgent

logger = logging.getLogger(__name__)

UNSUPPORTED_SCENE_KEYWORDS = (
    "\u5206\u671f",      # installment
    "\u63d0\u524d\u7ed3\u6e05",
    "\u8fd8\u6b3e\u534f\u5546",
    "\u5ef6\u671f\u8fd8\u6b3e",
    "\u6302\u5931",
    "\u8865\u5361",
    "\u505c\u5361",
    "\u4e34\u65f6\u989d\u5ea6",
    "\u56fa\u5b9a\u989d\u5ea6",
    "\u5e74\u8d39",
    "\u79ef\u5206\u5230\u8d26",
    "\u79ef\u5206\u672a\u5230\u8d26",
    "\u79ef\u5206\u6ca1\u6709\u5230\u8d26",
    "\u79ef\u5206\u6263\u51cf",
    "\u79ef\u5206\u5151\u6362",
    "\u79ef\u5206\u4e89\u8bae",
    "\u79ef\u5206\u5151\u6362\u5931\u8d25",
    "\u5f81\u4fe1",
    "\u6295\u8bc9",
    "\u50ac\u529e",
)

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
        unsupported_result = _unsupported_scene_result(ticket_content, workflow_config)
        if unsupported_result:
            return unsupported_result
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
        # Workflow names are deterministic contract values used by evaluation,
        # tracing, and downstream routing. Do not let LLM wording drift them.
        result["workflow_name"] = (
            scenario_config.get("workflow_name")
            or workflow_config.get("default_workflow", "unknown_flow")
        )
        result["reason"] = result.get("reason", "")

        logger.info(
            "[ClassifierAgent] Result: type=%s, confidence=%s",
            result.get("type"),
            result.get("confidence"),
        )
        return result


def _unsupported_scene_result(ticket_content: str, workflow_config: dict) -> dict | None:
    """Keep unsupported extension scenarios out of existing tool workflows."""
    if not ticket_content:
        return None
    if _looks_like_supported_scene(ticket_content):
        return None
    matched = [keyword for keyword in UNSUPPORTED_SCENE_KEYWORDS if keyword in ticket_content]
    if not matched:
        return None
    scenarios = workflow_config.get("scenarios", {})
    scenario_config = scenarios.get("UNKNOWN", {})
    return {
        "type": "UNKNOWN",
        "label": scenario_config.get("label", "\u672a\u77e5\u573a\u666f"),
        "confidence": 0.95,
        "workflow_name": scenario_config.get(
            "workflow_name",
            workflow_config.get("default_workflow", "unknown_flow"),
        ),
        "reason": (
            "\u547d\u4e2d\u5c1a\u672a\u63a5\u5165\u81ea\u52a8\u5de5\u5177\u7684"
            f"\u6269\u5c55\u573a\u666f\u5173\u952e\u8bcd: {', '.join(matched)}"
        ),
    }


def _looks_like_supported_scene(ticket_content: str) -> bool:
    if "APP" in ticket_content or "\u4e1a\u52a1\u6d41\u6c34" in ticket_content:
        return True
    if "\u4ea4\u6613" in ticket_content and (
        re.search(r"20\d{2}-\d{2}-\d{2}", ticket_content)
        or "\u5546\u6237" in ticket_content
        or "\u975e\u672c\u4eba" in ticket_content
        or "\u76d7\u5237" in ticket_content
        or "\u4e0d\u8ba4\u53ef" in ticket_content
    ):
        return True
    if re.search(r"[A-Z][A-Z0-9]+(?:_[A-Z0-9]+)+", ticket_content) and (
        "\u6d3b\u52a8" in ticket_content
        or "\u8d44\u683c" in ticket_content
        or "\u53c2\u52a0" in ticket_content
    ):
        return True
    return False
