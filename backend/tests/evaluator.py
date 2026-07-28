"""Evaluation helpers for Module F.

The evaluator has two jobs:
- score real Agent outputs collected by ``run_module_f.py``;
- keep ``/api/evaluation/metrics`` useful even before a full LLM-backed
  evaluation run by returning a labeled-sample reference summary.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

EVAL_SAMPLES_JSON = Path(__file__).resolve().parent.parent / "data" / "evaluation_samples.json"

# Baseline: manual processing takes about 120 seconds per ticket.
MANUAL_BASELINE_SECONDS = 120.0

MISSING_VALUES = {
    "",
    None,
    "N/A",
    "UNKNOWN",
    "unknown",
    "\u672a\u63d0\u4f9b",  # Chinese: not provided
}

HUMAN_INTERVENTION_STATUSES = {
    "pending_human_confirm",
    "escalated",
    "failed",
}


@dataclass
class ScoreBucket:
    correct: float = 0.0
    total: float = 0.0

    def add(self, correct: bool | int | float, total: int | float = 1) -> None:
        self.correct += float(correct)
        self.total += float(total)

    @property
    def score(self) -> float:
        if self.total <= 0:
            return 0.0
        return round(self.correct / self.total, 4)

    def as_dict(self) -> dict[str, float | int]:
        return {
            "score": self.score,
            "correct": round(self.correct, 4),
            "total": int(self.total) if self.total.is_integer() else round(self.total, 4),
        }


@dataclass
class EvalMetrics:
    intent_accuracy: float
    field_completeness: float
    tool_correctness: float
    avg_time_saved_seconds: float
    total_samples: int
    agents: dict[str, dict[str, Any]] = field(default_factory=dict)
    closed_loop_success_rate: float = 0.0
    avg_processing_ms: float = 0.0
    evaluated_samples: int = 0
    avg_manual_steps_saved: float = 0.0
    source: str = "unknown"


class Evaluator:
    """Compute metrics from labeled samples and Agent output records."""

    def __init__(self):
        self._samples = self._load_samples()

    @property
    def samples(self) -> list[dict]:
        return self._samples

    def reload(self) -> list[dict]:
        self._samples = self._load_samples()
        return self._samples

    def total_samples(self) -> int:
        return len(self._samples)

    def _load_samples(self) -> list[dict]:
        if not EVAL_SAMPLES_JSON.exists():
            return []
        with open(EVAL_SAMPLES_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError("evaluation_samples.json must contain a JSON array")
        return data

    def _expected(self, sample: dict, field_name: str, default=None):
        expected = sample.get("expected") or {}
        if field_name in expected:
            return expected[field_name]

        legacy_map = {
            "intentType": "expected_intent",
            "expectedFields": "expected_fields",
            "expectedTool": "expected_tool",
        }
        legacy_field = legacy_map.get(field_name)
        if legacy_field:
            return sample.get(legacy_field, default)
        return default

    def compute(
        self,
        records: list[dict] | None = None,
        ai_durations_ms: list[int] | None = None,
    ) -> EvalMetrics:
        """Compute Module F metrics.

        ``records`` should contain actual Agent outputs. If records are omitted,
        the evaluator returns a labeled-sample reference summary so the API no
        longer serves arbitrary demo constants.
        """
        if records:
            return self.compute_records(records, ai_durations_ms=ai_durations_ms)

        reference_records = self._build_reference_records()
        if reference_records:
            logger.info(
                "Evaluator: using labeled-sample reference metrics with total_samples=%s",
                len(reference_records),
            )
            return self.compute_records(
                reference_records,
                ai_durations_ms=ai_durations_ms,
                source="labeled_samples_reference",
            )

        return EvalMetrics(
            intent_accuracy=0.0,
            field_completeness=0.0,
            tool_correctness=0.0,
            avg_time_saved_seconds=0.0,
            total_samples=0,
            evaluated_samples=0,
            source="empty",
        )

    def compute_records(
        self,
        records: list[dict],
        *,
        ai_durations_ms: list[int] | None = None,
        source: str = "agent_run",
    ) -> EvalMetrics:
        sample_count = len(records)
        buckets = {
            "intent": ScoreBucket(),
            "workflow": ScoreBucket(),
            "priority": ScoreBucket(),
            "field_complete": ScoreBucket(),
            "missing": ScoreBucket(),
            "tool": ScoreBucket(),
            "params": ScoreBucket(),
            "execution": ScoreBucket(),
            "reply_points": ScoreBucket(),
            "template": ScoreBucket(),
            "readability": ScoreBucket(),
            "exception": ScoreBucket(),
            "human": ScoreBucket(),
            "status": ScoreBucket(),
        }

        durations = list(ai_durations_ms or [])
        manual_steps_saved = 0.0

        for record in records:
            sample = record.get("sample") or {}
            expected = record.get("expected") or sample.get("expected") or {}
            ticket = record.get("ticket") or sample.get("ticket") or {}
            outputs = record.get("outputs") or record

            intent = _as_dict(outputs.get("intent"))
            fields = _fields_dict(outputs.get("fields"))
            resolution = _as_dict(outputs.get("resolution"))
            tool_result = _as_dict(outputs.get("toolResult") or outputs.get("tool_result"))
            notification = _as_dict(outputs.get("notification"))
            escalation = _as_dict(outputs.get("escalation"))
            status = outputs.get("status") or record.get("status") or ""
            duration_ms = outputs.get("durationMs") or outputs.get("duration_ms") or record.get("duration_ms")
            if isinstance(duration_ms, (int, float)):
                durations.append(int(duration_ms))

            expected_intent = expected.get("intentType", "")
            expected_workflow = expected.get("workflowName", "")
            expected_tool = expected.get("expectedTool", "")
            expected_status = expected.get("expectedStatus", "")
            expected_fields = expected.get("expectedFields", {}) or {}
            required_fields = expected.get("requiredFields", []) or list(expected_fields.keys())
            expected_requires_human = bool(expected.get("requiresHuman", False))

            buckets["intent"].add(intent.get("type") == expected_intent)
            buckets["workflow"].add(intent.get("workflowName") == expected_workflow or intent.get("workflow_name") == expected_workflow)
            buckets["priority"].add(_priority_matches(ticket, expected, status, escalation))

            for field_name in required_fields:
                expected_value = expected_fields.get(field_name)
                actual_value = fields.get(field_name)
                expected_missing = _is_missing(expected_value)
                actual_missing = _is_missing(actual_value)
                if not expected_missing:
                    buckets["field_complete"].add(not actual_missing)
                buckets["missing"].add(expected_missing == actual_missing)

            selected_tool = resolution.get("toolName") or resolution.get("tool_name") or outputs.get("toolName") or outputs.get("tool_name") or ""
            should_score_resolution = (
                expected_status not in {"pending_info", "pending_human_confirm", "escalated"}
                or bool(selected_tool)
            )
            if expected_tool and should_score_resolution:
                buckets["tool"].add(selected_tool == expected_tool)

            tool_params = _as_dict(resolution.get("toolParams") or resolution.get("tool_params") or outputs.get("toolRequest") or outputs.get("tool_request"))
            param_keys = [key for key in required_fields if key in expected_fields and not _is_missing(expected_fields.get(key))]
            for key in param_keys:
                if key in tool_params:
                    buckets["params"].add(_value_matches(tool_params.get(key), expected_fields.get(key), field_name=key))
                elif selected_tool:
                    buckets["params"].add(False)

            expected_tool_execution = bool(expected_tool and expected_status == "pending_human_review")
            actual_tool_success = bool(tool_result.get("success"))
            if should_score_resolution and (expected_tool_execution or selected_tool):
                buckets["execution"].add(actual_tool_success == expected_tool_execution)

            reply_body = _notification_body(notification, outputs.get("replyDraft") or outputs.get("reply_draft", ""))
            reply_points = expected.get("replyPoints", []) or []
            for point in reply_points:
                buckets["reply_points"].add(_reply_point_covered(reply_body, str(point), expected, tool_result, notification))

            buckets["template"].add(_notification_has_required_shape(notification))
            buckets["readability"].add(_readability_score(reply_body))

            expected_exception = expected_status in {"pending_info", "pending_human_confirm", "escalated", "failed"}
            actual_exception = status in {"pending_info", "pending_human_confirm", "escalated", "failed"} or bool(escalation.get("needsMoreInfo") or escalation.get("needs_more_info"))
            buckets["exception"].add(expected_exception == actual_exception)

            actual_requires_human = _actual_requires_human(status, escalation, outputs, notification)
            buckets["human"].add(actual_requires_human == expected_requires_human)
            buckets["status"].add(status == expected_status)

            manual_steps_saved += _estimate_manual_steps_saved(status, selected_tool, actual_tool_success)

        avg_processing_ms = round(sum(durations) / len(durations), 1) if durations else 0.0
        avg_ai_time = avg_processing_ms / 1000 if avg_processing_ms else 0.0
        time_saved = round(max(MANUAL_BASELINE_SECONDS - avg_ai_time, 0.0), 1)

        agents = {
            "classifier": {
                "intentAccuracy": buckets["intent"].as_dict(),
                "workflowConsistency": buckets["workflow"].as_dict(),
                "priorityConsistency": buckets["priority"].as_dict(),
            },
            "intake": {
                "fieldCompleteness": buckets["field_complete"].as_dict(),
                "missingFieldAccuracy": buckets["missing"].as_dict(),
            },
            "resolution": {
                "toolCorrectness": buckets["tool"].as_dict(),
                "parameterAccuracy": buckets["params"].as_dict(),
                "executionSuccess": buckets["execution"].as_dict(),
            },
            "notification": {
                "replyPointCoverage": buckets["reply_points"].as_dict(),
                "templateCompliance": buckets["template"].as_dict(),
                "readabilityScore": buckets["readability"].as_dict(),
            },
            "escalation": {
                "exceptionRecognition": buckets["exception"].as_dict(),
                "humanInterventionAccuracy": buckets["human"].as_dict(),
            },
        }

        return EvalMetrics(
            intent_accuracy=buckets["intent"].score,
            field_completeness=buckets["field_complete"].score,
            tool_correctness=buckets["tool"].score,
            avg_time_saved_seconds=time_saved,
            total_samples=len(self._samples) or sample_count,
            agents=agents,
            closed_loop_success_rate=buckets["status"].score,
            avg_processing_ms=avg_processing_ms,
            evaluated_samples=sample_count,
            avg_manual_steps_saved=round(manual_steps_saved / sample_count, 1) if sample_count else 0.0,
            source=source,
        )

    def _build_reference_records(self) -> list[dict]:
        records = []
        for sample in self._samples:
            expected = sample.get("expected") or {}
            ticket = sample.get("ticket") or {}
            expected_fields = expected.get("expectedFields", {}) or {}
            fields = [
                {"name": name, "label": name, "value": value}
                for name, value in expected_fields.items()
            ]
            tool_name = expected.get("expectedTool", "")
            expected_status = expected.get("expectedStatus", "")
            tool_success = bool(tool_name and expected_status == "pending_human_review")
            notification = _reference_notification(expected, tool_success)
            records.append({
                "sample": sample,
                "ticket": ticket,
                "expected": expected,
                "outputs": {
                    "intent": {
                        "type": expected.get("intentType", ""),
                        "workflowName": expected.get("workflowName", ""),
                    },
                    "fields": fields,
                    "resolution": {
                        "toolName": tool_name,
                        "toolParams": {
                            name: value
                            for name, value in expected_fields.items()
                            if not _is_missing(value)
                        },
                    },
                    "toolResult": {
                        "success": tool_success,
                        "evidenceId": "EVAL-REFERENCE" if tool_success else "",
                    },
                    "notification": notification,
                    "escalation": {
                        "needsMoreInfo": expected_status == "pending_info",
                        "canAutoProceed": expected_status == "pending_human_review",
                    },
                    "status": expected_status,
                    "durationMs": 3500,
                    "requiresHumanReview": expected.get("requiresHuman", False),
                },
            })
        return records


def _as_dict(value: Any) -> dict:
    if not value:
        return {}
    if hasattr(value, "model_dump"):
        return value.model_dump(by_alias=True)
    return value if isinstance(value, dict) else {}


def _fields_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    fields = {}
    if isinstance(value, list):
        for field_item in value:
            item = _as_dict(field_item)
            name = item.get("name")
            if name:
                fields[name] = item.get("value")
    return fields


def _is_missing(value: Any) -> bool:
    if value in MISSING_VALUES:
        return True
    if isinstance(value, str) and value.strip() in MISSING_VALUES:
        return True
    return False


def _priority_matches(ticket: dict, expected: dict, status: str, escalation: dict) -> bool:
    risk_level = ticket.get("riskLevel") or ticket.get("risk_level") or "low"
    expected_requires_human = bool(expected.get("requiresHuman", False))
    if risk_level == "high":
        return status == "escalated" or not bool(escalation.get("canAutoProceed", escalation.get("can_auto_proceed", True)))
    if expected_requires_human:
        return status in HUMAN_INTERVENTION_STATUSES
    return status in {"pending_human_review", "pending_info"}


def _notification_body(notification: dict, fallback: str = "") -> str:
    standard = _as_dict(notification.get("standardReply") or notification.get("standard_reply"))
    return str(standard.get("body") or fallback or "")


def _contains_point(body: str, point: str) -> bool:
    if not point:
        return True
    normalized_body = _normalize_text(body)
    normalized_point = _normalize_text(point)
    if normalized_point in normalized_body:
        return True
    tokens = [token for token in normalized_point.split() if len(token) >= 2]
    if tokens and all(token in normalized_body for token in tokens):
        return True

    point_chars = _meaningful_chars(normalized_point)
    body_chars = _meaningful_chars(normalized_body)
    if not point_chars:
        return False
    overlap = sum(1 for char in point_chars if char in body_chars)
    return overlap / len(point_chars) >= 0.6


def _reply_point_covered(
    body: str,
    point: str,
    expected: dict,
    tool_result: dict,
    notification: dict,
) -> bool:
    if _contains_point(body, point):
        return True

    body_text = _normalize_text(body)
    point_text = _normalize_text(point)
    evidence_id = tool_result.get("evidenceId") or tool_result.get("evidence_id") or ""
    business_result = str(tool_result.get("businessResult") or tool_result.get("business_result") or "")
    next_step = str(tool_result.get("nextStep") or tool_result.get("next_step") or "")
    expected_result = str(expected.get("expectedResult", ""))
    review_summary = _as_dict(notification.get("reviewSummary") or notification.get("review_summary"))
    missing_fields = review_summary.get("missingFields") or review_summary.get("missing_fields") or []

    if expected.get("expectedStatus") in {"escalated", "pending_human_confirm"}:
        if _has_any(point_text, _KW_MANUAL_CONTEXT):
            return _has_any(body_text, _KW_MANUAL_RESPONSE)

    if _has_any(point_text, _KW_EVIDENCE):
        return bool(evidence_id and evidence_id in body_text)

    if _has_any(point_text, _KW_FOLLOW_UP):
        return _has_any(body_text, _KW_FOLLOW_UP) or _contains_point(body_text, next_step)

    if _has_any(point_text, _KW_MISSING):
        missing_text = " ".join(str(item) for item in missing_fields)
        return _has_any(body_text, _KW_MISSING) or any(str(item) in body_text for item in missing_fields) or _contains_point(body_text, missing_text)

    if _has_any(point_text, _KW_STATUS_RESULT):
        return (
            _has_any(body_text, _KW_STATUS_RESULT)
            or _contains_point(body_text, business_result)
            or _contains_point(body_text, expected_result)
        )

    if business_result and _contains_point(body_text, business_result):
        return True
    return bool(expected_result and _contains_point(body_text, expected_result))


def _normalize_text(value: str) -> str:
    return " ".join(str(value).replace("\n", " ").replace("，", " ").replace("。", " ").split())


_KW_EVIDENCE = (
    "\u8bc1\u636e",  # evidence
    "\u7f16\u53f7",  # id/no.
    "\u51ed\u8bc1",  # voucher/proof
)
_KW_FOLLOW_UP = (
    "App",
    "APP",
    "\u67e5\u770b",
    "\u67e5\u6536",
    "\u7559\u610f",
    "\u63d0\u793a",
    "\u4f7f\u7528",
    "\u6709\u6548\u671f",
    "\u8054\u7cfb",
    "\u6c9f\u901a",
)
_KW_MISSING = (
    "\u8865\u5145",
    "\u7f3a\u5931",
    "\u672a\u63d0\u4f9b",
    "\u5f85\u8865\u5145",
)
_KW_STATUS_RESULT = (
    "\u5df2",
    "\u6838\u5b9e",
    "\u5904\u7406",
    "\u7ed3\u679c",
    "\u8865\u53d1",
    "\u8fdb\u5ea6",
    "\u8282\u70b9",
    "\u9884\u8ba1",
    "\u5347\u7ea7",
    "\u590d\u6838",
)
_KW_MANUAL_CONTEXT = (
    "\u4eba\u5de5",
    "\u786e\u8ba4",
    "\u590d\u6838",
    "\u5347\u7ea7",
    "\u8ddf\u8fdb",
    "\u5b89\u5168",
    "\u5f02\u5e38",
    "\u6295\u8bc9",
    "\u8bb0\u5f55",
    "\u8d23\u4efb",
    "\u72b6\u6001",
    "\u751f\u6548",
    "\u540e\u7eed",
    "\u51ed\u8bc1",
)
_KW_MANUAL_RESPONSE = (
    "\u4eba\u5de5",
    "\u786e\u8ba4",
    "\u590d\u6838",
    "\u8f6c",
    "\u4e13\u5458",
    "\u8ddf\u8fdb",
    "\u5904\u7406",
    "\u63a5\u7ba1",
)


def _has_any(value: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword and keyword in value for keyword in keywords)


_STRICT_VALUE_FIELDS = {
    "customerId",
    "couponType",
    "applicationNo",
    "verifyStatus",
    "benefitCode",
    "transactionId",
    "transactionDate",
    "amount",
}


def _value_matches(actual: Any, expected: Any, *, field_name: str = "") -> bool:
    if _is_missing(expected):
        return _is_missing(actual)
    if str(actual) == str(expected):
        return True
    actual_text = _normalize_text(str(actual))
    expected_text = _normalize_text(str(expected))
    if field_name in _STRICT_VALUE_FIELDS:
        return expected_text in actual_text.split()
    if expected_text and expected_text in actual_text:
        return True
    if actual_text and actual_text in expected_text:
        return True
    expected_chars = _meaningful_chars(expected_text)
    actual_chars = _meaningful_chars(actual_text)
    if not expected_chars:
        return False
    overlap = sum(1 for char in expected_chars if char in actual_chars)
    return overlap / len(expected_chars) >= 0.75


def _meaningful_chars(value: str) -> list[str]:
    ignored = set(" \t\r\n，。；：、,.!?！？（）()[]【】《》\"'“”‘’")
    return [char for char in str(value) if char not in ignored]


def _notification_has_required_shape(notification: dict) -> bool:
    required = (
        ("standardReply", "standard_reply"),
        ("internalNotice", "internal_notice"),
        ("reviewSummary", "review_summary"),
        ("closureSuggestion", "closure_suggestion"),
        ("followUp", "follow_up"),
    )
    return all(any(isinstance(notification.get(key), dict) for key in variants) for variants in required)


def _readability_score(body: str) -> float:
    if not body:
        return 0.0
    score = 1.0
    if len(body) < 20:
        score -= 0.4
    if len(body) > 800:
        score -= 0.2
    if "{" in body or "}" in body:
        score -= 0.2
    lowered = body.lower()
    if "todo" in lowered or "debug" in lowered or "traceback" in lowered:
        score -= 0.4
    return max(round(score, 2), 0.0)


def _actual_requires_human(status: str, escalation: dict, outputs: dict, notification: dict) -> bool:
    if status in HUMAN_INTERVENTION_STATUSES:
        return True
    if status == "pending_info":
        intent = _as_dict(outputs.get("intent"))
        if intent.get("type") in {"CUSTOMER_ADDRESS_UPDATE", "TRANSACTION_DISPUTE", "UNKNOWN"}:
            return True
        return False
    if status == "pending_human_review":
        return False
    if escalation and not bool(escalation.get("canAutoProceed", escalation.get("can_auto_proceed", True))):
        return True
    closure = _as_dict(notification.get("closureSuggestion") or notification.get("closure_suggestion"))
    return bool(closure.get("requiresHumanReview") or closure.get("requires_human_review"))


def _estimate_manual_steps_saved(status: str, selected_tool: str, tool_success: bool) -> int:
    if tool_success and selected_tool:
        return 5
    if status == "pending_info":
        return 2
    if status in {"pending_human_confirm", "pending_human_review"}:
        return 3
    if status == "escalated":
        return 1
    return 0


def _reference_notification(expected: dict, tool_success: bool) -> dict:
    body = "\n".join(expected.get("replyPoints", [])) or expected.get("expectedResult", "")
    return {
        "standardReply": {
            "title": "Evaluation reference reply",
            "body": body,
            "status": "ready" if tool_success else "needs_review",
            "evidenceIds": ["EVAL-REFERENCE"] if tool_success else [],
            "nextOwner": "human",
        },
        "internalNotice": {
            "title": "Evaluation reference notice",
            "body": expected.get("expectedResult", ""),
            "status": "ready" if tool_success else "needs_review",
            "evidenceIds": ["EVAL-REFERENCE"] if tool_success else [],
            "nextOwner": "human",
        },
        "reviewSummary": {
            "reason": expected.get("expectedResult", ""),
            "riskDecision": expected.get("expectedStatus", ""),
            "missingFields": [],
            "toolEvidenceIds": ["EVAL-REFERENCE"] if tool_success else [],
            "suggestedAction": expected.get("expectedResult", ""),
        },
        "closureSuggestion": {
            "canClose": tool_success,
            "reason": expected.get("expectedResult", ""),
            "finalReply": body,
            "requiresHumanReview": not tool_success,
        },
        "followUp": {
            "enabled": tool_success,
            "template": "Evaluation follow-up",
            "triggerStatus": "closed" if tool_success else "",
        },
    }


evaluator = Evaluator()
