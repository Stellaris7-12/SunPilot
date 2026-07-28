"""Call-record → ticket-draft → page-task pipeline.

Extracted verbatim from the FastAPI entry point. Config-driven: field maps,
scenarios and SLA come from ``workflow_config.json`` / ``semantic_targets.json``.
Deterministic extraction only — no LLM calls live here.
"""

import json
import logging
import re
import uuid
from datetime import datetime, timedelta

from ticket_agent.config import CALL_TRANSCRIPTS_JSON
from ticket_agent.models.schemas.api_schemas import DraftKeyField, PageTaskHint
from ticket_agent.models.schemas.ai_result import PageTaskActionEnvelope, PageTaskEnvelope
from ticket_agent.repositories.repositories import ai_result_repository, call_record_repository
from ticket_agent.models.domain.scenario_detection import (
    detect_fits_scenario,
    normalize_scene,
    scenario_display_label,
)
from ticket_agent.orchestrator.field_extractor import extract_common_fields, extract_specific_fields
from ticket_agent.orchestrator.semantic_targets import load_semantic_targets
from ticket_agent.orchestrator.trace import TraceCollector
from ticket_agent.orchestrator.workflow_config import load_workflow_config

from ticket_agent.api.serializers import public_result

logger = logging.getLogger(__name__)

async def persist_ai_result(ticket_id: str, trace: TraceCollector, result: dict):
    await ai_result_repository.insert_ai_result(ticket_id, trace, result, public_result(result))


def load_call_records() -> list[dict]:
    if not CALL_TRANSCRIPTS_JSON.exists():
        return []
    with CALL_TRANSCRIPTS_JSON.open("r", encoding="utf-8") as file:
        data = json.load(file)
    return data if isinstance(data, list) else []


async def ensure_call_record_samples_persisted():
    for item in load_call_records():
        await call_record_repository.upsert_call_record(item)


def call_record_response(row: dict) -> dict:
    raw = json.loads(row.get("raw_json") or "{}")
    call_meta = raw.get("callMeta") or {
        "customerId": row.get("customer_id") or "",
        "customerName": row.get("customer_name") or "",
        "phone": row.get("phone") or "",
        "cardLast4": row.get("card_last4") or "",
        "channel": row.get("channel") or "",
        "agent": row.get("agent") or "",
        "callStartedAt": row.get("call_started_at") or "",
    }
    raw_scenario = row.get("scenario", "") or ""
    return {
        "id": row.get("id", ""),
        "source": row.get("source", ""),
        # 统一按 FITS 场景键输出，供前端业务分类过滤/展示
        "scenario": normalize_scene(raw_scenario, load_workflow_config()),
        "scenarioLabel": scenario_display_label(raw_scenario, load_workflow_config()),
        "riskLevel": row.get("risk_level", "low"),
        "callMeta": call_meta,
        "transcript": row.get("transcript", ""),
    }


def row_raw_json(row: dict | None) -> dict:
    if not row:
        return {}
    try:
        raw = json.loads(row.get("raw_json") or "{}")
        return raw if isinstance(raw, dict) else {}
    except json.JSONDecodeError:
        return {}


def compact_summary(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    customer_lines = [line for line in lines if line.startswith("客户")]
    basis = customer_lines or lines
    summary = "；".join(line.split("：", 1)[-1] for line in basis[:3])
    return summary[:180] or "已读取通话记录，等待坐席补充关键信息。"


def first_match(pattern: str, text: str) -> str:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return match.group(1).strip() if match else ""


def scenario_config(scene: str) -> dict:
    config = load_workflow_config()
    return (config.get("scenarios", {}) or {}).get(normalize_scene(scene, config), {})


def scenario_specific_fields(scene: str) -> list[dict]:
    fields = scenario_config(scene).get("specific_fields") or []
    return fields if isinstance(fields, list) else []


def default_option(field: dict) -> str:
    options = field.get("options") or []
    return str(options[0]) if options else ""


def scenario_deadline(scene: str) -> str:
    sla_days = int(scenario_config(scene).get("sla_days") or 0)
    if sla_days <= 0:
        return ""
    return (datetime.now() + timedelta(days=sla_days)).strftime("%Y-%m-%d %H:%M:%S")


def draft_ext_json(scene: str, transcript: str, draft: dict, call_meta: dict | None = None) -> dict:
    """P2-10: 配置驱动的字段抽取，替换硬编码的巨型 elif 链。

    现在从 workflow_config.json 的 specificFields[].extractRule 读取抽取规则，
    新增场景只需在配置中添加字段定义和 extractRule，无需修改代码。
    """
    workflow_config = load_workflow_config()
    scenario_cfg = workflow_config.get("scenarios", {}).get(scene, {})

    # 准备上下文（供 extractRule 使用）
    context = {
        **draft,
        **(call_meta or {}),
        "scene": scene,
    }

    # 使用配置驱动的抽取引擎
    ext = extract_specific_fields(scene, scenario_cfg, transcript, context)

    return ext


def apply_dispatch_config(draft: dict, transcript: str, call_meta: dict | None = None) -> dict:
    workflow_config = load_workflow_config()
    scene = normalize_scene(draft.get("scene", ""), workflow_config)
    if scene == "UNKNOWN":
        detected = detect_fits_scenario(transcript, workflow_config)
        scene = detected.scene
        if scene != "UNKNOWN":
            draft["category"] = draft.get("category") or detected.category
            draft["subcategory"] = draft.get("subcategory") or detected.subcategory
    if scene != "UNKNOWN":
        draft["scene"] = scene
    config = scenario_config(scene)
    if not config:
        return draft
    ext_json = dict(draft.get("extJson") or draft.get("ext_json") or {})
    generated_ext = draft_ext_json(scene, transcript, draft, call_meta)
    ext_json = {**generated_ext, **ext_json}
    draft["extJson"] = ext_json
    draft["orderPrefix"] = config.get("order_prefix") or ""
    draft["category"] = draft.get("category") or config.get("label") or scene
    draft["bizType"] = draft.get("category") or config.get("label") or scene
    draft["bizSubType"] = draft.get("subcategory") or ext_json.get("bizSubType") or ""
    draft["receiveUnit"] = draft.get("receiveUnit") or ext_json.get("receiveUnit") or ""
    draft["deadline"] = draft.get("deadline") or draft.get("dueAt") or scenario_deadline(scene)
    draft["dueAt"] = draft.get("dueAt") or draft["deadline"]
    draft["needReply"] = draft.get("needReply", True)
    return draft


def detect_call_scenario(text: str) -> tuple[str, str, str, str]:
    detection = detect_fits_scenario(text, load_workflow_config())
    if detection.intent_type == "UNKNOWN":
        return "人工客服发单", "综合服务", "待分类", "UNKNOWN"
    return detection.scene, detection.category, detection.subcategory, detection.intent_type


def build_key_fields(draft: dict, expected: dict | None = None) -> list[DraftKeyField]:
    source_fields = expected.get("keyFields", {}) if expected else {}
    fields = {
        "customerId": draft.get("customerId") or source_fields.get("customerId") or "",
        "customerName": draft.get("customerName") or "",
        "cardLast4": draft.get("cardLast4") or "",
        "scene": draft.get("scene") or "",
    }
    for key, value in source_fields.items():
        if key not in fields:
            fields[key] = str(value)
    labels = {
        "customerId": "客户号",
        "customerName": "客户姓名",
        "cardLast4": "卡尾号",
        "scene": "业务场景",
        "couponType": "券类型",
        "benefitCode": "权益编码",
        "applicationNo": "申请单号",
        "transactionId": "交易流水",
        "field": "变更字段",
        "newValue": "变更内容",
    }
    return [
        DraftKeyField(name=name, label=labels.get(name, name), value=str(value), source="通话文本")
        for name, value in fields.items()
        if str(value).strip()
    ]


def missing_draft_fields(draft: dict) -> list[str]:
    required = {
        "title": "标题",
        "customerName": "客户姓名",
        "phone": "预留手机",
        "cardLast4": "卡尾号",
        "scene": "业务场景",
        "content": "发单内容",
    }
    return [label for key, label in required.items() if not str(draft.get(key) or "").strip()]


def build_page_task_hints(draft: dict, missing_fields: list[str]) -> list[PageTaskHint]:
    """P1-4: 使用统一配置构建页面任务提示。

    从 semantic_targets.json 读取 target 定义，确保前后端一致。
    """
    semantic_config = load_semantic_targets()
    hints = [
        PageTaskHint(action="open", target="call-intake-workspace", label="打开通话发单工作区"),
    ]

    # 从配置获取字段对应的 target 标签
    target_labels = semantic_config.get_target_labels("call-intake")

    field_labels = {
        "title": "标题",
        "customerId": "客户号",
        "customerName": "客户姓名",
        "phone": "预留手机",
        "cardLast4": "卡尾号",
        "scene": "业务场景",
        "category": "业务大类",
        "subcategory": "业务小类",
        "priority": "优先级",
        "riskLabel": "风险标签",
        "riskLevel": "风险等级",
        "content": "发单内容",
    }
    for field, label in field_labels.items():
        target = f"dispatch-{field}"
        # 验证 target 是否在配置中定义
        if not semantic_config.is_valid_target("call-intake", target):
            logger.warning(f"Target '{target}' not found in semantic_targets.json")
        hints.append(PageTaskHint(
            action="fill",
            target=target,
            label=f"填写{label}",
            field=field,
            value=str(draft.get(field) or ""),
            source="来电内容",
            required=label in missing_fields,
        ))

    specific_labels = {
        field.get("name", ""): field.get("label") or field.get("name", "")
        for field in scenario_specific_fields(draft.get("scene", ""))
    }
    for field, value in (draft.get("extJson") or draft.get("ext_json") or {}).items():
        target = f"dispatch-{field}"
        hints.append(PageTaskHint(
            action="fill",
            target=target,
            label=f"填写{specific_labels.get(field, field)}",
            field=f"extJson.{field}",
            value=str(value or ""),
            source="来电内容",
            required=False,
        ))

    # 提交按钮 - 优先使用 dispatch-submit
    hints.append(PageTaskHint(
        action="submit" if not missing_fields else "stop",
        target="dispatch-submit",
        label="字段完整，提交标准工单" if not missing_fields else "字段不足，等待人工补充",
        source="发单规则",
        required=not missing_fields,
    ))

    # draft-submit 作为兼容别名（已在配置中标记为 deprecated）
    hints.append(PageTaskHint(
        action="alias",
        target="draft-submit",
        label="提交标准工单",
        source="兼容旧发单目标",
        required=False,
    ))
    return hints


def build_page_task_from_hints(
    draft: dict,
    hints: list[PageTaskHint],
    missing_fields: list[str],
    source_call_id: str,
) -> PageTaskEnvelope:
    kind_by_action = {
        "open": "openPanel",
        "fill": "fillForm",
        "submit": "clickSemantic",
        "stop": "stopForHuman",
    }
    actions = [
        PageTaskActionEnvelope(
            kind=kind_by_action.get(hint.action, "clickSemantic"),
            target=hint.target,
            label=hint.label,
            field=hint.field,
            value=hint.value,
            required=hint.required,
        )
        for hint in hints
        if hint.action != "alias"
    ]
    return PageTaskEnvelope(
        id=f"draft-{source_call_id or uuid.uuid4().hex[:8]}",
        source="call_intake",
        scene="call-intake",
        risk_level=draft.get("riskLevel") or draft.get("risk_level") or "low",
        mode="suggest" if missing_fields else "auto",
        business_payload={
            "ticketDraft": draft,
            "missingFields": missing_fields,
        },
        actions=actions,
        allowed_targets=[action.target for action in actions if action.target],
        # 演示模式：关闭人工确认要求，允许 PageAgent 自动填表演示
        requires_human_before_submit=False,
        stop_reason=f"字段不足：{'、'.join(missing_fields)}" if missing_fields else "",
    )


def draft_from_transcript(
    transcript: str, call_meta: dict | None = None
) -> tuple[dict, str, str, list[DraftKeyField]]:
    meta = call_meta or {}
    workflow_config = load_workflow_config()

    # 准备上下文（供 extractRule 使用）
    context = {**meta}

    # 使用配置驱动提取通用字段
    common_extracted = extract_common_fields(workflow_config, transcript, context)

    customer_id = common_extracted.get("customerId") or meta.get("customerId") or meta.get("customer_id") or ""
    card_last4 = common_extracted.get("cardLast4") or meta.get("cardLast4") or meta.get("card_last4") or ""
    phone = common_extracted.get("phone") or meta.get("phone") or "待补充"
    customer_name = common_extracted.get("customerName") or meta.get("customerName") or meta.get("customer_name") or "待补充客户"
    business_code = common_extracted.get("businessCode") or ""

    scene, category, subcategory, ticket_type = detect_call_scenario(transcript)
    summary = compact_summary(transcript)
    title = f"{scene} - {customer_id or customer_name or '待补充客户'}"
    if scene == "优惠券补发":
        title = "活动达标未收到优惠券"
    elif scene == "交易查询":
        title = "交易入账/争议核查"
    draft = {
        "title": title,
        "customerId": customer_id,
        "customerName": customer_name,
        "phone": phone,
        "cardLast4": card_last4 or "待补充",
        "scene": scene,
        "category": category,
        "subcategory": subcategory,
        "priority": "normal",
        "channel": meta.get("channel") or "客服热线发单",
        "assignee": meta.get("agent") or "坐席 A1027",
        "department": "信用卡运营组",
        "riskLabel": "中风险" if scene == "资料变更" else "低风险",
        "riskLevel": "medium" if scene == "资料变更" else "low",
        "content": f"{summary}。{('关键业务编号：' + business_code + '。') if business_code else ''}原始通话已整理为标准工单，发送后进入接单处理。",
    }
    draft = apply_dispatch_config(draft, transcript, meta)
    key_fields = build_key_fields(draft)
    return draft, summary, ticket_type, key_fields





