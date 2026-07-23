"""NotificationAgent - generate customer reply and internal notification bundle."""

import json
import logging

from agents.base import BaseAgent
from models.workflow import workflow_scenario

logger = logging.getLogger(__name__)

NOTIFICATION_SYSTEM_PROMPT = """你是一个信用卡工单通知与回单生成专家。根据工单处理全流程结果，生成结构化通知闭环。
要求：
1. standard_reply.body 是客户可见回单，需说明处理结论、证据编号和后续建议。
2. internal_notice.body 是业务人员可见通知，需说明系统做了什么、为什么、下一步谁处理。
3. review_summary 用于人工复核，需概括风险原因、缺失字段、工具证据和建议操作。
4. closure_suggestion 只给出是否建议结案，不要直接要求系统自动结案。
5. follow_up 只做回访模板和状态预留。
6. 不要编造未发生的业务动作或证据编号。

请只返回 JSON，结构如下：
{
  "reply_draft": "客户可见回单全文",
  "notification": {
    "standard_reply": {"title": "标准回单", "body": "...", "status": "ready|needs_info|needs_review|escalated|failed", "evidence_ids": [], "next_owner": "customer|agent|human|system"},
    "internal_notice": {"title": "内部通知", "body": "...", "status": "ready|needs_info|needs_review|escalated|failed", "evidence_ids": [], "next_owner": "customer|agent|human|system"},
    "review_summary": {"reason": "...", "risk_decision": "...", "missing_fields": [], "tool_evidence_ids": [], "suggested_action": "..."},
    "closure_suggestion": {"can_close": false, "reason": "...", "final_reply": "...", "requires_human_review": true},
    "follow_up": {"enabled": false, "template": "...", "trigger_status": ""}
  }
}"""


def _as_dict(value) -> dict:
    if not value:
        return {}
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return value if isinstance(value, dict) else {}


def _field_value(fields: list[dict], name: str, default: str = "") -> str:
    for field in fields:
        if field.get("name") == name and field.get("value"):
            return str(field["value"])
    return default


class NotificationAgent(BaseAgent):
    """Generate customer-facing replies and business-facing notification data."""

    async def run(self, input_data: dict, context: dict = None) -> dict:
        intent = input_data.get("intent", {})
        fields = input_data.get("fields", [])
        tool_result = _as_dict(input_data.get("tool_result"))
        verify_result = input_data.get("verify_result", {})
        workflow_config = input_data.get("workflow_config", {})
        status = input_data.get("status", "pending_human_review")
        missing_fields = input_data.get("missing_fields", []) or verify_result.get("missing_fields", [])
        failure_reason = input_data.get("failure_reason", "") or verify_result.get("risk_decision", "")
        pause_type = input_data.get("pause_type")

        notification_template = workflow_scenario(
            workflow_config,
            intent.get("type", "UNKNOWN"),
        ).notification_template

        parts = []
        if notification_template:
            parts.append(f"## 默认通知模板\n{notification_template}")

        parts.append("## 分类结果")
        parts.append(f"场景: {intent.get('label', '未知')}")
        parts.append(f"置信度: {intent.get('confidence', 0)}")

        parts.append("\n## 已抽取字段")
        for f in fields:
            parts.append(f"- {f['label']}: {f['value']}")

        parts.append("\n## 工单终态")
        parts.append(f"状态: {status}")
        if pause_type:
            parts.append(f"暂停类型: {pause_type}")
        if missing_fields:
            parts.append(f"缺失字段: {', '.join(missing_fields)}")
        if failure_reason:
            parts.append(f"失败或升级原因: {failure_reason}")

        parts.append("\n## 业务执行结果")
        if tool_result:
            parts.append(json.dumps(tool_result, ensure_ascii=False, indent=2))
        else:
            parts.append("未执行业务工具或尚未执行工具。")

        parts.append("\n## 升级与兜底判断")
        parts.append(f"风险等级: {verify_result.get('risk_level', 'unknown')}")
        parts.append(f"处理建议: {verify_result.get('risk_decision', '')}")

        if (
            status in {"pending_info", "pending_human_confirm", "escalated", "failed"}
            or verify_result.get("risk_level") == "high"
            or not verify_result.get("can_auto_proceed", True)
        ):
            parts.append("\n注意：此工单已标记为需人工复核，请生成建议转人工处理的回单话术。")

        user_prompt = "\n".join(parts)

        logger.info("[NotificationAgent] Generating reply draft")
        fallback = self._build_fallback(
            intent=intent,
            fields=fields,
            tool_result=tool_result,
            verify_result=verify_result,
            status=status,
            missing_fields=missing_fields,
            failure_reason=failure_reason,
            notification_template=notification_template,
        )
        try:
            result = await self.call_llm(NOTIFICATION_SYSTEM_PROMPT, user_prompt)
        except Exception as exc:
            logger.warning("[NotificationAgent] LLM failed, using fallback: %s", exc)
            result = fallback

        result = self._normalize_result(
            result,
            fallback,
            status=status,
            tool_result=tool_result,
            failure_reason=failure_reason,
            risk_decision=verify_result.get("risk_decision", ""),
        )

        logger.info("[NotificationAgent] Generated reply (%s chars)", len(result["reply_draft"]))
        return result

    def _build_fallback(
        self,
        *,
        intent: dict,
        fields: list[dict],
        tool_result: dict,
        verify_result: dict,
        status: str,
        missing_fields: list[str],
        failure_reason: str,
        notification_template: str,
    ) -> dict:
        label = intent.get("label") or "客户诉求"
        customer_id = _field_value(fields, "customerId", "客户")
        evidence_id = tool_result.get("evidence_id") or tool_result.get("evidenceId") or ""
        business_result = tool_result.get("business_result") or tool_result.get("businessResult") or ""
        next_step = tool_result.get("next_step") or tool_result.get("nextStep") or ""
        risk_decision = verify_result.get("risk_decision") or failure_reason or "待人工复核"
        evidence_ids = [evidence_id] if evidence_id else []

        notification_status = self._notification_status(status)
        can_close = status == "pending_human_review" and bool(tool_result.get("success", False))
        requires_review = not can_close

        if status == "pending_info":
            readable_missing = "、".join(missing_fields) if missing_fields else "必要业务信息"
            reply = f"已认真核实您的{label}诉求。为继续办理，请补充{readable_missing}，我们收到后会继续处理。"
            internal = f"{customer_id} 的工单待补充信息：{readable_missing}。下一步由客户补充后重新进入处理流程。"
            suggested_action = "联系客户补充缺失字段后重新发起 AI 处理。"
        elif status == "pending_human_confirm":
            reply = f"已认真核实您的{label}诉求。该事项涉及敏感业务操作，需要工作人员复核确认后继续处理。"
            internal = f"{customer_id} 的工单已暂停在人工确认节点，原因：{risk_decision}。确认后再执行后续业务动作。"
            suggested_action = "核对抽取字段与客户身份信息，确认后继续执行，拒绝则升级人工。"
        elif status == "escalated":
            reply = f"已认真核实您的{label}诉求。由于{risk_decision}，该工单已转人工复核处理，后续将由专员跟进。"
            internal = f"{customer_id} 的工单已升级人工。升级原因：{failure_reason or risk_decision}。"
            suggested_action = "人工复核风险原因、工具结果和客户原始诉求后处理。"
        elif status == "failed":
            reply = f"已认真核实您的{label}诉求。当前自动处理流程执行异常，已建议人工介入核查。"
            internal = f"{customer_id} 的工单自动流程失败。失败原因：{failure_reason or '未知异常'}。"
            suggested_action = "检查失败原因并由人工接管处理。"
        else:
            result_text = business_result or "业务处理已完成"
            evidence_text = f"证据编号：{evidence_id}。" if evidence_id else ""
            advice = next_step or "请您留意 App 或短信中的后续状态。"
            reply = f"已认真核实您的{label}诉求。{result_text}。{evidence_text}{advice}"
            internal = (
                f"{customer_id} 的工单已完成自动处理。"
                f"工具结果：{result_text}；证据编号：{evidence_id or '无'}。"
            )
            suggested_action = "业务人员复核回单内容，无误后结案。"

        if notification_template and status not in {"pending_info", "escalated", "failed"}:
            internal = f"{internal} 模板要求：{notification_template}"

        bundle = {
            "standard_reply": {
                "title": "标准回单",
                "body": reply,
                "status": notification_status,
                "evidence_ids": evidence_ids,
                "next_owner": "customer" if status == "pending_info" else "human",
            },
            "internal_notice": {
                "title": "内部通知",
                "body": internal,
                "status": notification_status,
                "evidence_ids": evidence_ids,
                "next_owner": self._next_owner(status),
            },
            "review_summary": {
                "reason": failure_reason or risk_decision,
                "risk_decision": risk_decision,
                "missing_fields": missing_fields,
                "tool_evidence_ids": evidence_ids,
                "suggested_action": suggested_action,
            },
            "closure_suggestion": {
                "can_close": can_close,
                "reason": "标准场景已自动处理并具备证据编号，建议人工复核回单后结案。" if can_close else "当前状态仍需补充、确认或人工处理，不建议直接结案。",
                "final_reply": reply,
                "requires_human_review": requires_review,
            },
            "follow_up": {
                "enabled": can_close,
                "template": "建议结案后进行满意度回访，确认客户是否认可处理结果。" if can_close else "",
                "trigger_status": "closed" if can_close else "",
            },
        }
        return {"reply_draft": reply, "notification": bundle}

    def _normalize_result(
        self,
        result: dict,
        fallback: dict,
        *,
        status: str,
        tool_result: dict,
        failure_reason: str,
        risk_decision: str,
    ) -> dict:
        if not isinstance(result, dict):
            return fallback

        notification = result.get("notification")
        if not isinstance(notification, dict):
            notification = fallback["notification"]

        for key, value in fallback["notification"].items():
            if not isinstance(notification.get(key), dict):
                notification[key] = value
            elif isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    current = notification[key].get(sub_key)
                    if current is None or current == "":
                        notification[key][sub_key] = sub_value

        reply_draft = result.get("reply_draft") or notification.get("standard_reply", {}).get("body")
        if not reply_draft:
            reply_draft = fallback["reply_draft"]

        evidence_id = tool_result.get("evidence_id") or tool_result.get("evidenceId") or ""
        allowed_evidence_ids = [evidence_id] if evidence_id else []
        for artifact_name in ("standard_reply", "internal_notice"):
            notification[artifact_name]["status"] = self._notification_status(status)
            notification[artifact_name]["evidence_ids"] = allowed_evidence_ids

        notification["review_summary"]["tool_evidence_ids"] = allowed_evidence_ids

        can_close = status == "pending_human_review" and bool(tool_result.get("success", False))
        notification["closure_suggestion"]["can_close"] = can_close
        notification["closure_suggestion"]["requires_human_review"] = not can_close
        if not can_close:
            notification["closure_suggestion"]["reason"] = fallback["notification"]["closure_suggestion"]["reason"]
            notification["follow_up"]["enabled"] = False
            notification["follow_up"]["template"] = ""
            notification["follow_up"]["trigger_status"] = ""
        else:
            notification["follow_up"]["enabled"] = bool(notification["follow_up"].get("enabled", True))
            notification["follow_up"]["trigger_status"] = notification["follow_up"].get("trigger_status") or "closed"

        if status in {"pending_info", "pending_human_confirm", "escalated", "failed"}:
            reply_draft = fallback["reply_draft"]
            notification["standard_reply"]["body"] = reply_draft
            notification["internal_notice"]["body"] = fallback["notification"]["internal_notice"]["body"]
            notification["review_summary"]["reason"] = failure_reason or risk_decision
            notification["review_summary"]["risk_decision"] = risk_decision or failure_reason
            notification["review_summary"]["suggested_action"] = fallback["notification"]["review_summary"]["suggested_action"]

        notification["standard_reply"]["body"] = notification["standard_reply"].get("body") or reply_draft
        notification["closure_suggestion"]["final_reply"] = (
            notification["closure_suggestion"].get("final_reply") or reply_draft
        )
        return {"reply_draft": reply_draft, "notification": notification}

    @staticmethod
    def _notification_status(status: str) -> str:
        return {
            "pending_info": "needs_info",
            "pending_human_confirm": "needs_review",
            "pending_human_review": "ready",
            "escalated": "escalated",
            "failed": "failed",
            "closed": "closed",
        }.get(status, "needs_review")

    @staticmethod
    def _next_owner(status: str) -> str:
        return {
            "pending_info": "customer",
            "pending_human_confirm": "human",
            "pending_human_review": "human",
            "escalated": "human",
            "failed": "human",
            "closed": "system",
        }.get(status, "human")
