"""MySQL/TDSQL initialization, seed data, and low-level helpers."""

import json
import re
from contextlib import asynccontextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any, AsyncGenerator

from sqlalchemy import text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from config import DATABASE_URL, DB_BACKEND, DB_POOL_SIZE, DB_TIMEOUT_SECONDS, TICKETS_JSON, validate_database_config

_async_engine: AsyncEngine | None = None


async def init_db():
    """Create MySQL/TDSQL tables and seed demo tickets."""
    validate_database_config()
    await _ensure_mysql_database()
    await _init_mysql_db()


async def _seed_tickets(db: Any):
    cursor = await db.execute("SELECT COUNT(*) AS count FROM tickets")
    row = await cursor.fetchone()
    count = row["count"] if isinstance(row, dict) else row[0]
    if count != 0:
        return

    with open(TICKETS_JSON, "r", encoding="utf-8") as f:
        tickets = json.load(f)

    for t in tickets:
        await insert_ticket_row(db, t)


async def _seed_mock_domain_data(db: Any):
    await db.execute("SET sql_notes = 0")
    records = await _load_mock_seed_records(db)
    for ticket in records:
        customer_id = ticket.get("customer_id") or ""
        if not customer_id:
            continue
        await db.execute(
            """INSERT INTO mock_customers
               (customer_id, customer_name, phone, segment, risk_level)
               VALUES (?, ?, ?, ?, ?)
               ON DUPLICATE KEY UPDATE customer_id = customer_id""",
            (
                customer_id,
                ticket.get("customer_name", ""),
                ticket.get("phone", ""),
                ticket.get("priority", "normal"),
                ticket.get("risk_level", "low"),
            ),
        )
        await db.execute(
            """INSERT INTO mock_cards
               (card_id, customer_id, card_last4, product_name, card_status, credit_limit)
               VALUES (?, ?, ?, ?, ?, ?)
               ON DUPLICATE KEY UPDATE card_id = card_id""",
            (
                f"CARD-{customer_id}-{ticket.get('card_last4', '')}",
                customer_id,
                ticket.get("card_last4", ""),
                "Credit Card",
                "active",
                50000,
            ),
        )
        benefit_code = _extract_business_code(ticket.get("content", ""))
        if benefit_code:
            await db.execute(
                """INSERT INTO mock_benefits
                   (benefit_id, customer_id, benefit_code, benefit_name, remaining_count, expire_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON DUPLICATE KEY UPDATE benefit_id = benefit_id""",
                (
                    f"BEN-{customer_id}-{benefit_code}",
                    customer_id,
                    benefit_code,
                    benefit_code.replace("_", " "),
                    2,
                    "2026-12-31",
                ),
            )
        await db.execute(
            """INSERT INTO mock_applications
               (application_no, customer_id, product_name, current_node, expected_finish_at)
               VALUES (?, ?, ?, ?, ?)
               ON DUPLICATE KEY UPDATE application_no = application_no""",
            (
                _extract_application_no(ticket.get("content", "")) or f"APP{customer_id[1:]}",
                customer_id,
                "Credit Card Application",
                "under_review",
                "2026-07-23 18:00:00",
            ),
        )
        await db.execute(
            """INSERT INTO mock_transactions
               (transaction_id, customer_id, card_last4, amount, merchant, transaction_time, status)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON DUPLICATE KEY UPDATE transaction_id = transaction_id""",
            (
                _extract_transaction_id(ticket.get("content", "")) or f"TXN{customer_id[1:]}",
                customer_id,
                ticket.get("card_last4", ""),
                _extract_amount(ticket.get("content", "")),
                _extract_merchant(ticket.get("content", "")),
                "2026-07-15 12:00:00",
                "posted",
            ),
        )

    permissions = (
        ("perm-customer-lookup", "customer.lookup", "low", 0),
        ("perm-card-query", "card.account-status-query", "low", 0),
        ("perm-coupon-reissue", "coupon.reissue", "low", 0),
        ("perm-address-update", "customer.update-address", "medium", 1),
        ("perm-dispute-create", "dispute.case-create", "medium", 1),
        ("perm-ticket-close", "ticket.close-request", "high", 1),
    )
    for permission in permissions:
        await db.execute(
            """INSERT INTO mock_permissions
               (permission_id, tool_name, risk_level, requires_human)
               VALUES (?, ?, ?, ?)
               ON DUPLICATE KEY UPDATE permission_id = permission_id""",
            permission,
        )
    await db.execute("SET sql_notes = 1")


async def _load_mock_seed_records(db: Any) -> list[dict[str, Any]]:
    cursor = await db.execute("SELECT * FROM tickets ORDER BY created_at")
    records = [row_to_dict(row) for row in await cursor.fetchall()]
    transcript_path = Path(__file__).resolve().parents[1] / "data" / "call_transcripts.json"
    if not transcript_path.exists():
        return records
    with open(transcript_path, "r", encoding="utf-8") as f:
        for item in json.load(f):
            draft = item.get("ticketDraft") or {}
            if draft:
                records.append(_normalize_ticket_seed_record(draft, item))
    return records


def _normalize_ticket_seed_record(draft: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    call_meta = item.get("callMeta") or {}
    return {
        "customer_id": draft.get("customer_id") or draft.get("customerId") or call_meta.get("customerId") or "",
        "customer_name": draft.get("customer_name") or draft.get("customerName") or call_meta.get("customerName") or "",
        "phone": draft.get("phone") or call_meta.get("phone") or "",
        "card_last4": draft.get("card_last4") or draft.get("cardLast4") or call_meta.get("cardLast4") or "",
        "priority": draft.get("priority", "normal"),
        "risk_level": draft.get("risk_level") or draft.get("riskLevel") or item.get("riskLevel") or "low",
        "content": draft.get("content") or item.get("transcript") or "",
    }


def _extract_business_code(content: str) -> str | None:
    match = re.search(
        r"(?<![A-Z0-9])([A-Z][A-Z0-9]+(?:_[A-Z0-9]+)+)(?![A-Z0-9])",
        content or "",
    )
    if not match:
        return None
    code = match.group(1)
    return code if _is_business_code(code) else None


def _is_business_code(code: str) -> bool:
    return not code.startswith(("APP", "TXN"))


def _extract_application_no(content: str) -> str | None:
    match = re.search(r"(?<![A-Z0-9])APP[0-9A-Z]{6,}(?![A-Z0-9])", content or "")
    return match.group(0) if match else None


def _extract_transaction_id(content: str) -> str | None:
    match = re.search(r"(?<![A-Z0-9])TXN[0-9A-Z]{5,}(?![A-Z0-9])", content or "")
    return match.group(0) if match else None


def _extract_amount(content: str) -> float:
    text = content or ""
    for pattern in (
        r"金额(?:是|为)?\s*([0-9]+(?:\.[0-9]{1,2})?)",
        r"([0-9]+(?:\.[0-9]{1,2})?)\s*元",
    ):
        match = re.search(pattern, text)
        if match:
            return float(match.group(1))
    match = re.search(r"([0-9]+(?:\.[0-9]{1,2})?)", text)
    return float(match.group(1)) if match else 128.0


def _extract_merchant(content: str) -> str:
    text = content or ""
    upper = text.upper()
    if "星河商场" in text:
        return "星河商场"
    for pattern in (r"商户(?:叫|名称为)?([A-Z0-9 ]{3,})", r"([A-Z][A-Z0-9 ]{2,})扣款"):
        match = re.search(pattern, upper)
        if match:
            return match.group(1).strip()
    if "HOTEL" in upper:
        return "SAMPLE HOTEL"
    if "ONLINE" in upper or "GLOBAL SHOP" in upper:
        return "UNKNOWN ONLINE"
    return "SAMPLE MERCHANT"


async def insert_ticket_row(db: Any, ticket: dict[str, Any]):
    now = ticket.get("updated_at") or ticket.get("created_at", "")
    customer_id = ticket.get("customer_id") or ticket.get("customerId") or ""
    await db.execute(
        """INSERT INTO tickets
           (id, no, title, customer_id, customer_name, phone, card_last4, scene,
            category, subcategory, priority, channel, assignee, department,
            created_at, due_at, updated_at, risk_label, risk_level, status,
            content, closed_at, final_reply, cancel_reason)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            ticket["id"],
            ticket["no"],
            ticket["title"],
            customer_id,
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
            ticket["created_at"],
            nullable_datetime(ticket.get("due_at", "")),
            now,
            ticket["risk_label"],
            ticket["risk_level"],
            ticket["status"],
            ticket["content"],
            nullable_datetime(ticket.get("closed_at", "")),
            ticket.get("final_reply", ""),
            ticket.get("cancel_reason", ""),
        ),
    )


def row_to_dict(row: Any | None) -> dict[str, Any] | None:
    if row is None:
        return None
    if isinstance(row, dict):
        return _normalize_row(dict(row))
    return _normalize_row(dict(row))


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized = {}
    for key, value in row.items():
        if isinstance(value, datetime):
            normalized[key] = value.strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(value, date):
            normalized[key] = value.isoformat()
        elif value is None:
            normalized[key] = ""
        else:
            normalized[key] = value
    return normalized


def nullable_datetime(value: Any):
    if not value:
        return None
    return value


@asynccontextmanager
async def get_db() -> AsyncGenerator[Any, None]:
    validate_database_config()
    if DB_BACKEND not in {"mysql", "tdsql"}:
        raise RuntimeError(f"Unsupported DB_BACKEND={DB_BACKEND!r}. Only MySQL/TDSQL is supported.")
    async with _get_mysql_connection() as db:
        yield db


async def _init_mysql_db():
    async with _get_mysql_connection() as db:
        ddl_path = Path(__file__).resolve().parents[1] / "migrations" / "mysql" / "001_i1_schema.sql"
        ddl = ddl_path.read_text(encoding="utf-8")
        await db.execute("SET sql_notes = 0")
        for statement in _split_mysql_ddl(ddl):
            if statement.upper().startswith("CREATE DATABASE") or statement.upper().startswith("USE "):
                continue
            await db.execute(statement)
        await db.execute(
            """ALTER TABLE tickets MODIFY status ENUM(
               'open','in_progress','pending_info','pending_human_confirm',
               'pending_human_review','escalated','failed','cancelled','closed'
            ) NOT NULL DEFAULT 'open'"""
        )
        await db.execute("SET sql_notes = 1")
        await db.commit()
    async with get_db() as db:
        cursor = await db.execute("SELECT COUNT(*) AS count FROM tickets")
        row = await cursor.fetchone()
        if row and row["count"] == 0:
            with open(TICKETS_JSON, "r", encoding="utf-8") as f:
                for ticket in json.load(f):
                    await insert_ticket_row(db, ticket)
        await _seed_mock_domain_data(db)
        await db.commit()


async def _ensure_mysql_database():
    url = make_url(DATABASE_URL)
    database_name = url.database
    if not database_name:
        raise RuntimeError("DATABASE_URL must include a database name.")
    if not re.fullmatch(r"[A-Za-z0-9_]+", database_name):
        raise RuntimeError(f"Unsafe database name in DATABASE_URL: {database_name!r}")

    server_url = URL.create(
        url.drivername,
        username=url.username,
        password=url.password,
        host=url.host,
        port=url.port,
        query=url.query,
    )
    engine = create_async_engine(
        server_url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": DB_TIMEOUT_SECONDS},
    )
    try:
        async with engine.begin() as connection:
            await connection.execute(text("SET sql_notes = 0"))
            await connection.execute(
                text(
                    f"CREATE DATABASE IF NOT EXISTS `{database_name}` "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
            )
            await connection.execute(text("SET sql_notes = 1"))
    finally:
        await engine.dispose()


def _split_mysql_ddl(ddl: str) -> list[str]:
    statements: list[str] = []
    current: list[str] = []
    for raw_line in ddl.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("--"):
            continue
        current.append(raw_line)
        if line.endswith(";"):
            statement = "\n".join(current).strip().rstrip(";").strip()
            if statement:
                statements.append(statement)
            current = []
    if current:
        statement = "\n".join(current).strip().rstrip(";").strip()
        if statement:
            statements.append(statement)
    return statements


def _get_engine() -> AsyncEngine:
    global _async_engine
    if _async_engine is None:
        validate_database_config()
        _async_engine = create_async_engine(
            DATABASE_URL,
            pool_size=DB_POOL_SIZE,
            pool_pre_ping=True,
            connect_args={"connect_timeout": DB_TIMEOUT_SECONDS},
        )
    return _async_engine


@asynccontextmanager
async def _get_mysql_connection() -> AsyncGenerator["_MysqlConnection", None]:
    connection = await _get_engine().connect()
    transaction = await connection.begin()
    wrapper = _MysqlConnection(connection, transaction)
    try:
        yield wrapper
    finally:
        await wrapper.close()


class _MysqlCursor:
    def __init__(self, rows: list[dict[str, Any]]):
        self._rows = rows

    async def fetchone(self):
        return self._rows[0] if self._rows else None

    async def fetchall(self):
        return list(self._rows)


class _MysqlConnection:
    def __init__(self, connection: AsyncConnection, transaction):
        self._connection = connection
        self._transaction = transaction

    async def execute(self, sql: str, parameters: tuple[Any, ...] | list[Any] = ()):
        statement, values = _prepare_mysql_statement(sql, parameters)
        result = await self._connection.execute(text(statement), values)
        if result.returns_rows:
            return _MysqlCursor([dict(row) for row in result.mappings().all()])
        return _MysqlCursor([])

    async def commit(self):
        if self._transaction is not None:
            await self._transaction.commit()
            self._transaction = None

    async def close(self):
        if self._transaction is not None:
            await self._transaction.rollback()
            self._transaction = None
        await self._connection.close()


def _prepare_mysql_statement(sql: str, parameters: tuple[Any, ...] | list[Any]):
    if not parameters:
        return sql, {}
    values: dict[str, Any] = {}
    parts = sql.split("?")
    if len(parts) - 1 != len(parameters):
        raise ValueError("SQL placeholder count does not match parameter count")
    statement_parts: list[str] = []
    for index, part in enumerate(parts[:-1]):
        key = f"p{index}"
        statement_parts.append(part)
        statement_parts.append(f":{key}")
        values[key] = parameters[index]
    statement_parts.append(parts[-1])
    return "".join(statement_parts), values
