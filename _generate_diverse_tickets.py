#!/usr/bin/env python3
"""生成多样化的演示数据,避免客户重复"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta
import random

# 添加 backend/src 到 sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR / "backend" / "src"))

from ticket_agent.models.database import get_db

# 多样化的客户池(30个客户,确保50条工单时每个客户最多2条)
CUSTOMERS = [
    ("C20001", "张明"), ("C20002", "李娜"), ("C20003", "王芳"), ("C20004", "刘洋"),
    ("C20005", "陈静"), ("C20006", "赵强"), ("C20007", "孙丽"), ("C20008", "周杰"),
    ("C20009", "吴婷"), ("C20010", "郑浩"), ("C20011", "冯雪"), ("C20012", "于涛"),
    ("C20013", "蒋敏"), ("C20014", "韩冰"), ("C20015", "曹军"), ("C20016", "许梅"),
    ("C20017", "谢辉"), ("C20018", "邹文"), ("C20019", "苗琳"), ("C20020", "姚斌"),
    ("C30001", "胡静"), ("C30002", "林峰"), ("C30003", "唐莉"), ("C30004", "江涛"),
    ("C30005", "秦慧"), ("C30006", "袁强"), ("C30007", "段雪"), ("C30008", "贾明"),
    ("C30009", "薛婷"), ("C30010", "顾浩"),
]

CATEGORIES = [
    "协商还款", "伪冒调查", "客户经营", "权益与活动", "账单查询",
    "额度调整", "分期办理", "卡片激活", "密码重置", "挂失补卡"
]

DEPARTMENTS = [
    "信用卡运营组", "信用卡权益组", "卡部[上海卡部]", "风险管理部", "客服中心"
]

STATUSES = ["open", "in_progress", "pending_info", "pending_human_review"]

async def generate_diverse_tickets():
    """生成多样化工单数据"""
    sys.stdout.reconfigure(encoding='utf-8')

    async with get_db() as session:
        # 先清空关联表,再清空工单数据
        print("=== 清空现有数据(级联删除) ===")
        await session.execute("DELETE FROM agent_execution_log")
        await session.execute("DELETE FROM ticket_operation_log")
        await session.execute("DELETE FROM tool_call_log")
        await session.execute("DELETE FROM trace_steps")
        await session.execute("DELETE FROM ai_results")
        await session.execute("DELETE FROM tickets")
        # 不需要手动commit,async with会自动commit
        print("✅ 已清空所有关联数据")

        # 生成50条工单,每个客户最多2条,类型均衡分布
        print("=== 生成50条多样化工单(类型均衡) ===")
        base_time = datetime.now() - timedelta(days=30)
        ticket_id = 10000

        customer_usage = {}  # 记录每个客户使用次数
        category_usage = {cat: 0 for cat in CATEGORIES}  # 记录每个类型使用次数

        for i in range(50):
            # 均衡选择客户:优先选择使用次数少的
            min_customer_usage = min((customer_usage.get(c[0], 0) for c in CUSTOMERS), default=0)
            least_used_customers = [c for c in CUSTOMERS if customer_usage.get(c[0], 0) == min_customer_usage]
            customer_id, customer_name = random.choice(least_used_customers)
            customer_usage[customer_id] = customer_usage.get(customer_id, 0) + 1

            # 均衡选择类型:优先选择使用次数少的
            min_usage = min(category_usage.values())
            least_used_categories = [cat for cat, cnt in category_usage.items() if cnt == min_usage]
            category = random.choice(least_used_categories)
            category_usage[category] += 1

            department = random.choice(DEPARTMENTS)
            status = random.choice(STATUSES)
            created_at = base_time + timedelta(hours=i*12 + random.randint(0, 600))

            ticket_no = f"{random.choice(['112026', '132026', '292026'])}{607 + i:04d}"

            await session.execute("""
                INSERT INTO tickets (
                    id, no, title, customer_id, customer_name, phone, card_last4,
                    scene, category, subcategory, priority, channel, assignee,
                    department, created_at, status, content, risk_label, risk_level
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?
                )
            """, (
                f"demo_{ticket_id}",
                ticket_no,
                f"{category}工单#{i+1}",
                customer_id,
                customer_name,
                f"138{random.randint(1000,9999)}{random.randint(1000,9999)}",
                f"{random.randint(1000,9999)}",
                category,
                category,
                "",
                random.choice(["normal", "normal", "urgent"]),
                random.choice(["客服发单", "网点转办", "系统自动"]),
                random.choice(["王坐席", "刘坐席", "张坐席", "李坐席"]),
                department,
                created_at.strftime("%Y-%m-%d %H:%M:%S"),
                status,
                f"客户{customer_name}({customer_id})的{category}请求",
                "",
                "low"
            ))
            ticket_id += 1

        print(f"✅ 成功生成 50 条工单")

    # 用新连接验证数据
    async with get_db() as verify_session:
        result = await verify_session.execute("SELECT COUNT(*) as total FROM tickets")
        rows = await result.fetchall()
        actual_count = rows[0]['total'] if rows else 0
        print(f"📊 数据库实际记录数: {actual_count}")

        # 验证类型分布
        result_cat = await verify_session.execute("""
            SELECT category, COUNT(*) as cnt
            FROM tickets
            GROUP BY category
            ORDER BY cnt DESC
        """)
        rows_cat = await result_cat.fetchall()
        print("\n=== 工单类型分布 ===")
        for row in rows_cat:
            print(f"  {row['category']}: {row['cnt']} 条")

        # 验证重复情况
        result2 = await verify_session.execute("""
            SELECT customer_id, customer_name, COUNT(*) as cnt
            FROM tickets
            GROUP BY customer_id, customer_name
            HAVING cnt > 2
            ORDER BY cnt DESC
        """)
        rows2 = await result2.fetchall()

        if rows2:
            print("\n⚠️ 仍有客户超过2条工单:")
            for row in rows2:
                print(f"  {row['customer_name']} ({row['customer_id']}): {row['cnt']} 条")
        else:
            print("\n✅ 所有客户工单数 ≤ 2,数据多样化!")

if __name__ == "__main__":
    asyncio.run(generate_diverse_tickets())
