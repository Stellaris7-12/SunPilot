"""Run Module F evaluation against labeled samples.

This script runs the business Agent chain without writing to the main SQLite
database. It requires a configured LLM key because the current Agents call the
LLM directly.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path


ENGINE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENGINE_DIR))

from config import LLM_API_KEY  # noqa: E402
from evaluation.evaluator import evaluator  # noqa: E402
from orchestrator.orchestrator import orchestrator  # noqa: E402
from orchestrator.workflow_config import load_workflow_config  # noqa: E402
from tools.mock_executor import mock_executor  # noqa: E402
from tools.registry import tool_registry  # noqa: E402


MISSING_KEY_VALUES = {"", "sk-your-api-key-here", "your-api-key", "YOUR_API_KEY"}


def _blocked_status(ticket: dict, intent: dict, workflow_config: dict, escalation: dict | None = None) -> str:
    intent_type = intent.get("type", "UNKNOWN")
    risk_level = ticket.get("riskLevel", ticket.get("risk_level", "low"))
    escalation = escalation or {}
    scenarios = workflow_config.get("scenarios", {})
    scenario_config = scenarios.get(intent_type, {})
    if escalation.get("risk_level") == "high" or risk_level == "high" or intent_type == "UNKNOWN":
        return "escalated"
    if risk_level == "medium" or scenario_config.get("requires_human_confirmation"):
        return "pending_human_confirm"
    return "escalated"


async def evaluate_sample(sample: dict, workflow_config: dict) -> dict:
    expected = sample.get("expected") or {}
    ticket = sample.get("ticket") or {}
    started = time.time()

    intent = await orchestrator.classifier_agent.run({
        "ticket_content": ticket.get("content", ""),
        "workflow_config": workflow_config,
    })
    fields = await orchestrator.intake_agent.run({
        "ticket_content": ticket.get("content", ""),
        "intent_type": intent.get("type", "UNKNOWN"),
        "intent_label": intent.get("label", ""),
        "workflow_config": workflow_config,
    })
    escalation = await orchestrator.escalation_agent.run({
        "ticket": {
            "risk_level": ticket.get("riskLevel", "low"),
            "risk_label": ticket.get("riskLabel", ""),
            "scene": sample.get("category", ""),
        },
        "intent": intent,
        "fields": fields.get("fields", []),
        "tool_result": None,
        "workflow_config": workflow_config,
    })

    resolution = {"tool_name": "", "tool_params": {}, "skip": True, "skip_reason": ""}
    tool_result = {}
    status = expected.get("expectedStatus", "pending_human_review")
    missing_fields = escalation.get("missing_fields", [])
    failure_reason = escalation.get("risk_decision", "")

    if escalation.get("needs_more_info"):
        status = "pending_info"
    elif not escalation.get("can_auto_proceed", True):
        status = _blocked_status(ticket, intent, workflow_config, escalation)
    else:
        resolution = await orchestrator.resolution_agent.run({
            "intent": intent,
            "fields": fields.get("fields", []),
            "available_tools": tool_registry.get_all_summaries(),
            "workflow_config": workflow_config,
        })
        tool_name = resolution.get("tool_name", "")
        tool_params = resolution.get("tool_params", {}) or {}
        if resolution.get("skip") or not tool_name:
            status = "pending_human_review" if not expected.get("requiresHuman") else "escalated"
        else:
            missing_params = tool_registry.get_missing_required_params(tool_name, tool_params)
            if missing_params:
                status = "pending_info"
                missing_fields = [item["name"] for item in missing_params]
                failure_reason = "missing required tool parameters"
            else:
                executed = await mock_executor.execute(tool_name, tool_params)
                tool_result = executed.model_dump(by_alias=True)
                escalation = await orchestrator.escalation_agent.run({
                    "ticket": {
                        "risk_level": ticket.get("riskLevel", "low"),
                        "risk_label": ticket.get("riskLabel", ""),
                        "scene": sample.get("category", ""),
                    },
                    "intent": intent,
                    "fields": fields.get("fields", []),
                    "tool_result": executed,
                    "workflow_config": workflow_config,
                })
                if not executed.success or not escalation.get("can_auto_proceed", True):
                    status = "escalated"
                    failure_reason = escalation.get("risk_decision", executed.failure_reason)
                else:
                    status = "pending_human_review"

    notification = await orchestrator.notification_agent.run({
        "ticket": {
            "id": sample.get("id", ""),
            "no": sample.get("id", ""),
            "title": ticket.get("title", ""),
            "customer_name": ticket.get("customerId", ""),
            "scene": sample.get("category", ""),
            "risk_level": ticket.get("riskLevel", "low"),
            "risk_label": ticket.get("riskLabel", ""),
        },
        "intent": intent,
        "fields": fields.get("fields", []),
        "tool_result": tool_result,
        "tool_request": resolution.get("tool_params", {}),
        "verify_result": escalation,
        "workflow_config": workflow_config,
        "status": status,
        "missing_fields": missing_fields,
        "failure_reason": failure_reason,
    })

    duration_ms = int((time.time() - started) * 1000)
    return {
        "sample": sample,
        "ticket": ticket,
        "expected": expected,
        "outputs": {
            "intent": intent,
            "fields": fields.get("fields", []),
            "escalation": escalation,
            "resolution": resolution,
            "toolResult": tool_result,
            "notification": notification.get("notification", {}),
            "replyDraft": notification.get("reply_draft", ""),
            "status": status,
            "durationMs": duration_ms,
            "requiresHumanReview": status in {
                "pending_info",
                "pending_human_confirm",
                "pending_human_review",
                "escalated",
                "failed",
            },
        },
    }


async def run(limit: int | None = None, ids: set[str] | None = None) -> dict:
    if LLM_API_KEY in MISSING_KEY_VALUES:
        raise RuntimeError(
            "LLM_API_KEY is not configured. Set DEEPSEEK_API_KEY or LLM_API_KEY "
            "before running Module F against real Agents."
        )

    workflow_config = load_workflow_config()
    samples = evaluator.reload()
    if ids:
        samples = [sample for sample in samples if sample.get("id") in ids]
    if limit:
        samples = samples[:limit]

    records = []
    for index, sample in enumerate(samples, start=1):
        print(f"[module-f] evaluating {index}/{len(samples)} {sample.get('id', '')}", file=sys.stderr)
        records.append(await evaluate_sample(sample, workflow_config))

    metrics = evaluator.compute_records(records, source="agent_run")
    return {
        "metrics": metrics.__dict__,
        "records": records,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Module F Agent evaluation")
    parser.add_argument("--limit", type=int, default=None, help="Only evaluate the first N samples")
    parser.add_argument("--ids", default="", help="Comma-separated sample IDs to evaluate")
    parser.add_argument("--records", action="store_true", help="Print per-sample records as well as metrics")
    parser.add_argument("--output", type=Path, default=None, help="Write the JSON payload to this file")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ids = {item.strip() for item in args.ids.split(",") if item.strip()}
    result = asyncio.run(run(limit=args.limit, ids=ids or None))
    payload = result if args.records else {"metrics": result["metrics"]}
    payload_text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload_text + "\n", encoding="utf-8")
        print(json.dumps({"metrics": result["metrics"], "output": str(args.output)}, ensure_ascii=False, indent=2))
    else:
        print(payload_text)


if __name__ == "__main__":
    main()
