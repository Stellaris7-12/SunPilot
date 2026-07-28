#!/usr/bin/env python3
"""验证生成的数据质量"""
import asyncio
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR / "backend" / "src"))

from ticket_agent.models.database import get_db

async def verify():
    sys.stdout.reconfigure(encoding='utf-8')

    async with get_db() as session:
        # 客户分布
        r = await session.execute(
            'SELECT customer_name, customer_id, COUNT(*) as cnt FROM tickets GROUP BY customer_id, customer_name ORDER BY cnt DESC LIMIT 10'
        )
        rows = await r.fetchall()
        print('=== 客户工单数TOP10 ===')
        for row in rows:
            print(f'  {row[0]} ({row[1]}): {row[2]}条')

        # 类型分布
        r = await session.execute(
            'SELECT category, COUNT(*) as cnt FROM tickets GROUP BY category ORDER BY cnt DESC'
        )
        rows = await r.fetchall()
        print('\n=== 工单类型分布 ===')
        for row in rows:
            print(f'  {row[0]}: {row[1]}条')

        # 总数
        r = await session.execute('SELECT COUNT(*) as total FROM tickets')
        rows = await r.fetchall()
        total = rows[0][0] if rows else 0
        print(f'\n总工单数: {total}')

asyncio.run(verify())
