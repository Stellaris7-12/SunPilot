#!/usr/bin/env python3
import asyncio
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR / "backend" / "src"))

from ticket_agent.models.database import get_db

async def check():
    async with get_db() as session:
        r = await session.execute('SELECT COUNT(*) FROM tickets')
        result = await r.fetchall()
        print(f"查询结果类型: {type(result)}")
        print(f"查询结果: {result}")
        if result:
            print(f"第一行: {result[0]}")
            print(f"第一行类型: {type(result[0])}")

asyncio.run(check())
