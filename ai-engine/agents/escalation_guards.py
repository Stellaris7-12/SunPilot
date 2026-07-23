"""Deterministic guards used inside EscalationAgent."""

TOOL_ESCALATION_KEYWORDS = ("冲突", "权限", "拒绝", "失败", "异常", "不存在")
MISSING_VALUES = {"", "未提取", "未提供", "N/A", "UNKNOWN", None}


class CompletenessGuard:
    """Checks unsupported scenes and required business fields."""

    @staticmethod
    def unsupported_scene(intent_type: str, ticket_risk: str, checks: list[dict]) -> dict | None:
        if intent_type != "UNKNOWN":
            return None
        checks.append({"label": "未知场景需人工分流", "status": "需复核"})
        return {
            "checks": checks,
            "risk_level": "high" if ticket_risk == "high" else "medium",
            "risk_decision": "当前场景未接入自动化工具，建议转人工处理",
            "can_auto_proceed": False,
            "missing_fields": [],
            "needs_more_info": False,
        }

    @staticmethod
    def missing_required(
        required: list[str],
        fields_dict: dict,
        ticket_risk: str,
        checks: list[dict],
    ) -> dict | None:
        missing = [
            name for name in required
            if fields_dict.get(name) in MISSING_VALUES
        ]
        if not missing:
            return None
        checks.append({
            "label": f"必填字段缺失: {', '.join(missing)}",
            "status": "待补充",
        })
        return {
            "checks": checks,
            "risk_level": ticket_risk,
            "risk_decision": "信息不足，需要补充必填字段后继续处理",
            "can_auto_proceed": False,
            "missing_fields": missing,
            "needs_more_info": True,
        }


class RiskGuard:
    """Checks risk-level and manual-confirmation gates."""

    @staticmethod
    def high_risk_ticket(ticket_risk: str, checks: list[dict]) -> dict | None:
        if ticket_risk != "high":
            return None
        checks.append({"label": "工单标记为高风险，建议转人工", "status": "已拦截"})
        return {
            "checks": checks,
            "risk_level": "high",
            "risk_decision": "高风险工单，已转人工审核",
            "can_auto_proceed": False,
            "missing_fields": [],
            "needs_more_info": False,
        }

    @staticmethod
    def transaction_precheck(
        intent_type: str,
        tool_result: dict,
        ticket_risk: str,
        checks: list[dict],
    ) -> dict | None:
        if intent_type != "TRANSACTION_DISPUTE" or tool_result:
            return None
        checks.append({"label": "交易核查先执行只读查询取证", "status": "通过"})
        return {
            "checks": checks,
            "risk_level": ticket_risk,
            "risk_decision": "交易信息已基本齐全，先查询 Mock 交易流水作为人工复核证据",
            "can_auto_proceed": True,
            "missing_fields": [],
            "needs_more_info": False,
        }

    @staticmethod
    def failed_identity_check(
        intent_type: str,
        fields_dict: dict,
        checks: list[dict],
    ) -> dict | None:
        verify_status = str(fields_dict.get("verifyStatus", "")).upper()
        if intent_type != "CUSTOMER_ADDRESS_UPDATE":
            return None
        if "FAILED" not in verify_status and "未通过" not in verify_status:
            return None
        checks.append({"label": "身份核验未通过", "status": "已拦截"})
        return {
            "checks": checks,
            "risk_level": "high",
            "risk_decision": "资料变更的身份核验未通过，已转人工处理",
            "can_auto_proceed": False,
            "missing_fields": [],
            "needs_more_info": False,
        }

    @staticmethod
    def requires_confirmation_before_tool(
        intent_type: str,
        ticket_risk: str,
        requires_confirmation: bool,
        tool_result: dict,
        checks: list[dict],
    ) -> dict | None:
        if tool_result:
            return None
        if not (
            ticket_risk == "medium"
            or intent_type == "CUSTOMER_ADDRESS_UPDATE"
            or requires_confirmation
        ):
            return None
        checks.append({"label": "敏感或中风险操作需人工确认", "status": "待确认"})
        return {
            "checks": checks,
            "risk_level": "medium",
            "risk_decision": "信息已基本齐全，但涉及敏感或中风险操作，需人工确认后再继续",
            "can_auto_proceed": False,
            "missing_fields": [],
            "needs_more_info": False,
        }

    @staticmethod
    def transaction_review_after_tool(intent_type: str, checks: list[dict]) -> dict | None:
        if intent_type != "TRANSACTION_DISPUTE":
            return None
        checks.append({"label": "交易争议需人工复核", "status": "需复核"})
        return {
            "checks": checks,
            "risk_level": "high",
            "risk_decision": "交易争议类工单，建议转人工复核",
            "can_auto_proceed": False,
            "missing_fields": [],
            "needs_more_info": False,
        }


class ToolResultGuard:
    """Checks tool execution failures and tool-level human gates."""

    @staticmethod
    def evaluate(tool_result: dict, checks: list[dict]) -> dict | None:
        if not tool_result:
            return None

        failure_reason = tool_result.get("failure_reason") or tool_result.get("message", "")
        business_result = tool_result.get("business_result", "")
        if not tool_result.get("success", False):
            checks.append({
                "label": f"工具执行失败: {failure_reason}",
                "status": "已拦截",
            })
            return {
                "checks": checks,
                "risk_level": "high",
                "risk_decision": failure_reason or "工具执行失败，已升级人工处理",
                "can_auto_proceed": False,
                "missing_fields": [],
                "needs_more_info": False,
            }

        if any(keyword in f"{failure_reason}{business_result}" for keyword in TOOL_ESCALATION_KEYWORDS):
            checks.append({
                "label": "工具结果存在冲突、权限或异常信号",
                "status": "需复核",
            })
            return {
                "checks": checks,
                "risk_level": "high",
                "risk_decision": "工具结果存在冲突或权限异常，已升级人工复核",
                "can_auto_proceed": False,
                "missing_fields": [],
                "needs_more_info": False,
            }

        if tool_result.get("requires_human"):
            checks.append({
                "label": "工具结果要求人工复核",
                "status": "需复核",
            })
            return {
                "checks": checks,
                "risk_level": "medium",
                "risk_decision": "业务工具返回需人工复核，已转人工确认",
                "can_auto_proceed": False,
                "missing_fields": [],
                "needs_more_info": False,
            }

        return None
