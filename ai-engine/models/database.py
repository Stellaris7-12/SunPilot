"""SQLite database initialization and compatible migrations."""

import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import aiosqlite

from config import DATABASE_PATH, TICKETS_JSON


TICKET_STATUS_VALUES = (
    "'open','in_progress','pending_info','pending_human_confirm',"
    "'pending_human_review','escalated','failed','closed'"
)
LEGACY_TICKET_STATUS_VALUES = (
    "'open','in_progress','pending_human_confirm',"
    "'pending_human_review','escalated','closed'"
)


async def init_db():
    """Create tables, run non-destructive migrations, and seed demo tickets."""
    db_path = Path(DATABASE_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(str(db_path)) as db:
        await db.execute("PRAGMA journal_mode=WAL")

        await db.executescript(f"""
            CREATE TABLE IF NOT EXISTS tickets (
                id TEXT PRIMARY KEY,
                no TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                customer_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                card_last4 TEXT NOT NULL,
                scene TEXT NOT NULL,
                created_at TEXT NOT NULL,
                risk_label TEXT NOT NULL,
                risk_level TEXT NOT NULL CHECK(risk_level IN ('low','medium','high')),
                status TEXT NOT NULL DEFAULT 'open'
                    CHECK(status IN ({TICKET_STATUS_VALUES})),
                content TEXT NOT NULL
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
        """)

        await _migrate_ticket_status_check(db)
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
            "requires_human_review": "INTEGER NOT NULL DEFAULT 1",
            "duration_ms": "INTEGER NOT NULL DEFAULT 0",
            "failure_reason": "TEXT",
        })
        await _add_missing_columns(db, "tool_call_log", {
            "failure_reason": "TEXT",
        })

        await _seed_tickets(db)
        await db.commit()


async def _migrate_ticket_status_check(db: aiosqlite.Connection):
    """Expand the ticket status CHECK constraint while preserving rows."""
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
            customer_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            card_last4 TEXT NOT NULL,
            scene TEXT NOT NULL,
            created_at TEXT NOT NULL,
            risk_label TEXT NOT NULL,
            risk_level TEXT NOT NULL CHECK(risk_level IN ('low','medium','high')),
            status TEXT NOT NULL DEFAULT 'open'
                CHECK(status IN ({TICKET_STATUS_VALUES})),
            content TEXT NOT NULL
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


async def _seed_tickets(db: aiosqlite.Connection):
    cursor = await db.execute("SELECT COUNT(*) FROM tickets")
    count = (await cursor.fetchone())[0]
    if count != 0:
        return

    with open(TICKETS_JSON, "r", encoding="utf-8") as f:
        tickets = json.load(f)

    for t in tickets:
        await db.execute(
            """INSERT INTO tickets (id, no, title, customer_name, phone, card_last4,
               scene, created_at, risk_label, risk_level, status, content)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                t["id"], t["no"], t["title"], t["customer_name"], t["phone"],
                t["card_last4"], t["scene"], t["created_at"], t["risk_label"],
                t["risk_level"], t["status"], t["content"],
            ),
        )


@asynccontextmanager
async def get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    db = await aiosqlite.connect(DATABASE_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    try:
        yield db
    finally:
        await db.close()
