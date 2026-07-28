#!/usr/bin/env python3
"""检查工单表中的重复客户"""
import asyncio
import sys
from pathlib import Path

# 添加 backend/src 到 sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR / "backend" / "src"))

from ticket_agent.models.database import get_db

async def check_duplicates():
    """查询重复客户统计"""
    sys.stdout.reconfigure(encoding='utf-8')

    # 使用 async with 获取session
    async with get_db() as session:
        # 查询客户出现次数
        result = await session.execute("""
            SELECT customer_id, customer_name, COUNT(*) as cnt
            FROM tickets
            GROUP BY customer_id, customer_name
            HAVING cnt > 1
            ORDER BY cnt DESC
            LIMIT 10
        """)

        print("=== 重复客户统计(TOP 10) ===")
        rows = await result.fetchall()
        if not rows:
            print("没有重复客户")
        else:
            for row in rows:
                print(f"{row['customer_name']} ({row['customer_id']}): {row['cnt']} 条工单")

        print("\n=== 陆琪(C30113)的所有工单 ===")
        result2 = await session.execute("""
            SELECT ticket_no, title, category, status, created_at
            FROM tickets
            WHERE customer_id = 'C30113'
            ORDER BY created_at DESC
        """)

        rows2 = await result2.fetchall()
        if not rows2:
            print("无记录")
        else:
            for row in rows2:
                title = row['title'][:30] if len(row['title']) > 30 else row['title']
                print(f"{row['ticket_no']} | {title} | {row['category']} | {row['status']}")

        print("\n=== 顾明(C30112)的所有工单 ===")
        result3 = await session.execute("""
            SELECT ticket_no, title, category, status, created_at
            FROM tickets
            WHERE customer_id = 'C30112'
            ORDER BY created_at DESC
        """)

        rows3 = await result3.fetchall()
        if not rows3:
            print("无记录")
        else:
            for row in rows3:
                title = row['title'][:30] if len(row['title']) > 30 else row['title']
                print(f"{row['ticket_no']} | {title} | {row['category']} | {row['status']}")

        # 统计总工单数
        result4 = await session.execute("SELECT COUNT(*) as total FROM tickets")
        rows4 = await result4.fetchall()
        print(f"\n=== 总工单数: {rows4[0]['total']} ===")

if __name__ == "__main__":
    asyncio.run(check_duplicates())
