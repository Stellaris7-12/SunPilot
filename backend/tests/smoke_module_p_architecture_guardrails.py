"""Module P smoke checks for architecture guardrails.

These checks intentionally stay static and lightweight. They prevent the
architecture from drifting back to extra business agents, legacy agent names in
the public registry, or AI actions outside SunPilot.
"""

import json
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR / "tests"))


EXPECTED_BUSINESS_AGENTS = {
    "classifier_agent",
    "intake_agent",
    "resolution_agent",
    "escalation_agent",
    "notification_agent",
}
LEGACY_AGENT_IDS = {
    "intent_agent",
    "extract_agent",
    "tool_agent",
    "verify_agent",
    "reply_agent",
    "dispatcher_agent",
}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def assert_true(condition: bool, message: str):
    if not condition:
        raise AssertionError(message)


def assert_not_contains(source: str, needle: str, message: str):
    assert_true(needle not in source, message)


def main():
    cards_path = BACKEND_DIR / "src" / "ticket_agent" / "data" / "agent_cards.json"
    cards = json.loads(read_text(cards_path))
    agent_ids = {card["agent_id"] for card in cards}

    assert_true(
        agent_ids == EXPECTED_BUSINESS_AGENTS,
        f"agent_cards.json must expose exactly five business agents, got {sorted(agent_ids)}",
    )
    assert_true(
        not (agent_ids & LEGACY_AGENT_IDS),
        f"legacy shim ids must not be registered: {sorted(agent_ids & LEGACY_AGENT_IDS)}",
    )

    orchestrator_source = read_text(BACKEND_DIR / "src" / "ticket_agent" / "orchestrator" / "orchestrator.py")
    for agent_id in EXPECTED_BUSINESS_AGENTS:
        assert_true(
            f'agent_registry.get("{agent_id}")' in orchestrator_source,
            f"Orchestrator must wire registered business agent {agent_id}",
        )
    assert_not_contains(
        orchestrator_source,
        'agent_registry.get("dispatcher_agent")',
        "DispatcherAgent must not be wired as a sixth backend business agent",
    )

    # P1-7 fix: PipelineContext is a dataclass, not a dict. The tool-failure
    # self-heal retry must use attribute access, never ctx.get()/ctx[...],
    # otherwise every tool failure raises AttributeError and collapses to FAILED.
    pipeline_context_source = read_text(BACKEND_DIR / "src" / "ticket_agent" / "orchestrator" / "pipeline_context.py")
    assert_true(
        "tool_retry_attempted" in pipeline_context_source,
        "PipelineContext must declare tool_retry_attempted for the self-heal retry guard",
    )
    assert_not_contains(
        orchestrator_source,
        'ctx.get("_tool_retry_attempted")',
        "Retry guard must use ctx.tool_retry_attempted, not dict-style ctx.get()",
    )
    assert_not_contains(
        orchestrator_source,
        'ctx["_tool_retry_attempted"]',
        "Retry guard must use ctx.tool_retry_attempted, not dict-style ctx[...]",
    )
    assert_true(
        "ctx.tool_retry_attempted" in orchestrator_source,
        "Retry guard must read/write ctx.tool_retry_attempted attribute",
    )

    # AI process action is owned exclusively by the SunPilot panel. The shell's
    # top bar and the layout wrapper must not render or emit their own AI action;
    # the SunPilot panel owns startAiProcess and the shell wires it via @start-ai-process.
    shell_view = read_text(ROOT_DIR / "frontend" / "src" / "views" / "EnterpriseTicketShellView.vue")
    enterprise_layout = read_text(ROOT_DIR / "frontend" / "src" / "layouts" / "EnterpriseLayout.vue")
    sunpilot_panel = read_text(ROOT_DIR / "frontend" / "src" / "sunpilot" / "panel" / "SunPilotPanel.vue")

    assert_not_contains(shell_view, "启动 AI", "Shell top bar must not render an AI action button")
    assert_true("<SunPilotPanel" in shell_view, "Shell must mount the SunPilot panel")
    assert_true(
        '@start-ai-process="handleProcess"' in shell_view,
        "Shell must wire the AI process action through the SunPilot panel event",
    )
    assert_not_contains(
        enterprise_layout,
        "startAiProcess",
        "Enterprise layout wrapper must not own the AI process action",
    )
    assert_true(
        "startAiProcess" in sunpilot_panel,
        "SunPilot panel must own the AI process quick action",
    )

    print("module P architecture guardrails smoke passed")


if __name__ == "__main__":
    main()
