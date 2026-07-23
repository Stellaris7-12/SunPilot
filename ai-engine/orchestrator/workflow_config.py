"""Workflow configuration loader for business-agent orchestration."""

import json
import logging
from functools import lru_cache
from pathlib import Path

from models.workflow import WorkflowConfig


WORKFLOW_CONFIG_JSON = Path(__file__).resolve().parent.parent / "data" / "workflow_config.json"

logger = logging.getLogger(__name__)

DEFAULT_WORKFLOW_CONFIG = {
    "default_workflow": "unknown_flow",
    "scenarios": {
        "COUPON_REISSUE": {
            "workflow_name": "coupon_reissue_flow",
            "label": "优惠券补发",
            "fields": [
                {"name": "customerId", "label": "客户号"},
                {"name": "phone", "label": "手机号（脱敏后）"},
                {"name": "couponType", "label": "券类型描述"},
                {"name": "reason", "label": "补发原因"},
            ],
            "required_fields": ["customerId", "couponType", "reason"],
            "recommended_tool": "coupon.reissue",
            "requires_human_confirmation": False,
            "notification_template": "已核实客户权益或活动达标情况，并根据处理结果反馈优惠券补发状态。",
        },
        "CUSTOMER_ADDRESS_UPDATE": {
            "workflow_name": "address_update_flow",
            "label": "资料修改",
            "fields": [
                {"name": "customerId", "label": "客户号"},
                {"name": "phone", "label": "手机号（脱敏后）"},
                {"name": "newAddress", "label": "新地址"},
                {"name": "verifyStatus", "label": "身份核验状态"},
            ],
            "required_fields": ["customerId", "newAddress", "verifyStatus"],
            "recommended_tool": "customer.update-address",
            "requires_human_confirmation": True,
            "notification_template": "已根据客户申请和身份核验结果处理资料修改，并提示客户关注后续生效状态。",
        },
        "TRANSACTION_DISPUTE": {
            "workflow_name": "transaction_dispute_flow",
            "label": "交易争议",
            "fields": [
                {"name": "customerId", "label": "客户号"},
                {"name": "transactionDate", "label": "交易日期"},
                {"name": "amount", "label": "交易金额"},
                {"name": "merchantName", "label": "商户名称"},
                {"name": "disputeReason", "label": "争议原因"},
            ],
            "required_fields": ["customerId", "transactionDate", "amount", "merchantName"],
            "recommended_tool": "transaction.query",
            "requires_human_confirmation": True,
            "notification_template": "已记录客户交易争议诉求，并说明需人工复核的原因和后续处理流程。",
        },
        "BENEFIT_QUERY": {
            "workflow_name": "benefit_query_flow",
            "label": "权益资格查询",
            "fields": [
                {"name": "customerId", "label": "客户号"},
                {"name": "phone", "label": "手机号（脱敏后）"},
                {"name": "benefitCode", "label": "权益或活动编码"},
                {"name": "queryReason", "label": "查询原因"},
            ],
            "required_fields": ["customerId", "benefitCode", "queryReason"],
            "recommended_tool": "benefit.query",
            "requires_human_confirmation": False,
            "notification_template": "已查询客户权益资格，并向客户说明可用状态、使用规则和后续建议。",
        },
        "APPLICATION_PROGRESS_QUERY": {
            "workflow_name": "application_progress_query_flow",
            "label": "申请进度查询",
            "fields": [
                {"name": "customerId", "label": "客户号"},
                {"name": "phone", "label": "手机号（脱敏后）"},
                {"name": "applicationNo", "label": "申请单号或业务流水号"},
            ],
            "required_fields": ["customerId", "applicationNo"],
            "recommended_tool": "application.progress-query",
            "requires_human_confirmation": False,
            "notification_template": "已查询业务申请进度，并向客户同步当前节点、预计完成时间和注意事项。",
        },
        "UNKNOWN": {
            "workflow_name": "unknown_flow",
            "label": "未知场景",
            "fields": [
                {"name": "customerId", "label": "客户号"},
                {"name": "phone", "label": "手机号"},
                {"name": "summary", "label": "诉求摘要"},
            ],
            "required_fields": [],
            "recommended_tool": "",
            "requires_human_confirmation": True,
            "notification_template": "当前诉求无法稳定识别，建议补充信息或转人工处理。",
        },
    },
}


@lru_cache(maxsize=1)
def load_workflow_config() -> dict:
    """Load and validate lightweight workflow config from disk."""
    try:
        with open(WORKFLOW_CONFIG_JSON, "r", encoding="utf-8") as file:
            payload = json.load(file)
        return WorkflowConfig.model_validate(payload).to_runtime_dict()
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        logger.warning("Falling back to built-in workflow config: %s", exc)
        return WorkflowConfig.model_validate(DEFAULT_WORKFLOW_CONFIG).to_runtime_dict()


def get_scenario_config(intent_type: str) -> dict:
    """Return scenario config, falling back to UNKNOWN."""
    config = load_workflow_config()
    scenarios = config.get("scenarios", {})
    return scenarios.get(intent_type) or scenarios.get("UNKNOWN", {})
