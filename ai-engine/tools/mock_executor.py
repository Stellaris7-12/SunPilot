"""Mock tool executor for demo business-system calls."""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime

from models.tool_schemas import ToolResult
from tools.registry import tool_registry

logger = logging.getLogger(__name__)

_PREFIX_MAP = {
    "coupon": "CP",
    "customer": "ADDR",
    "transaction": "TXN",
    "benefit": "BEN",
    "application": "APP",
}

_ACTION_MAP = {
    "coupon.reissue": "补发优惠券",
    "customer.update-address": "修改客户资料",
    "transaction.query": "查询交易流水",
    "benefit.query": "查询权益资格",
    "application.progress-query": "查询申请进度",
}

_NEXT_STEP_MAP = {
    "coupon.reissue": "通知客户查收优惠券并关注到账状态",
    "customer.update-address": "提示客户关注资料生效状态",
    "transaction.query": "结合交易详情判断是否进入人工争议处理",
    "benefit.query": "根据权益资格生成客户说明或补发建议",
    "application.progress-query": "向客户同步当前进度和预计下一处理节点",
}

_ESCALATION_KEYWORDS = ("冲突", "权限", "拒绝", "失败", "异常", "不存在")


class MockExecutor:
    """Simulates external API/business-system calls."""

    def __init__(self, registry=None):
        self._registry = registry or tool_registry

    async def execute(self, tool_name: str, params: dict) -> ToolResult:
        """Execute a mock tool and return a normalized business result."""
        tool_def = self._registry.get(tool_name)
        if tool_def is None:
            message = f"工具 '{tool_name}' 不存在"
            return ToolResult(
                success=False,
                tool_name=tool_name,
                evidence_id="",
                action="工具路由",
                business_result=message,
                next_step="交由人工确认工具配置",
                requires_human=True,
                failure_reason=message,
                message=message,
                duration_ms=0,
            )

        is_valid, message = self._registry.validate_params(tool_name, params)
        if not is_valid:
            return ToolResult(
                success=False,
                tool_name=tool_name,
                evidence_id="",
                action=_ACTION_MAP.get(tool_name, tool_def.display_name),
                business_result=message,
                next_step="补充缺失参数后重新执行",
                requires_human=False,
                failure_reason=message,
                message=message,
                duration_ms=0,
            )

        start = time.time()
        await asyncio.sleep(tool_def.mock_delay_ms / 1000)

        evidence_id = self._generate_evidence_id(tool_def.category)
        response = json.loads(json.dumps(tool_def.mock_response))
        response = self._replace_templates(response, evidence_id)

        elapsed_ms = int((time.time() - start) * 1000)
        business_result = self._business_result(tool_name, response)
        requires_human = bool(
            response.get("needManualReview")
            or response.get("requiresHuman")
            or any(keyword in business_result for keyword in _ESCALATION_KEYWORDS)
        )
        next_step = response.get("nextStep") or _NEXT_STEP_MAP.get(tool_name, "进入人工复核或结案")
        action = response.get("action") or _ACTION_MAP.get(tool_name, tool_def.display_name)

        logger.info(
            "[MockExecutor] %s executed - evidence_id=%s, duration=%sms",
            tool_name,
            evidence_id,
            elapsed_ms,
        )

        return ToolResult(
            success=True,
            tool_name=tool_name,
            evidence_id=evidence_id,
            action=action,
            business_result=business_result,
            next_step=next_step,
            requires_human=requires_human,
            data=response,
            message=f"工具 {tool_def.display_name} 执行成功",
            duration_ms=elapsed_ms,
        )

    def _replace_templates(self, response: dict, evidence_id: str) -> dict:
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        replaced = {}
        for key, value in response.items():
            if isinstance(value, str):
                value = value.replace("{{TIMESTAMP}}", timestamp)
                value = value.replace("{{EVIDENCE_ID}}", evidence_id)
            replaced[key] = value
        replaced["evidenceId"] = evidence_id
        return replaced

    def _business_result(self, tool_name: str, response: dict) -> str:
        if response.get("businessResult"):
            return str(response["businessResult"])
        status = response.get("status", "SUCCESS")
        if tool_name == "coupon.reissue":
            return f"优惠券已补发，券号 {response.get('couponId', '')}，状态 {status}"
        if tool_name == "customer.update-address":
            return f"客户资料已更新，变更单号 {response.get('changeId', '')}，状态 {status}"
        if tool_name == "transaction.query":
            return (
                f"已查询到交易 {response.get('transactionId', '')}，"
                f"渠道 {response.get('channel', '')}，状态 {status}"
            )
        if tool_name == "benefit.query":
            return (
                f"权益资格 {response.get('eligible', False)}，"
                f"权益状态 {response.get('status', '')}"
            )
        if tool_name == "application.progress-query":
            return (
                f"申请进度 {response.get('stage', '')}，"
                f"预计完成时间 {response.get('eta', '')}"
            )
        return f"工具执行完成，状态 {status}"

    def _generate_evidence_id(self, category: str) -> str:
        """Generate a business-meaningful evidence ID."""
        prefix = _PREFIX_MAP.get(category, "EV")
        date_str = datetime.now().strftime("%Y%m%d")
        suffix = str(uuid.uuid4())[:8].upper()
        return f"{prefix}{date_str}{suffix}"


from tools.registry import tool_registry as _registry

mock_executor = MockExecutor(_registry)
