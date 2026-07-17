"""NotificationAgent - generate customer reply and status notification drafts."""

import json
import logging

from agents.base import BaseAgent

logger = logging.getLogger(__name__)

NOTIFICATION_SYSTEM_PROMPT = """你是一个信用卡工单通知与回单生成专家。根据工单处理的全流程结果，生成规范化的回单话术。
话术要求：
1. 开头确认客户诉求，体现"已认真核实"
2. 中间说明处理动作和具体结果，必须包含证据编号（如券编号、变更编号、交易流水号）
3. 结尾给出客户后续操作建议（如"请在App中查看"）
4. 语言专业、简洁、温暖，符合信用卡客服语气
5. 如果处理结果是转人工复核，话术应说明原因和后续流程
6. 不要编造未发生的操作结果
请以JSON格式返回：{"reply_draft": "回单话术全文"}

只返回JSON，不要包含任何其他文字。"""


class NotificationAgent(BaseAgent):
    """Generate a professional reply draft from the full pipeline output."""

    async def run(self, input_data: dict, context: dict = None) -> dict:
        intent = input_data.get("intent", {})
        fields = input_data.get("fields", [])
        tool_result = input_data.get("tool_result")
        verify_result = input_data.get("verify_result", {})
        workflow_config = input_data.get("workflow_config", {})

        notification_template = (
            workflow_config.get("scenarios", {})
            .get(intent.get("type", "UNKNOWN"), {})
            .get("notification_template", "")
        )

        parts = []
        if notification_template:
            parts.append(f"## 默认通知模板\n{notification_template}")

        parts.append("## 分类结果")
        parts.append(f"场景: {intent.get('label', '未知')}")
        parts.append(f"置信度: {intent.get('confidence', 0)}")

        parts.append("\n## 已抽取字段")
        for f in fields:
            parts.append(f"- {f['label']}: {f['value']}")

        parts.append("\n## 业务执行结果")
        if tool_result:
            parts.append(json.dumps(tool_result, ensure_ascii=False, indent=2))
        else:
            parts.append("未执行业务工具（工单已升级人工处理）")

        parts.append("\n## 升级与兜底判断")
        parts.append(f"风险等级: {verify_result.get('risk_level', 'unknown')}")
        parts.append(f"处理建议: {verify_result.get('risk_decision', '')}")

        if verify_result.get("risk_level") == "high" or not verify_result.get("can_auto_proceed", True):
            parts.append("\n注意：此工单已标记为需人工复核，请生成建议转人工处理的回单话术。")

        user_prompt = "\n".join(parts)

        logger.info("[NotificationAgent] Generating reply draft")
        result = await self.call_llm(NOTIFICATION_SYSTEM_PROMPT, user_prompt)

        if "reply_draft" not in result:
            result["reply_draft"] = "（回单话术生成失败，请人工填写）"

        logger.info("[NotificationAgent] Generated reply (%s chars)", len(result["reply_draft"]))
        return result
