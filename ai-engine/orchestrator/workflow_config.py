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
        "协商还款": {
            "workflow_name": "repayment_negotiation_dispatch_flow",
            "label": "协商还款",
            "orderPrefix": "11",
            "slaDays": 2,
            "fields": [
                {"name": "customerId", "label": "客户号"},
                {"name": "customerName", "label": "客户姓名"},
                {"name": "phone", "label": "手机号"},
                {"name": "content", "label": "发单内容"},
                {"name": "accountNo", "label": "账户号"},
                {"name": "repaymentPlan", "label": "协商方案"},
            ],
            "required_fields": ["customerId", "customerName", "phone", "content", "accountNo", "repaymentPlan"],
            "recommended_tool": "customer.lookup",
            "requires_human_confirmation": True,
            "notification_template": "已记录协商还款诉求，建议人工复核账户、方案和客户承诺还款安排。",
        },
        "伪冒预防": {
            "workflow_name": "fraud_prevention_dispatch_flow",
            "label": "伪冒预防",
            "orderPrefix": "12",
            "slaDays": 2,
            "fields": [
                {"name": "customerId", "label": "客户号"},
                {"name": "customerName", "label": "客户姓名"},
                {"name": "phone", "label": "手机号"},
                {"name": "content", "label": "发单内容"},
                {"name": "caseNo", "label": "案件编号"},
                {"name": "workOrderCategory", "label": "工单类别"},
                {"name": "mainDemand", "label": "主体诉求"},
            ],
            "required_fields": ["customerId", "customerName", "phone", "content", "caseNo", "workOrderCategory", "mainDemand"],
            "recommended_tool": "card.account-status-query",
            "requires_human_confirmation": True,
            "notification_template": "已记录疑似伪冒预防诉求，建议人工复核客户身份、案件编号和风险阻断状态。",
        },
        "伪冒调查": {
            "workflow_name": "fraud_investigation_dispatch_flow",
            "label": "伪冒调查",
            "orderPrefix": "13",
            "slaDays": 3,
            "fields": [
                {"name": "customerId", "label": "客户号"},
                {"name": "customerName", "label": "客户姓名"},
                {"name": "phone", "label": "手机号"},
                {"name": "content", "label": "发单内容"},
                {"name": "cardList", "label": "卡片列表"},
                {"name": "controlReason", "label": "管制原因"},
                {"name": "xdk", "label": "X-DK"},
            ],
            "required_fields": ["customerId", "customerName", "phone", "content", "cardList", "controlReason", "xdk"],
            "recommended_tool": "card.account-status-query",
            "requires_human_confirmation": True,
            "notification_template": "已记录伪冒调查诉求，建议人工核验卡片管制原因和调查组处理意见。",
        },
        "客户经营": {
            "workflow_name": "customer_management_dispatch_flow",
            "label": "客户经营",
            "orderPrefix": "29",
            "slaDays": 6,
            "fields": [
                {"name": "customerId", "label": "客户号"},
                {"name": "customerName", "label": "客户姓名"},
                {"name": "phone", "label": "手机号"},
                {"name": "content", "label": "发单内容"},
                {"name": "receiveUnit", "label": "接单单位"},
                {"name": "bizSubType", "label": "业务细类"},
                {"name": "materialType", "label": "资料类型"},
            ],
            "required_fields": ["customerId", "customerName", "phone", "content", "receiveUnit", "bizSubType", "materialType"],
            "recommended_tool": "customer.lookup",
            "requires_human_confirmation": True,
            "notification_template": "已记录客户经营类资料诉求，建议由卡部人工复核资料类型和办理材料。",
        },
        "市场企划": {
            "workflow_name": "marketing_planning_dispatch_flow",
            "label": "市场企划",
            "orderPrefix": "30",
            "slaDays": 5,
            "fields": [
                {"name": "customerId", "label": "客户号"},
                {"name": "customerName", "label": "客户姓名"},
                {"name": "phone", "label": "手机号"},
                {"name": "content", "label": "发单内容"},
                {"name": "remark", "label": "订单号/备注"},
                {"name": "customerFeedback", "label": "客户反馈情况"},
                {"name": "receiveUnit", "label": "接单单位"},
                {"name": "bizSubType", "label": "业务细类"},
            ],
            "required_fields": ["customerId", "customerName", "phone", "content", "remark", "customerFeedback", "receiveUnit", "bizSubType"],
            "recommended_tool": "benefit.query",
            "requires_human_confirmation": False,
            "notification_template": "已记录市场企划类活动反馈，建议核验订单号、活动资格和补发规则。",
        },
        "调单扣款": {
            "workflow_name": "chargeback_dispatch_flow",
            "label": "调单扣款",
            "orderPrefix": "41",
            "slaDays": 3,
            "fields": [
                {"name": "customerId", "label": "客户号"},
                {"name": "customerName", "label": "客户姓名"},
                {"name": "phone", "label": "手机号"},
                {"name": "content", "label": "发单内容"},
                {"name": "workOrderCategory", "label": "工单类别"},
                {"name": "callPurpose", "label": "来电目的"},
            ],
            "required_fields": ["customerId", "customerName", "phone", "content", "workOrderCategory", "callPurpose"],
            "recommended_tool": "transaction.query",
            "requires_human_confirmation": True,
            "notification_template": "已记录调单扣款类诉求，建议核验交易信息、附件材料和调扣处理意见。",
        },
        "征信": {
            "workflow_name": "credit_reporting_dispatch_flow",
            "label": "征信",
            "orderPrefix": "42",
            "slaDays": 3,
            "fields": [
                {"name": "customerId", "label": "客户号"},
                {"name": "customerName", "label": "客户姓名"},
                {"name": "phone", "label": "手机号"},
                {"name": "content", "label": "发单内容"},
                {"name": "accountType", "label": "账户类型"},
                {"name": "accountNo", "label": "账户号"},
                {"name": "isSensitive", "label": "是否敏感"},
                {"name": "overdueStatus", "label": "逾期状态"},
            ],
            "required_fields": ["customerId", "customerName", "phone", "content", "accountType", "accountNo", "isSensitive", "overdueStatus"],
            "recommended_tool": "customer.lookup",
            "requires_human_confirmation": True,
            "notification_template": "已记录征信类诉求，建议人工复核账户类型、逾期状态和敏感信息处理要求。",
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
