"""Shared FITS scenario detection for call intake and agent classification."""

from __future__ import annotations

import re
from dataclasses import dataclass


FITS_SCENARIOS = (
    "协商还款",
    "伪冒预防",
    "伪冒调查",
    "客户经营",
    "市场企划",
    "调单扣款",
    "征信",
    "UNKNOWN",
)

LEGACY_SCENE_ALIASES = {
    "优惠券补发": "市场企划",
    "权益资格查询": "市场企划",
    "资料修改": "客户经营",
    "资料变更": "客户经营",
    "交易查询": "调单扣款",
    "交易核查": "调单扣款",
    "交易争议": "调单扣款",
    "征信异议": "征信",
}

LEGACY_INTENT_ALIASES = {
    "COUPON_REISSUE": "市场企划",
    "BENEFIT_QUERY": "市场企划",
    "CUSTOMER_ADDRESS_UPDATE": "客户经营",
    "TRANSACTION_DISPUTE": "调单扣款",
    "APPLICATION_PROGRESS_QUERY": "UNKNOWN",
    "CARD_STATUS_CHANGE": "伪冒调查",
}


@dataclass(frozen=True)
class ScenarioDetection:
    scene: str
    category: str
    subcategory: str
    intent_type: str
    reason: str
    confidence: float = 0.95


_SCENE_PATTERNS: tuple[tuple[str, str, str, str, re.Pattern], ...] = (
    ("伪冒预防", "伪冒", "伪冒预防", "命中伪冒预防业务线索", re.compile(r"非本人申请|冒名|伪冒预防|还款提醒|投诉引导|伪冒交易预警", re.I)),
    ("伪冒调查", "伪冒", "伪冒调查", "命中伪冒调查或卡片管制线索", re.compile(r"伪冒调查|卡片被.*管制|系统管制|两核身|核身不过|X-DK|BLOCK", re.I)),
    ("客户经营", "客户经营", "资料借阅", "命中客户经营资料诉求", re.compile(r"客户经营|资料借阅|结清证明|解抵押|汽车分期结清|接单单位卡部|地址变更|账单地址|资料修改|资料变更|联系人变更|预留手机号", re.I)),
    ("市场企划", "市场企划", "饭票总对总-麦当劳", "命中市场企划或活动权益线索", re.compile(r"市场企划|麦当劳|饭票|影票|掌上生活|订单号|优惠券未到账|优惠券|未收到券|活动达标|权益|贵宾厅|积分|DINING|AIRPORT|POINT|MALL", re.I)),
    ("征信", "征信", "贷后风险核实", "命中征信或贷后风险线索", re.compile(r"征信|账户逾期|逾期状态|贷后历史风险|是否敏感|征信异议|上报记录|E CODE", re.I)),
    ("调单扣款", "调单扣款", "交易调单扣款", "命中交易调单或扣款核查线索", re.compile(r"调单扣款|交易调单|调扣|扣款|公司资料异动|附件|交易|流水|入账|盗刷|非本人|TXN|拒付|商户", re.I)),
    ("协商还款", "协商还款", "客助-协商还款", "命中协商还款线索", re.compile(r"协商还款|还款方案|延期还款|停息|分期偿还|客助", re.I)),
)


def normalize_scene(scene: str, workflow_config: dict | None = None) -> str:
    """Normalize stored or legacy scene labels to the FITS scenario key."""
    scene = (scene or "").strip()
    scenarios = (workflow_config or {}).get("scenarios", {})
    if scene in scenarios:
        return scene
    alias = LEGACY_SCENE_ALIASES.get(scene, scene)
    return alias if alias in scenarios else "UNKNOWN"


def normalize_intent_type(intent_type: str, workflow_config: dict | None = None) -> str:
    """Normalize legacy classifier intent ids to the FITS scenario key."""
    intent_type = (intent_type or "").strip()
    scenarios = (workflow_config or {}).get("scenarios", {})
    if intent_type in scenarios:
        return intent_type
    alias = LEGACY_INTENT_ALIASES.get(intent_type, intent_type)
    return alias if alias in scenarios else "UNKNOWN"


def detect_fits_scenario(text: str, workflow_config: dict | None = None) -> ScenarioDetection:
    """Detect the FITS scenario from structured summary or raw transcript."""
    workflow_config = workflow_config or {}
    text = text or ""
    explicit_scene = _first_match(r"场景[:：]\s*([^\n]+)", text)
    normalized = normalize_scene(explicit_scene, workflow_config)
    if normalized != "UNKNOWN":
        scenario = _scenario_config(normalized, workflow_config)
        return ScenarioDetection(
            scene=normalized,
            category=scenario.get("label") or normalized,
            subcategory=scenario.get("label") or normalized,
            intent_type=normalized,
            reason=f"优先采用工单已登记场景: {explicit_scene}",
            confidence=0.99,
        )

    for scene, category, subcategory, reason, pattern in _SCENE_PATTERNS:
        if pattern.search(text):
            normalized = normalize_scene(scene, workflow_config)
            if normalized != "UNKNOWN":
                return ScenarioDetection(
                    scene=normalized,
                    category=category,
                    subcategory=subcategory,
                    intent_type=normalized,
                    reason=reason,
                )

    scenario = _scenario_config("UNKNOWN", workflow_config)
    return ScenarioDetection(
        scene="UNKNOWN",
        category=scenario.get("label", "未知场景"),
        subcategory="待分类",
        intent_type="UNKNOWN",
        reason="未命中已接入 FITS 场景规则",
        confidence=0.0,
    )


def scenario_result(text: str, workflow_config: dict | None = None) -> dict:
    detection = detect_fits_scenario(text, workflow_config)
    scenario = _scenario_config(detection.intent_type, workflow_config or {})
    return {
        "type": detection.intent_type,
        "label": scenario.get("label") or detection.scene,
        "confidence": detection.confidence,
        "workflow_name": scenario.get("workflow_name") or (workflow_config or {}).get("default_workflow", "unknown_flow"),
        "reason": detection.reason,
    }


def _scenario_config(scene: str, workflow_config: dict) -> dict:
    return (workflow_config.get("scenarios", {}) or {}).get(scene, {})


def _first_match(pattern: str, text: str) -> str:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return match.group(1).strip() if match else ""
