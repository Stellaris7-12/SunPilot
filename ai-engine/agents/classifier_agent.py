"""ClassifierAgent - classify ticket business scenario and workflow."""

import logging
import re

from agents.base import BaseAgent
from models.scenario_detection import FITS_SCENARIOS, scenario_result

logger = logging.getLogger(__name__)

CLASSIFIER_SYSTEM_PROMPT = """你是一个信用卡工单分类与优先级判定专家。
请分析工单内容，判断客户诉求属于以下哪类场景：
1. 协商还款 - 客户申请还款协商、延期、客助或特殊方案
2. 伪冒预防 - 疑似非本人申请、冒名、伪冒交易预警或投诉引导
3. 伪冒调查 - 卡片被管制、两核身不过、X-DK 或调查组介入
4. 客户经营 - 资料借阅、结清证明、解抵押、卡部承接材料类诉求
5. 市场企划 - 活动权益、优惠券、饭票、影票、掌上生活和营销活动反馈
6. 调单扣款 - 交易调单、调扣、扣款、交易查询或争议取证
7. 征信 - 征信、贷后风险、逾期状态和敏感账户核实
8. UNKNOWN - 无法识别或不属于以上场景

请以 JSON 格式返回：
{
  "type": "协商还款 | 伪冒预防 | 伪冒调查 | 客户经营 | 市场企划 | 调单扣款 | 征信 | UNKNOWN",
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

        deterministic_result = scenario_result(ticket_content, workflow_config)
        if deterministic_result.get("type") != "UNKNOWN":
            return deterministic_result
        if _looks_like_pure_consultation(ticket_content):
            return {
                "type": "UNKNOWN",
                "label": "未知场景",
                "confidence": 0.0,
                "workflow_name": workflow_config.get("default_workflow", "unknown_flow"),
                "reason": "客户仅咨询规则或领取方式，未形成已接入 FITS 工单处理诉求",
            }

        user_prompt = f"请分析以下工单内容，识别业务场景和处理路径：\n\n{ticket_content}"

        logger.info("[ClassifierAgent] Analyzing ticket content (%s chars)", len(ticket_content))
        result = await self.call_llm(CLASSIFIER_SYSTEM_PROMPT, user_prompt)

        scenarios = workflow_config.get("scenarios", {})
        intent_type = result.get("type") or "UNKNOWN"
        if intent_type not in FITS_SCENARIOS:
            intent_type = "UNKNOWN"
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


def _looks_like_pure_consultation(text: str) -> bool:
    """Prevent LLM fallback from turning generic FAQ-style questions into tickets."""
    text = text or ""
    if not re.search(r"咨询|规则|领取方式|如何领取|怎么用|使用条件|办理入口", text, re.I):
        return False
    actionable_pattern = (
        r"工单|处理|核实|调查|投诉|要求|申请|补发|未到账|失败|异常|争议|拒付|"
        r"管制|逾期|调单|扣款|结清证明|资料借阅|协商还款|延期还款|确认剩余次数"
    )
    return not re.search(actionable_pattern, text, re.I)
