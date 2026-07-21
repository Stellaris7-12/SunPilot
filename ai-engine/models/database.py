"""Database initialization, compatible migrations, and low-level helpers."""

import json
from contextlib import asynccontextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any, AsyncGenerator

import aiosqlite
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from config import DATABASE_PATH, DATABASE_URL, DB_BACKEND, DB_POOL_SIZE, DB_TIMEOUT_SECONDS, TICKETS_JSON


TICKET_STATUS_VALUES = (
    "'open','in_progress','pending_info','pending_human_confirm',"
    "'pending_human_review','escalated','failed','closed'"
)

TICKET_PRIORITY_VALUES = "'low','normal','urgent','critical'"

_async_engine: AsyncEngine | None = None


async def init_db():
    """Create tables, run non-destructive migrations, and seed demo tickets."""
    if DB_BACKEND in {"mysql", "tdsql"}:
        await _init_mysql_db()
        return
    if DB_BACKEND not in {"sqlite", "fallback"}:
        raise RuntimeError(f"Unsupported DB_BACKEND={DB_BACKEND!r}")

    db_path = Path(DATABASE_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(str(db_path)) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")

        await db.executescript(f"""
            CREATE TABLE IF NOT EXISTS tickets (
                id TEXT PRIMARY KEY,
                no TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                customer_id TEXT NOT NULL DEFAULT '',
                customer_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                card_last4 TEXT NOT NULL,
                scene TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT '',
                subcategory TEXT NOT NULL DEFAULT '',
                priority TEXT NOT NULL DEFAULT 'normal'
                    CHECK(priority IN ({TICKET_PRIORITY_VALUES})),
                channel TEXT NOT NULL DEFAULT '',
                assignee TEXT NOT NULL DEFAULT '',
                department TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                due_at TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT '',
                risk_label TEXT NOT NULL,
                risk_level TEXT NOT NULL CHECK(risk_level IN ('low','medium','high')),
                status TEXT NOT NULL DEFAULT 'open'
                    CHECK(status IN ({TICKET_STATUS_VALUES})),
                content TEXT NOT NULL,
                closed_at TEXT NOT NULL DEFAULT '',
                final_reply TEXT NOT NULL DEFAULT '',
                cancel_reason TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS ai_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id TEXT NOT NULL REFERENCES tickets(id),
                result_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS trace_steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id TEXT NOT NULL REFERENCES tickets(id),
                run_id TEXT NOT NULL,
                agent TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                summary TEXT NOT NULL,
                duration TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('RUNNING','SUCCESS','FAILED','SKIPPED')),
                step_order INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS tool_call_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id TEXT NOT NULL REFERENCES tickets(id),
                tool_name TEXT NOT NULL,
                request_json TEXT NOT NULL,
                response_json TEXT NOT NULL,
                evidence_id TEXT,
                success INTEGER NOT NULL DEFAULT 0,
                duration_ms INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sample_id TEXT NOT NULL,
                scenario TEXT NOT NULL,
                intent_correct INTEGER NOT NULL DEFAULT 0,
                field_complete_count INTEGER NOT NULL DEFAULT 0,
                field_total_count INTEGER NOT NULL DEFAULT 0,
                tool_correct INTEGER NOT NULL DEFAULT 0,
                time_saved_ms INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS ticket_operation_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id TEXT NOT NULL REFERENCES tickets(id),
                operation TEXT NOT NULL,
                operator TEXT NOT NULL DEFAULT 'system',
                from_status TEXT NOT NULL DEFAULT '',
                to_status TEXT NOT NULL DEFAULT '',
                detail_json TEXT NOT NULL DEFAULT '{{}}',
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS mock_customers (
                customer_id TEXT PRIMARY KEY,
                customer_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                segment TEXT NOT NULL DEFAULT '',
                risk_level TEXT NOT NULL DEFAULT 'low',
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS mock_cards (
                card_id TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL REFERENCES mock_customers(customer_id),
                card_last4 TEXT NOT NULL,
                product_name TEXT NOT NULL DEFAULT '',
                card_status TEXT NOT NULL DEFAULT 'active',
                credit_limit INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS mock_transactions (
                transaction_id TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL REFERENCES mock_customers(customer_id),
                card_last4 TEXT NOT NULL,
                amount REAL NOT NULL DEFAULT 0,
                merchant TEXT NOT NULL DEFAULT '',
                transaction_time TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS mock_benefits (
                benefit_id TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL REFERENCES mock_customers(customer_id),
                benefit_code TEXT NOT NULL,
                benefit_name TEXT NOT NULL DEFAULT '',
                remaining_count INTEGER NOT NULL DEFAULT 0,
                expire_at TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS mock_applications (
                application_no TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL REFERENCES mock_customers(customer_id),
                product_name TEXT NOT NULL DEFAULT '',
                current_node TEXT NOT NULL DEFAULT '',
                expected_finish_at TEXT NOT NULL DEFAULT ''
            );
        """)

        await _migrate_ticket_status_check(db)
        await _add_missing_columns(db, "tickets", _ticket_columns())
        await _add_missing_columns(db, "ai_results", {
            "run_id": "TEXT",
            "status": "TEXT",
            "workflow_name": "TEXT",
            "intent_type": "TEXT",
            "intent_label": "TEXT",
            "intent_confidence": "REAL",
            "extracted_fields_json": "TEXT",
            "tool_name": "TEXT",
            "tool_request_json": "TEXT",
            "tool_response_json": "TEXT",
            "evidence_id": "TEXT",
            "reply_draft": "TEXT",
            "notification_json": "TEXT",
            "requires_human_review": "INTEGER NOT NULL DEFAULT 1",
            "duration_ms": "INTEGER NOT NULL DEFAULT 0",
            "failure_reason": "TEXT",
            "final_reply": "TEXT",
            "closed_at": "TEXT",
        })
        await _add_missing_columns(db, "tool_call_log", {
            "failure_reason": "TEXT",
        })
        await _create_indexes(db)
        await _seed_tickets(db)
        await db.commit()


def _ticket_columns() -> dict[str, str]:
    return {
        "customer_id": "TEXT NOT NULL DEFAULT ''",
        "category": "TEXT NOT NULL DEFAULT ''",
        "subcategory": "TEXT NOT NULL DEFAULT ''",
        "priority": "TEXT NOT NULL DEFAULT 'normal'",
        "channel": "TEXT NOT NULL DEFAULT ''",
        "assignee": "TEXT NOT NULL DEFAULT ''",
        "department": "TEXT NOT NULL DEFAULT ''",
        "due_at": "TEXT NOT NULL DEFAULT ''",
        "updated_at": "TEXT NOT NULL DEFAULT ''",
        "closed_at": "TEXT NOT NULL DEFAULT ''",
        "final_reply": "TEXT NOT NULL DEFAULT ''",
        "cancel_reason": "TEXT NOT NULL DEFAULT ''",
    }


async def _migrate_ticket_status_check(db: aiosqlite.Connection):
    """Expand legacy ticket status CHECK constraints while preserving rows."""
    cursor = await db.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'tickets'"
    )
    row = await cursor.fetchone()
    table_sql = row[0] if row else ""
    if "pending_info" in table_sql and "failed" in table_sql:
        return
    if not table_sql:
        return

    await db.executescript(f"""
        DROP TABLE IF EXISTS tickets_migrated;

        CREATE TABLE IF NOT EXISTS tickets_migrated (
            id TEXT PRIMARY KEY,
            no TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            customer_id TEXT NOT NULL DEFAULT '',
            customer_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            card_last4 TEXT NOT NULL,
            scene TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT '',
            subcategory TEXT NOT NULL DEFAULT '',
            priority TEXT NOT NULL DEFAULT 'normal',
            channel TEXT NOT NULL DEFAULT '',
            assignee TEXT NOT NULL DEFAULT '',
            department TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            due_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT '',
            risk_label TEXT NOT NULL,
            risk_level TEXT NOT NULL CHECK(risk_level IN ('low','medium','high')),
            status TEXT NOT NULL DEFAULT 'open'
                CHECK(status IN ({TICKET_STATUS_VALUES})),
            content TEXT NOT NULL,
            closed_at TEXT NOT NULL DEFAULT '',
            final_reply TEXT NOT NULL DEFAULT '',
            cancel_reason TEXT NOT NULL DEFAULT ''
        );

        INSERT INTO tickets_migrated
            (id, no, title, customer_name, phone, card_last4, scene,
             created_at, risk_label, risk_level, status, content)
        SELECT
            id, no, title, customer_name, phone, card_last4, scene,
            created_at, risk_label, risk_level, status, content
        FROM tickets;

        DROP TABLE tickets;
        ALTER TABLE tickets_migrated RENAME TO tickets;
    """)


async def _add_missing_columns(
    db: aiosqlite.Connection,
    table_name: str,
    columns: dict[str, str],
):
    cursor = await db.execute(f"PRAGMA table_info({table_name})")
    existing = {row[1] for row in await cursor.fetchall()}
    for column_name, column_def in columns.items():
        if column_name not in existing:
            await db.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}"
            )


async def _create_indexes(db: aiosqlite.Connection):
    await db.executescript("""
        CREATE INDEX IF NOT EXISTS idx_tickets_customer_id ON tickets(customer_id);
        CREATE INDEX IF NOT EXISTS idx_tickets_category ON tickets(category, subcategory);
        CREATE INDEX IF NOT EXISTS idx_tickets_assignee ON tickets(assignee);
        CREATE INDEX IF NOT EXISTS idx_tickets_status_due_at ON tickets(status, due_at);
        CREATE INDEX IF NOT EXISTS idx_ai_results_ticket_created ON ai_results(ticket_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_trace_steps_ticket_created ON trace_steps(ticket_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_tool_call_log_ticket_created ON tool_call_log(ticket_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_ticket_operation_log_ticket_created
            ON ticket_operation_log(ticket_id, created_at);
    """)


async def _seed_tickets(db: aiosqlite.Connection):
    cursor = await db.execute("SELECT COUNT(*) FROM tickets")
    count = (await cursor.fetchone())[0]
    if count != 0:
        return

    with open(TICKETS_JSON, "r", encoding="utf-8") as f:
        tickets = json.load(f)

    for t in tickets:
        await insert_ticket_row(db, t)


async def insert_ticket_row(db: aiosqlite.Connection, ticket: dict[str, Any]):
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
    if DB_BACKEND in {"mysql", "tdsql"} and not value:
        return None
    return value


@asynccontextmanager
async def get_db() -> AsyncGenerator[Any, None]:
    if DB_BACKEND in {"mysql", "tdsql"}:
        async with _get_mysql_connection() as db:
            yield db
        return
    if DB_BACKEND not in {"sqlite", "fallback"}:
        raise RuntimeError(f"Unsupported DB_BACKEND={DB_BACKEND!r}")
    db = await aiosqlite.connect(DATABASE_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    try:
        yield db
    finally:
        await db.close()


async def _init_mysql_db():
    async with _get_mysql_connection() as db:
        ddl_path = Path(__file__).resolve().parents[1] / "migrations" / "mysql" / "001_i1_schema.sql"
        ddl = ddl_path.read_text(encoding="utf-8")
        await db.execute("SET sql_notes = 0")
        for statement in _split_mysql_ddl(ddl):
            if statement.upper().startswith("CREATE DATABASE") or statement.upper().startswith("USE "):
                continue
            await db.execute(statement)
        await db.execute("SET sql_notes = 1")
        await db.commit()
    async with get_db() as db:
        cursor = await db.execute("SELECT COUNT(*) AS count FROM tickets")
        row = await cursor.fetchone()
        if row and row["count"] == 0:
            with open(TICKETS_JSON, "r", encoding="utf-8") as f:
                for ticket in json.load(f):
                    await insert_ticket_row(db, ticket)
            await db.commit()


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
