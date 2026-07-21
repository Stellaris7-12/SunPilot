"""Shared MySQL-only helpers for module K smoke tests."""

import json
import os
from pathlib import Path

from sqlalchemy.engine import URL, make_url


TEST_DATABASE_NAME = os.getenv("MYSQL_TEST_DATABASE", "ticket_agent_test")

RESET_TABLES = (
    "ticket_operation_log",
    "tool_call_log",
    "trace_steps",
    "ai_results",
    "tickets",
    "mock_tool_history",
    "mock_permissions",
    "mock_coupons",
    "mock_applications",
    "mock_benefits",
    "mock_transactions",
    "mock_cards",
    "mock_customers",
)


def configure_mysql_test_database() -> str:
    database_url = _build_test_database_url()
    os.environ["DB_BACKEND"] = "mysql"
    os.environ["DATABASE_URL"] = database_url
    return database_url


async def reset_mysql_test_data(database_module):
    await database_module.init_db()
    with open(database_module.TICKETS_JSON, "r", encoding="utf-8") as f:
        tickets = json.load(f)

    async with database_module.get_db() as db:
        for table in RESET_TABLES:
            await db.execute(f"DELETE FROM {table}")
        for ticket in tickets:
            await database_module.insert_ticket_row(db, ticket)
        await database_module._seed_mock_domain_data(db)
        await db.commit()
    await dispose_database_engine(database_module)


async def dispose_database_engine(database_module):
    engine = getattr(database_module, "_async_engine", None)
    if engine is not None:
        await engine.dispose()
        database_module._async_engine = None


def _build_test_database_url() -> str:
    raw_url = os.path.expandvars(os.getenv("DATABASE_URL", ""))
    if raw_url and "sqlite" not in raw_url.lower() and "${" not in raw_url and "$MYSQL_ROOT_PASSWORD" not in raw_url:
        url = make_url(raw_url).set(database=TEST_DATABASE_NAME)
        return url.render_as_string(hide_password=False)

    password = os.getenv("MYSQL_ROOT_PASSWORD")
    if not password:
        raise RuntimeError("MYSQL_ROOT_PASSWORD is required for MySQL smoke tests.")
    return URL.create(
        "mysql+asyncmy",
        username="root",
        password=password,
        host="127.0.0.1",
        port=3306,
        database=TEST_DATABASE_NAME,
        query={"charset": "utf8mb4"},
    ).render_as_string(hide_password=False)
