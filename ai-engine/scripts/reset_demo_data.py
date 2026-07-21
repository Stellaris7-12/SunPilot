"""Controlled demo data reset for the local TicketAgent sandbox.

This script intentionally resets only the configured local demo database. It
does not touch evaluation samples or any external business system.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path


ENGINE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENGINE_DIR))

from config import DB_BACKEND, TICKETS_JSON  # noqa: E402
from models.database import get_db, init_db, insert_ticket_row  # noqa: E402


RESET_TABLES = (
    "ticket_operation_log",
    "tool_call_log",
    "trace_steps",
    "ai_results",
    "tickets",
    "mock_applications",
    "mock_benefits",
    "mock_transactions",
    "mock_cards",
    "mock_customers",
)


async def reset_demo_data():
    if DB_BACKEND not in {"sqlite", "fallback", "mysql", "tdsql"}:
        raise RuntimeError(f"Unsupported DB_BACKEND={DB_BACKEND!r}")

    await init_db()
    with open(TICKETS_JSON, "r", encoding="utf-8") as f:
        tickets = json.load(f)

    async with get_db() as db:
        for table in RESET_TABLES:
            await db.execute(f"DELETE FROM {table}")
        for ticket in tickets:
            await insert_ticket_row(db, ticket)
        await db.commit()

    print(f"Reset local demo database with {len(tickets)} tickets from {TICKETS_JSON}.")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--confirm-reset-demo",
        action="store_true",
        help="Required. Confirms local demo data and processing records will be cleared.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if not args.confirm_reset_demo:
        raise SystemExit("Refusing to reset demo data without --confirm-reset-demo.")
    asyncio.run(reset_demo_data())
