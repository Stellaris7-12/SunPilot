"""Production-like mock tool executor for local business-system calls."""

import asyncio
import logging
import re
import time
import uuid
from datetime import datetime
from typing import Any

from models.repositories import mock_business_repository
from models.tool_schemas import ToolResult
from tools.registry import tool_registry

logger = logging.getLogger(__name__)

_PREFIX_MAP = {
    "coupon": "CP",
    "customer": "CUS",
    "card": "CARD",
    "transaction": "TXN",
    "benefit": "BEN",
    "application": "APP",
    "merchant": "MCH",
    "statement": "BILL",
    "ticket": "TKT",
}

_MISSING_VALUES = {"", "N/A", "UNKNOWN", "未提供", None}


class MockExecutor:
    """Simulates external business APIs with domain data, gates, and idempotency."""

    def __init__(self, registry=None):
        self._registry = registry or tool_registry

    async def execute(self, tool_name: str, params: dict) -> ToolResult:
        tool_def = self._registry.get(tool_name)
        if tool_def is None:
            return self._result(
                tool_name,
                False,
                "TOOL_NOT_FOUND",
                f"Tool {tool_name} is not registered.",
                requires_human=True,
                duration_ms=0,
            )

        is_valid, message = self._registry.validate_params(tool_name, params)
        if not is_valid:
            return self._result(
                tool_name,
                False,
                "MISSING_PARAMS",
                message,
                requires_human=False,
                duration_ms=0,
            )

        start = time.time()
        await asyncio.sleep(tool_def.mock_delay_ms / 1000)
        response = await self._dispatch(tool_name, params or {}, tool_def.category, tool_def.requires_confirmation)
        elapsed_ms = int((time.time() - start) * 1000)
        response["durationMs"] = elapsed_ms

        logger.info(
            "[MockExecutor] %s executed - evidence_id=%s, duration=%sms",
            tool_name,
            response.get("evidenceId", ""),
            elapsed_ms,
        )
        return self._to_tool_result(tool_name, response)

    async def enrich_params(self, tool_name: str, params: dict, ticket=None) -> tuple[dict, dict]:
        """Fill missing tool parameters with read-only mock-domain queries."""
        enriched = dict(params or {})
        filled: dict[str, Any] = {}
        unresolved: list[str] = []
        source_tools: list[str] = []
        evidence_ids: list[str] = []

        candidate_customer_id = enriched.get("customerId") or getattr(ticket, "customer_id", "")
        lookup_params = {
            "customerId": "" if _is_missing(candidate_customer_id) else candidate_customer_id,
            "cardLast4": enriched.get("cardLast4") or getattr(ticket, "card_last4", ""),
        }
        customer = await mock_business_repository.find_customer(lookup_params)
        if customer and _is_missing(enriched.get("customerId")):
            enriched["customerId"] = customer["customer_id"]
            filled["customerId"] = customer["customer_id"]
            source_tools.append("customer.lookup")

        content = getattr(ticket, "content", "") if ticket is not None else ""
        code = _extract_business_code(content)
        if tool_name == "coupon.reissue" and _is_missing(enriched.get("couponType")) and code:
            enriched["couponType"] = code
            filled["couponType"] = code
            source_tools.append("coupon.status-query")
        if tool_name in {"benefit.query", "benefit.entitlement-query"} and _is_missing(enriched.get("benefitCode")):
            benefit = await mock_business_repository.get_benefit(enriched.get("customerId", ""), code or "")
            if benefit:
                enriched["benefitCode"] = benefit["benefit_code"]
                filled["benefitCode"] = benefit["benefit_code"]
                source_tools.append("benefit.entitlement-query")
        if tool_name == "application.progress-query" and _is_missing(enriched.get("applicationNo")):
            app = await mock_business_repository.get_application(enriched.get("customerId", ""))
            if app:
                enriched["applicationNo"] = app["application_no"]
                filled["applicationNo"] = app["application_no"]
                source_tools.append("application.progress-query")
        if tool_name in {"transaction.query", "transaction.detail-query"}:
            transaction = await mock_business_repository.get_transaction({
                "customerId": enriched.get("customerId"),
                "amount": enriched.get("amount"),
                "merchantName": enriched.get("merchantName"),
            })
            if transaction:
                for target, source in (
                    ("transactionId", "transaction_id"),
                    ("amount", "amount"),
                    ("merchantName", "merchant"),
                ):
                    if _is_missing(enriched.get(target)):
                        enriched[target] = transaction[source]
                        filled[target] = transaction[source]
                if _is_missing(enriched.get("transactionDate")):
                    enriched["transactionDate"] = str(transaction["transaction_time"])[:10]
                    filled["transactionDate"] = enriched["transactionDate"]
                source_tools.append("transaction.detail-query")

        missing = self._registry.get_missing_required_params(tool_name, enriched)
        unresolved = [item["name"] for item in missing]
        if filled:
            evidence_ids.append(self._generate_evidence_id("enrichment"))
        return enriched, {
            "filledFields": filled,
            "unresolvedFields": unresolved,
            "sourceTools": sorted(set(source_tools)),
            "evidenceIds": evidence_ids,
            "confidence": 0.86 if filled and not unresolved else 0.55,
            "conflicts": [],
            "requiresHumanReview": bool(unresolved),
        }

    async def _dispatch(self, tool_name: str, params: dict, category: str, requires_confirmation: bool) -> dict:
        if tool_name in {"customer.lookup", "customer.profile-query"}:
            return await self._customer_result(tool_name, params, category)
        if tool_name == "card.account-status-query":
            card = await mock_business_repository.get_card(params.get("customerId", ""), params.get("cardLast4", ""))
            return self._query_result(tool_name, category, "CARD_FOUND", "Card account is active.", {"card": card}, found=bool(card))
        if tool_name in {"benefit.query", "benefit.entitlement-query", "campaign.eligibility-check"}:
            benefit = await mock_business_repository.get_benefit(
                params.get("customerId", ""),
                params.get("benefitCode") or params.get("couponType") or "",
            )
            return self._query_result(tool_name, "benefit", "BENEFIT_FOUND", "Benefit entitlement found.", {"benefit": benefit}, found=bool(benefit))
        if tool_name in {"application.progress-query"}:
            app = await mock_business_repository.get_application(params.get("customerId", ""), params.get("applicationNo", ""))
            return self._query_result(tool_name, "application", "APPLICATION_FOUND", "Application progress found.", {"application": app}, found=bool(app))
        if tool_name in {"transaction.query", "transaction.detail-query"}:
            transaction = await mock_business_repository.get_transaction(params)
            if transaction is None:
                transaction = await mock_business_repository.get_transaction({"customerId": params.get("customerId")})
            return self._query_result(tool_name, "transaction", "TRANSACTION_FOUND", "Transaction located for review.", {"transaction": transaction}, found=bool(transaction), requires_human=True)
        if tool_name == "coupon.status-query":
            history = await mock_business_repository.get_history(customer_id=params.get("customerId", ""), tool_name="coupon.reissue")
            return self._query_result(tool_name, "coupon", "COUPON_HISTORY_FOUND", "Coupon delivery history checked.", {"history": history}, found=True)
        if tool_name == "coupon.reissue":
            return await self._coupon_reissue(params)
        if tool_name == "customer.update-address":
            if not _verify_passed(params.get("verifyStatus")):
                return self._base_response(tool_name, "customer", False, "VERIFY_REQUIRED", "Address update requires identity verification.", requires_human=True)
            return await self._controlled_success(tool_name, params, "customer", "ADDRESS_UPDATE_ACCEPTED", "Address update accepted after human confirmation.", requires_human=False)
        if tool_name == "dispute.case-create":
            return await self._controlled_success(tool_name, params, "transaction", "DISPUTE_CASE_CREATED", "Dispute collaboration case created.", requires_human=True)
        if tool_name in {"points.repair-request", "fee.adjustment-request", "notification.send-draft", "ticket.assign", "ticket.close-request"}:
            return await self._controlled_success(tool_name, params, category, "REQUEST_PREPARED", "Controlled request prepared; no authoritative status was changed.", requires_human=requires_confirmation)
        if tool_name in {"merchant.info-query", "statement.bill-query", "ticket.history-search", "knowledge.policy-search"}:
            return self._query_result(tool_name, category, "QUERY_READY", "Mock query completed.", {"query": params}, found=True)
        return self._base_response(tool_name, category, True, "MOCK_SUCCESS", "Mock tool executed.")

    async def _customer_result(self, tool_name: str, params: dict, category: str) -> dict:
        customer = await mock_business_repository.find_customer(params)
        return self._query_result(tool_name, category, "CUSTOMER_FOUND", "Customer profile found.", {"customer": customer}, found=bool(customer))

    async def _coupon_reissue(self, params: dict) -> dict:
        customer_id = params.get("customerId", "")
        coupon_type = params.get("couponType", "")
        history = await mock_business_repository.get_history(customer_id=customer_id, tool_name="coupon.reissue")
        for item in history:
            try:
                response = item.get("response_json") or "{}"
                if coupon_type and coupon_type in response:
                    return self._base_response(
                        "coupon.reissue",
                        "coupon",
                        True,
                        "IDEMPOTENT_REPLAY",
                        "Coupon was already reissued; returning existing business evidence.",
                        operation_id=item.get("operation_id", ""),
                        evidence_id=item.get("evidence_id", ""),
                        audit_payload={"idempotent": True, "couponType": coupon_type},
                    )
            except TypeError:
                continue
        return await self._controlled_success(
            "coupon.reissue",
            params,
            "coupon",
            "COUPON_REISSUED",
            "Coupon reissue accepted and evidence generated.",
            requires_human=False,
            audit_payload={"couponType": coupon_type},
        )

    async def _controlled_success(
        self,
        tool_name: str,
        params: dict,
        category: str,
        business_code: str,
        message: str,
        *,
        requires_human: bool,
        audit_payload: dict | None = None,
    ) -> dict:
        response = self._base_response(
            tool_name,
            category,
            True,
            business_code,
            message,
            requires_human=requires_human,
            audit_payload=audit_payload or {},
        )
        await mock_business_repository.record_history(
            ticket_id=params.get("ticketId", ""),
            customer_id=params.get("customerId", ""),
            tool_name=tool_name,
            operation_id=response["operationId"],
            evidence_id=response["evidenceId"],
            request=params,
            response=response,
        )
        return response

    def _query_result(
        self,
        tool_name: str,
        category: str,
        business_code: str,
        message: str,
        data: dict,
        *,
        found: bool,
        requires_human: bool = False,
    ) -> dict:
        if not found:
            return self._base_response(tool_name, category, False, "NOT_FOUND", "No matching mock business record was found.", requires_human=True)
        return self._base_response(tool_name, category, True, business_code, message, requires_human=requires_human, audit_payload=data)

    def _base_response(
        self,
        tool_name: str,
        category: str,
        success: bool,
        business_code: str,
        message: str,
        *,
        requires_human: bool = False,
        operation_id: str = "",
        evidence_id: str = "",
        audit_payload: dict | None = None,
    ) -> dict:
        evidence_id = evidence_id or self._generate_evidence_id(category)
        operation_id = operation_id or f"OP{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}"
        return {
            "success": success,
            "businessStatus": "success" if success else "failed",
            "businessCode": business_code,
            "businessMessage": message,
            "operationId": operation_id,
            "evidenceId": evidence_id if success else "",
            "requiresHuman": requires_human,
            "failureReason": "" if success else message,
            "nextStep": _next_step(tool_name, success, requires_human),
            "auditPayload": audit_payload or {},
        }

    def _result(
        self,
        tool_name: str,
        success: bool,
        code: str,
        message: str,
        *,
        requires_human: bool,
        duration_ms: int,
    ) -> ToolResult:
        response = self._base_response(tool_name, "tool", success, code, message, requires_human=requires_human)
        response["durationMs"] = duration_ms
        return self._to_tool_result(tool_name, response)

    def _to_tool_result(self, tool_name: str, response: dict) -> ToolResult:
        success = bool(response.get("success"))
        return ToolResult(
            success=success,
            tool_name=tool_name,
            evidence_id=response.get("evidenceId", ""),
            action=tool_name,
            business_result=response.get("businessMessage", ""),
            next_step=response.get("nextStep", ""),
            requires_human=bool(response.get("requiresHuman")),
            failure_reason=response.get("failureReason", ""),
            data=response,
            message=response.get("businessMessage", ""),
            duration_ms=int(response.get("durationMs", 0) or 0),
        )

    def _generate_evidence_id(self, category: str) -> str:
        prefix = _PREFIX_MAP.get(category, "EV")
        return f"{prefix}{datetime.now().strftime('%Y%m%d')}{uuid.uuid4().hex[:8].upper()}"


def _extract_business_code(content: str) -> str | None:
    match = re.search(
        r"(?<![A-Z0-9])([A-Z][A-Z0-9]+(?:_[A-Z0-9]+)+)(?![A-Z0-9])",
        content or "",
    )
    if not match:
        return None
    code = match.group(1)
    return code if not code.startswith(("APP", "TXN")) else None


def _is_missing(value: Any) -> bool:
    if value in _MISSING_VALUES:
        return True
    text = str(value).strip()
    return (
        not text
        or text.lower() in {"none", "null"}
        or text in {"未提供", "未提取", "未填写", "未知"}
        or text.startswith("鏈")
    )


def _verify_passed(value: Any) -> bool:
    text = str(value or "").strip().upper()
    return "PASSED" in text or "通过" in str(value or "")


def _next_step(tool_name: str, success: bool, requires_human: bool) -> str:
    if not success:
        return "Route to manual review or request more information."
    if requires_human:
        return "Prepare manual review; do not close or submit automatically."
    if tool_name == "coupon.reissue":
        return "Notify customer to check the coupon center after operator review."
    return "Use the business result to prepare reply draft and review evidence."


mock_executor = MockExecutor(tool_registry)
