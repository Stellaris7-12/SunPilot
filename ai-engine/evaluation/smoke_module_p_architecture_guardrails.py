"""Module P smoke checks for architecture guardrails.

These checks intentionally stay static and lightweight. They prevent the
architecture from drifting back to extra business agents, legacy agent names in
the public registry, or AI actions outside SunPilot.
"""

import json
import sys
from pathlib import Path


ENGINE_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = ENGINE_DIR.parent
sys.path.insert(0, str(ENGINE_DIR))


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
    cards_path = ENGINE_DIR / "data" / "agent_cards.json"
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

    orchestrator_source = read_text(ENGINE_DIR / "orchestrator" / "orchestrator.py")
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

    app_header = read_text(ROOT_DIR / "frontend" / "src" / "components" / "layout" / "AppHeader.vue")
    legacy_detail = read_text(ROOT_DIR / "frontend" / "src" / "views" / "LegacyTicketDetailView.vue")
    legacy_assistant = read_text(ROOT_DIR / "frontend" / "src" / "components" / "ai" / "PageAssistantPanel.vue")
    agent_panel = read_text(ROOT_DIR / "frontend" / "src" / "page-agent" / "panel" / "AgentPanel.vue")

    assert_not_contains(app_header, "启动 AI", "AppHeader must not render an AI action")
    assert_not_contains(app_header, "@process", "AppHeader must not emit AI process events")
    assert_not_contains(legacy_detail, "PageAssistantPanel", "Legacy detail must mount SunPilot AgentPanel")
    assert_true("<AgentPanel" in legacy_detail, "Legacy detail must mount AgentPanel")
    assert_true("<AgentPanel" in legacy_assistant, "PageAssistantPanel must remain a thin AgentPanel wrapper")
    assert_true("startAiProcess" in agent_panel, "SunPilot AgentPanel must own the AI process quick action")

    print("module P architecture guardrails smoke passed")


if __name__ == "__main__":
    main()
