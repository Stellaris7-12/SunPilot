"""Repository layer for ticket, AI result, trace, and audit persistence."""

import json
from datetime import datetime
from typing import Any

from .database import get_db, nullable_datetime, row_to_dict


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class TicketRepository:
    async def list_tickets(self, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        filters = filters or {}
        where: list[str] = []
        params: list[Any] = []
        _add_like_filter(where, params, "no", filters.get("ticket_no"))
        _add_like_filter(where, params, "customer_id", filters.get("customer_id"))
        _add_like_filter(where, params, "customer_name", filters.get("customer_name"))
        _add_equal_filter(where, params, "status", filters.get("status"))
        _add_equal_filter(where, params, "category", filters.get("category"))
        _add_equal_filter(where, params, "priority", filters.get("priority") or filters.get("risk"))
        _add_equal_filter(where, params, "risk_level", filters.get("risk_level"))
        _add_equal_filter(where, params, "assignee", filters.get("assignee"))
        _add_equal_filter(where, params, "channel", filters.get("channel"))
        if filters.get("created_from"):
            where.append("created_at >= ?")
            params.append(filters["created_from"])
        if filters.get("created_to"):
            where.append("created_at <= ?")
            params.append(filters["created_to"])
        if filters.get("sla_overdue") is True:
            where.append("due_at <> '' AND due_at < ? AND status NOT IN ('closed', 'cancelled')")
            params.append(_now())
        sql = "SELECT * FROM tickets"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY created_at DESC"
        async with get_db() as db:
            cursor = await db.execute(sql, tuple(params))
            return [row_to_dict(row) for row in await cursor.fetchall()]

    async def get_ticket(self, ticket_id: str) -> dict[str, Any] | None:
        async with get_db() as db:
            cursor = await db.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
            return row_to_dict(await cursor.fetchone())

    async def create_ticket(self, ticket: dict[str, Any]) -> dict[str, Any]:
        created_at = ticket.get("created_at") or _now()
        updated_at = ticket.get("updated_at") or created_at
        async with get_db() as db:
            await db.execute(
                """INSERT INTO tickets
                   (id, no, title, customer_id, customer_name, phone, card_last4,
                    scene, category, subcategory, priority, channel, assignee,
                    department, created_at, due_at, updated_at, risk_label,
                    risk_level, status, content)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    ticket["id"],
                    ticket["no"],
                    ticket["title"],
                    ticket.get("customer_id", ""),
                    ticket["customer_name"],
                    ticket["phone"],
                    ticket["card_last4"],
                    ticket["scene"],
                    ticket.get("category", ""),
                    ticket.get("subcategory", ""),
                    ticket.get("priority", "normal"),
                    ticket.get("channel", ""),
                    ticket.get("assignee", ""),
                    ticket.get("department", ""),
                    created_at,
                    nullable_datetime(ticket.get("due_at", "")),
                    updated_at,
                    ticket.get("risk_label", "低风险"),
                    ticket.get("risk_level", "low"),
                    ticket.get("status", "open"),
                    ticket["content"],
                ),
            )
            await db.execute(
                """INSERT INTO ticket_operation_log
                   (ticket_id, operation, operator, from_status, to_status, detail_json)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    ticket["id"],
                    "create_ticket",
                    ticket.get("operator", "operator"),
                    "",
                    ticket.get("status", "open"),
                    json.dumps({"no": ticket["no"], "title": ticket["title"]}, ensure_ascii=False),
                ),
            )
            await db.commit()
        row = await self.get_ticket(ticket["id"])
        if row is None:
            raise RuntimeError(f"Ticket {ticket['id']} was not created")
        return row

    async def update_ticket(self, ticket_id: str, changes: dict[str, Any], *, operator: str = "operator") -> dict[str, Any]:
        row = await self.get_ticket(ticket_id)
        if row is None:
            raise ValueError("Ticket not found")
        if row["status"] in {"closed", "cancelled"}:
            raise ValueError(f"Cannot edit ticket in status '{row['status']}'")
        allowed = {
            "title",
            "customer_id",
            "customer_name",
            "phone",
            "card_last4",
            "scene",
            "category",
            "subcategory",
            "priority",
            "channel",
            "assignee",
            "department",
            "due_at",
            "risk_label",
            "risk_level",
            "content",
        }
        update = {key: value for key, value in changes.items() if key in allowed and value is not None}
        if not update:
            return row
        update["updated_at"] = _now()
        assignments = ", ".join(f"{key} = ?" for key in update)
        params = [nullable_datetime(value) if key == "due_at" else value for key, value in update.items()]
        params.append(ticket_id)
        async with get_db() as db:
            await db.execute(f"UPDATE tickets SET {assignments} WHERE id = ?", tuple(params))
            await db.execute(
                """INSERT INTO ticket_operation_log
                   (ticket_id, operation, operator, from_status, to_status, detail_json)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    ticket_id,
                    "edit_ticket",
                    operator,
                    row["status"],
                    row["status"],
                    json.dumps({"changedFields": sorted(update.keys())}, ensure_ascii=False),
                ),
            )
            await db.commit()
        updated = await self.get_ticket(ticket_id)
        if updated is None:
            raise RuntimeError("Ticket disappeared after update")
        return updated

    async def assign_ticket(
        self,
        ticket_id: str,
        assignee: str,
        department: str | None = None,
        *,
        operator: str = "operator",
    ) -> dict[str, Any]:
        row = await self.get_ticket(ticket_id)
        if row is None:
            raise ValueError("Ticket not found")
        if row["status"] in {"closed", "cancelled"}:
            raise ValueError(f"Cannot assign ticket in status '{row['status']}'")
        updated_at = _now()
        async with get_db() as db:
            if department is None:
                await db.execute(
                    "UPDATE tickets SET assignee = ?, updated_at = ? WHERE id = ?",
                    (assignee, updated_at, ticket_id),
                )
            else:
                await db.execute(
                    "UPDATE tickets SET assignee = ?, department = ?, updated_at = ? WHERE id = ?",
                    (assignee, department, updated_at, ticket_id),
                )
            await db.execute(
                """INSERT INTO ticket_operation_log
                   (ticket_id, operation, operator, from_status, to_status, detail_json)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    ticket_id,
                    "assign_ticket",
                    operator,
                    row["status"],
                    row["status"],
                    json.dumps({"assignee": assignee, "department": department}, ensure_ascii=False),
                ),
            )
            await db.commit()
        updated = await self.get_ticket(ticket_id)
        if updated is None:
            raise RuntimeError("Ticket disappeared after assign")
        return updated

    async def cancel_ticket(self, ticket_id: str, reason: str, *, operator: str = "operator") -> dict[str, Any]:
        row = await self.get_ticket(ticket_id)
        if row is None:
            raise ValueError("Ticket not found")
        _ensure_transition(ticket_id, row["status"], "cancelled")
        now = _now()
        async with get_db() as db:
            await db.execute(
                """UPDATE tickets
                   SET status = ?, cancel_reason = ?, updated_at = ?
                   WHERE id = ?""",
                ("cancelled", reason, now, ticket_id),
            )
            await db.execute(
                """INSERT INTO ticket_operation_log
                   (ticket_id, operation, operator, from_status, to_status, detail_json)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    ticket_id,
                    "cancel_ticket",
                    operator,
                    row["status"],
                    "cancelled",
                    json.dumps({"reason": reason}, ensure_ascii=False),
                ),
            )
            await db.commit()
        updated = await self.get_ticket(ticket_id)
        if updated is None:
            raise RuntimeError("Ticket disappeared after cancel")
        return updated

    async def reopen_ticket(self, ticket_id: str, reason: str = "", *, operator: str = "operator") -> dict[str, Any]:
        row = await self.get_ticket(ticket_id)
        if row is None:
            raise ValueError("Ticket not found")
        _ensure_transition(ticket_id, row["status"], "open")
        now = _now()
        async with get_db() as db:
            await db.execute(
                """UPDATE tickets
                   SET status = ?, closed_at = ?, cancel_reason = '', updated_at = ?
                   WHERE id = ?""",
                ("open", nullable_datetime(""), now, ticket_id),
            )
            await db.execute(
                """INSERT INTO ticket_operation_log
                   (ticket_id, operation, operator, from_status, to_status, detail_json)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    ticket_id,
                    "reopen_ticket",
                    operator,
                    row["status"],
                    "open",
                    json.dumps({"reason": reason}, ensure_ascii=False),
                ),
            )
            await db.commit()
        updated = await self.get_ticket(ticket_id)
        if updated is None:
            raise RuntimeError("Ticket disappeared after reopen")
        return updated

    async def save_reply_draft(self, ticket_id: str, draft: str, *, operator: str = "operator"):
        row = await self.get_ticket(ticket_id)
        if row is None:
            raise ValueError("Ticket not found")
        if row["status"] in {"closed", "cancelled"}:
            raise ValueError(f"Cannot save draft in status '{row['status']}'")
        async with get_db() as db:
            await db.execute(
                """INSERT INTO ticket_operation_log
                   (ticket_id, operation, operator, from_status, to_status, detail_json)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    ticket_id,
                    "save_reply_draft",
                    operator,
                    row["status"],
                    row["status"],
                    json.dumps({"draft": draft}, ensure_ascii=False),
                ),
            )
            await db.commit()

    async def list_operation_logs(self, ticket_id: str) -> list[dict[str, Any]]:
        async with get_db() as db:
            cursor = await db.execute(
                """SELECT * FROM ticket_operation_log
                   WHERE ticket_id = ?
                   ORDER BY created_at DESC, id DESC""",
                (ticket_id,),
            )
            return [row_to_dict(row) for row in await cursor.fetchall()]

    async def update_status(
        self,
        ticket_id: str,
        status: str,
        *,
        operator: str = "system",
        operation: str = "status_change",
        detail: dict[str, Any] | None = None,
    ):
        row = await self.get_ticket(ticket_id)
        from_status = row["status"] if row else ""
        if row:
            _ensure_transition(ticket_id, from_status, status)
        async with get_db() as db:
            await db.execute(
                "UPDATE tickets SET status = ?, updated_at = ? WHERE id = ?",
                (status, _now(), ticket_id),
            )
            await db.execute(
                """INSERT INTO ticket_operation_log
                   (ticket_id, operation, operator, from_status, to_status, detail_json)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    ticket_id,
                    operation,
                    operator,
                    from_status,
                    status,
                    json.dumps(detail or {}, ensure_ascii=False),
                ),
            )
            await db.commit()

    async def close_ticket(self, ticket_id: str, final_reply: str):
        row = await self.get_ticket(ticket_id)
        if row is None:
            raise ValueError("Ticket not found")
        _ensure_transition(ticket_id, row["status"], "closed")
        closed_at = _now()
        async with get_db() as db:
            await db.execute(
                """UPDATE tickets
                   SET status = ?, final_reply = ?, closed_at = ?, updated_at = ?
                   WHERE id = ?""",
                ("closed", final_reply, closed_at, closed_at, ticket_id),
            )
            await db.execute(
                """UPDATE ai_results
                   SET final_reply = ?, closed_at = ?
                   WHERE id = ?""",
                (final_reply, closed_at, await self._latest_ai_result_id(db, ticket_id)),
            )
            await db.execute(
                """INSERT INTO ticket_operation_log
                   (ticket_id, operation, operator, from_status, to_status, detail_json)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    ticket_id,
                    "close_ticket",
                    "operator",
                    row["status"],
                    "closed",
                    json.dumps({"finalReply": final_reply}, ensure_ascii=False),
                ),
            )
            await db.commit()

    async def _latest_ai_result_id(self, db, ticket_id: str):
        cursor = await db.execute(
            """SELECT id FROM ai_results
               WHERE ticket_id = ?
               ORDER BY created_at DESC, id DESC
               LIMIT 1""",
            (ticket_id,),
        )
        row = await cursor.fetchone()
        return row["id"] if row else None


class AiResultRepository:
    async def insert_ai_result(self, ticket_id: str, trace, result: dict[str, Any], public_result: dict[str, Any]):
        result_copy = {k: v for k, v in result.items() if not k.startswith("_")}
        intent = result_copy.get("intent") or {}
        async with get_db() as db:
            await db.execute(
                """INSERT INTO ai_results
                   (ticket_id, run_id, status, result_json, workflow_name,
                    intent_type, intent_label, intent_confidence, extracted_fields_json,
                    tool_name, tool_request_json, tool_response_json, evidence_id,
                    reply_draft, notification_json, requires_human_review, duration_ms,
                    failure_reason)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    ticket_id,
                    trace.run_id,
                    result.get("_status", ""),
                    json.dumps(public_result, ensure_ascii=False),
                    result_copy.get("workflow_name", ""),
                    intent.get("type", ""),
                    intent.get("label", ""),
                    intent.get("confidence", 0.0),
                    json.dumps(result_copy.get("fields", []), ensure_ascii=False),
                    result_copy.get("tool_name", ""),
                    json.dumps(result_copy.get("tool_request", {}), ensure_ascii=False),
                    json.dumps(result_copy.get("tool_response", {}), ensure_ascii=False),
                    (result_copy.get("tool_response", {}) or {}).get("evidenceId", ""),
                    result_copy.get("reply_draft", ""),
                    json.dumps(public_result.get("notification"), ensure_ascii=False),
                    1 if result_copy.get("requires_human_review", True) else 0,
                    result.get("_total_duration_ms", 0),
                    result.get("_failure_reason", "") or result_copy.get("failure_reason", ""),
                ),
            )
            await db.commit()

    async def get_latest_result_json(self, ticket_id: str) -> str | None:
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT result_json FROM ai_results WHERE ticket_id = ? ORDER BY created_at DESC LIMIT 1",
                (ticket_id,),
            )
            row = await cursor.fetchone()
            return row["result_json"] if row else None


class TraceRepository:
    async def insert_trace_steps(self, ticket_id: str, run_id: str, steps: list[Any]):
        async with get_db() as db:
            for i, step in enumerate(steps):
                await db.execute(
                    """INSERT INTO trace_steps
                       (ticket_id, run_id, agent, agent_id, summary, duration, status, step_order)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        ticket_id,
                        run_id,
                        step.agent,
                        step.agent_id,
                        step.summary,
                        step.duration,
                        step.status.value,
                        i + 1,
                    ),
                )
            await db.commit()

    async def list_recent_trace(self, ticket_id: str, limit: int = 10) -> list[dict[str, Any]]:
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT * FROM trace_steps WHERE ticket_id = ? ORDER BY created_at DESC LIMIT ?",
                (ticket_id, limit),
            )
            return [row_to_dict(row) for row in await cursor.fetchall()]


class ToolCallRepository:
    async def insert_tool_call(self, ticket_id: str, tool_name: str, request: dict[str, Any], tool_result):
        async with get_db() as db:
            await db.execute(
                """INSERT INTO tool_call_log
                   (ticket_id, tool_name, request_json, response_json, evidence_id,
                    success, duration_ms, failure_reason)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    ticket_id,
                    tool_name,
                    json.dumps(request, ensure_ascii=False),
                    json.dumps(tool_result.model_dump(by_alias=True), ensure_ascii=False),
                    tool_result.evidence_id,
                    1 if tool_result.success else 0,
                    tool_result.duration_ms,
                    "" if tool_result.success else (tool_result.failure_reason or tool_result.message),
                ),
            )
            await db.commit()

    async def list_tool_calls(self, ticket_id: str) -> list[dict[str, Any]]:
        async with get_db() as db:
            cursor = await db.execute(
                """SELECT * FROM tool_call_log
                   WHERE ticket_id = ?
                   ORDER BY created_at DESC, id DESC""",
                (ticket_id,),
            )
            return [row_to_dict(row) for row in await cursor.fetchall()]


class MockBusinessRepository:
    async def find_customer(self, params: dict[str, Any]) -> dict[str, Any] | None:
        customer_id = params.get("customerId") or params.get("customer_id")
        phone = params.get("phone")
        name = params.get("customerName") or params.get("customer_name")
        card_last4 = params.get("cardLast4") or params.get("card_last4")
        where: list[str] = []
        values: list[Any] = []
        if customer_id:
            where.append("c.customer_id = ?")
            values.append(customer_id)
        if phone:
            where.append("c.phone = ?")
            values.append(phone)
        if name:
            where.append("c.customer_name = ?")
            values.append(name)
        if card_last4:
            where.append("card.card_last4 = ?")
            values.append(card_last4)
        if not where:
            return None
        async with get_db() as db:
            cursor = await db.execute(
                f"""SELECT c.*, card.card_last4, card.card_status, card.product_name
                    FROM mock_customers c
                    LEFT JOIN mock_cards card ON card.customer_id = c.customer_id
                    WHERE {' AND '.join(where)}
                    LIMIT 1""",
                tuple(values),
            )
            return row_to_dict(await cursor.fetchone())

    async def get_card(self, customer_id: str, card_last4: str = "") -> dict[str, Any] | None:
        sql = "SELECT * FROM mock_cards WHERE customer_id = ?"
        params: list[Any] = [customer_id]
        if card_last4:
            sql += " AND card_last4 = ?"
            params.append(card_last4)
        sql += " LIMIT 1"
        async with get_db() as db:
            cursor = await db.execute(sql, tuple(params))
            return row_to_dict(await cursor.fetchone())

    async def get_benefit(self, customer_id: str, benefit_code: str = "") -> dict[str, Any] | None:
        sql = "SELECT * FROM mock_benefits WHERE customer_id = ?"
        params: list[Any] = [customer_id]
        if benefit_code:
            sql += " AND benefit_code = ?"
            params.append(benefit_code)
        sql += " ORDER BY expire_at DESC LIMIT 1"
        async with get_db() as db:
            cursor = await db.execute(sql, tuple(params))
            return row_to_dict(await cursor.fetchone())

    async def get_application(self, customer_id: str, application_no: str = "") -> dict[str, Any] | None:
        sql = "SELECT * FROM mock_applications WHERE customer_id = ?"
        params: list[Any] = [customer_id]
        if application_no:
            sql += " AND application_no = ?"
            params.append(application_no)
        sql += " ORDER BY expected_finish_at DESC LIMIT 1"
        async with get_db() as db:
            cursor = await db.execute(sql, tuple(params))
            return row_to_dict(await cursor.fetchone())

    async def get_transaction(self, params: dict[str, Any]) -> dict[str, Any] | None:
        where = ["customer_id = ?"]
        values: list[Any] = [params.get("customerId") or params.get("customer_id")]
        if not values[0]:
            return None
        if params.get("transactionId"):
            where.append("transaction_id = ?")
            values.append(params["transactionId"])
        if params.get("cardLast4"):
            where.append("card_last4 = ?")
            values.append(params["cardLast4"])
        amount = _optional_float(params.get("amount"))
        if amount is not None:
            where.append("ABS(amount - ?) < 0.01")
            values.append(amount)
        merchant_name = params.get("merchantName") or params.get("merchant")
        if merchant_name:
            where.append("LOWER(merchant) LIKE ?")
            values.append(f"%{str(merchant_name).lower()}%")
        async with get_db() as db:
            cursor = await db.execute(
                f"SELECT * FROM mock_transactions WHERE {' AND '.join(where)} LIMIT 1",
                tuple(values),
            )
            return row_to_dict(await cursor.fetchone())

    async def get_history(self, ticket_id: str = "", customer_id: str = "", tool_name: str = "") -> list[dict[str, Any]]:
        where: list[str] = []
        params: list[Any] = []
        _add_equal_filter(where, params, "ticket_id", ticket_id)
        _add_equal_filter(where, params, "customer_id", customer_id)
        _add_equal_filter(where, params, "tool_name", tool_name)
        sql = "SELECT * FROM mock_tool_history"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY created_at DESC, id DESC"
        async with get_db() as db:
            cursor = await db.execute(sql, tuple(params))
            return [row_to_dict(row) for row in await cursor.fetchall()]

    async def record_history(
        self,
        *,
        ticket_id: str = "",
        customer_id: str = "",
        tool_name: str,
        operation_id: str,
        evidence_id: str,
        request: dict[str, Any],
        response: dict[str, Any],
    ):
        async with get_db() as db:
            await db.execute(
                """INSERT INTO mock_tool_history
                   (ticket_id, customer_id, tool_name, operation_id, evidence_id, request_json, response_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    ticket_id,
                    customer_id,
                    tool_name,
                    operation_id,
                    evidence_id,
                    json.dumps(request, ensure_ascii=False),
                    json.dumps(response, ensure_ascii=False),
                ),
            )
            await db.commit()

def _add_like_filter(where: list[str], params: list[Any], column: str, value: Any):
    if value not in {None, ""}:
        where.append(f"LOWER({column}) LIKE ?")
        params.append(f"%{str(value).lower()}%")


def _optional_float(value: Any) -> float | None:
    if value in {None, "", "未提供", "未提取", "N/A", "UNKNOWN"}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _add_equal_filter(where: list[str], params: list[Any], column: str, value: Any):
    if value not in {None, ""}:
        where.append(f"{column} = ?")
        params.append(value)


def _ensure_transition(ticket_id: str, from_status: str, to_status: str):
    from orchestrator.state_machine import TicketStateMachine

    TicketStateMachine.transition(ticket_id, from_status, to_status)


ticket_repository = TicketRepository()
ai_result_repository = AiResultRepository()
trace_repository = TraceRepository()
tool_call_repository = ToolCallRepository()
mock_business_repository = MockBusinessRepository()
