"""Demo: IntakeAgent 规则快车道 vs LLM 兜底增强对比。

用途：答辩演示。同一批工单分别走两条路径，直观展示：

1. 规则快车道 (deterministic)：正则+结构化解析抽全部必填字段，命中即返回，
   零 LLM 调用、零延迟、可复现。
2. LLM 增强兜底 (llm_augmented)：规则漏抽必填字段时才触发 LLM，
   且 LLM 只补空缺、绝不覆盖规则已抽到的真实值 (_merge_fields)。

脚本不改动任何数据，只读取 workflow_config 并调用 IntakeAgent。
LLM 不可用时（无网络/无 key）会捕获异常，仍展示规则侧结果。

运行：
    cd ai-engine
    python scripts/demo_intake_modes.py
"""

import asyncio
import sys
from pathlib import Path


# Windows consoles often default to a GBK codepage; force UTF-8 so the
# Chinese demo output is readable during the defense (答辩).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "backend" / "src"))

from ticket_agent.agents.agent_registry import agent_registry  # noqa: E402
from ticket_agent.agents.intake_agent import IntakeAgent, _deterministic_fields, _fields_from_config  # noqa: E402
from ticket_agent.models.domain.agent_card import AgentCard  # noqa: E402
from ticket_agent.models.domain.workflow import workflow_scenario  # noqa: E402
from ticket_agent.orchestrator.workflow_config import load_workflow_config  # noqa: E402


# 两个对照样例：一个字段齐全（走快车道），一个缺必填（触发 LLM 兜底）。
DEMO_TICKETS = [
    {
        "title": "样例 A · 字段齐全 → 期望规则快车道",
        "intent_type": "协商还款",
        "intent_label": "协商还款",
        "ticket_content": (
            "客户号：88001234\n"
            "客户姓名：张伟\n"
            "手机号：13800138000\n"
            "账户号：6225880100012345\n"
            "发单内容：客户申请分12期协商还款，希望减免部分违约金。\n"
            "协商方案：分12期，每期还款2000元。"
        ),
    },
    {
        "title": "样例 B · 缺必填字段 → 期望 LLM 兜底增强",
        "intent_type": "协商还款",
        "intent_label": "协商还款",
        "ticket_content": (
            "我这张卡实在还不上了，想跟你们商量下能不能分期，"
            "本人张伟，手机13800138000，麻烦帮我看看方案。"
        ),
    },
]


def _fmt_fields(fields: list[dict]) -> str:
    if not fields:
        return "    (无)"
    return "\n".join(
        f"    - {f.get('label', f['name'])}({f['name']}): {f.get('value', '')!r}"
        for f in fields
    )


def _build_intake_agent() -> IntakeAgent:
    card = agent_registry.get("intake_agent") or AgentCard(
        agent_id="intake_agent", name="Intake Agent", description=""
    )
    return IntakeAgent(card)


async def _run_case(agent: IntakeAgent, workflow_config: dict, ticket: dict) -> None:
    intent_type = ticket["intent_type"]
    content = ticket["ticket_content"]

    print("=" * 72)
    print(ticket["title"])
    print("-" * 72)
    print("工单内容：")
    for line in content.splitlines():
        print(f"    {line}")

    required = workflow_scenario(workflow_config, intent_type).required_fields
    print(f"\n必填字段 (config)：{required}")

    # ---- 路径 1：纯规则抽取（不调用 LLM） ----
    rules_only = _deterministic_fields(
        content, _fields_from_config(intent_type, workflow_config)
    )
    present = {f["name"] for f in rules_only if str(f.get("value", "")).strip() not in {"", "未提供"}}
    missing = [name for name in required if name not in present]
    print("\n[路径1] 纯规则抽取结果：")
    print(_fmt_fields(rules_only))
    print(f"    规则漏抽的必填字段：{missing or '无（全部命中）'}")

    # ---- 路径 2：IntakeAgent.run（自动决定快车道 or LLM 兜底） ----
    print("\n[路径2] IntakeAgent.run() 实际执行：")
    input_data = {
        "ticket_content": content,
        "intent_type": intent_type,
        "intent_label": ticket["intent_label"],
        "workflow_config": workflow_config,
    }
    try:
        result = await agent.run(input_data)
        print(f"    extraction_mode = {result.get('extraction_mode')}")
        print(_fmt_fields(result.get("fields", [])))
    except Exception as exc:  # noqa: BLE001 - demo 需在 LLM 不可用时优雅降级
        print(f"    [LLM 调用失败，降级展示规则侧] {type(exc).__name__}: {exc}")
        print("    说明：真实环境接入 DeepSeek/OpenAI 后此处将返回 llm_augmented 结果。")
    print()


async def main() -> None:
    workflow_config = load_workflow_config()
    agent = _build_intake_agent()

    print("\nIntakeAgent 双路径对比演示 (规则快车道 vs LLM 兜底增强)\n")
    for ticket in DEMO_TICKETS:
        await _run_case(agent, workflow_config, ticket)

    print("=" * 72)
    print("结论：")
    print("  · 字段齐全时走规则快车道，0 次 LLM 调用、结果可复现；")
    print("  · 字段缺失时才触发 LLM，且 LLM 仅补空缺、不覆盖规则真实值；")
    print("  · 判定标准来自 workflow_config 的 required_fields（单一事实来源）。")
    print("=" * 72)


if __name__ == "__main__":
    asyncio.run(main())
