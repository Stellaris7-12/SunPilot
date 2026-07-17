"""SQLite database initialization and connection management."""

import json
import aiosqlite
from pathlib import Path
from config import DATABASE_PATH, TICKETS_JSON


async def init_db():
    """Create tables and seed initial data if the database is empty."""
    db_path = Path(DATABASE_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(str(db_path)) as db:
        # Enable WAL mode for better concurrent read performance
        await db.execute("PRAGMA journal_mode=WAL")

        # Create tables
        await db.executescript("""
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
                    CHECK(status IN ('open','in_progress','pending_human_confirm','pending_human_review','escalated','closed')),
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

        # Seed tickets if table is empty
        cursor = await db.execute("SELECT COUNT(*) FROM tickets")
        count = (await cursor.fetchone())[0]

        if count == 0:
            with open(TICKETS_JSON, "r", encoding="utf-8") as f:
                tickets = json.load(f)

            for t in tickets:
                await db.execute(
                    """INSERT INTO tickets (id, no, title, customer_name, phone, card_last4,
                       scene, created_at, risk_label, risk_level, status, content)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (t["id"], t["no"], t["title"], t["customer_name"], t["phone"],
                     t["card_last4"], t["scene"], t["created_at"], t["risk_label"],
                     t["risk_level"], t["status"], t["content"])
                )

        await db.commit()


from contextlib import asynccontextmanager
from typing import AsyncGenerator


@asynccontextmanager
async def get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    """Get an async SQLite connection context manager.

    Usage:
        async with get_db() as db:
            cursor = await db.execute("SELECT * FROM tickets")
            rows = await cursor.fetchall()
    """
    db = await aiosqlite.connect(DATABASE_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    try:
        yield db
    finally:
        await db.close()
