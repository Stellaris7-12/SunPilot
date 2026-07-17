"""Orchestrator — coordinates the 5-agent pipeline with HITL pause/resume."""
# (license header omitted for brevity)

import asyncio
import json
import logging
import time
from typing import Optional

from models.ticket import Ticket, TicketStatus, RiskLevel
from models.ai_result import AiProcessResult, IntentResult, FieldResult, VerifyCheck
from models.agent_card import AgentCard
from models.database import get_db

from agents.intent_agent import IntentAgent
from agents.extract_agent import ExtractAgent
from agents.tool_agent import ToolCallingAgent
from agents.verify_agent import VerifyAgent
from agents.reply_agent import ReplyAgent
from agents.agent_registry import agent_registry

from tools.registry import tool_registry
from tools.mock_executor import mock_executor

from orchestrator.state_machine import TicketStateMachine, TicketState
from orchestrator.trace import TraceCollector, TraceStatus

logger = logging.getLogger(__name__)


class Orchestrator:
    """Coordinates the 5-agent pipeline for credit card ticket processing.

    The pipeline adapts based on risk level:
    - LOW risk: Intent → Extract → Verify → Tool → Reply → human review
    - MEDIUM risk: Intent → Extract → Verify → pause → human confirm → Tool → Reply → human review
    - HIGH risk: Pre-check → skip Tool + Reply → escalate → human processes
    """

    def __init__(self):
        # Load agent cards from registry
        self.intent_agent = IntentAgent(
            agent_registry.get("intent_agent") or AgentCard(agent_id="intent_agent", name="意图识别Agent", description=""))
        self.extract_agent = ExtractAgent(
            agent_registry.get("extract_agent") or AgentCard(agent_id="extract_agent", name="字段抽取Agent", description=""))
        self.tool_agent = ToolCallingAgent(
            agent_registry.get("tool_agent") or AgentCard(agent_id="tool_agent", name="工具调用Agent", description=""))
        self.verify_agent = VerifyAgent(
            agent_registry.get("verify_agent") or AgentCard(agent_id="verify_agent", name="审核校验Agent", description=""))
        self.reply_agent = ReplyAgent(
            agent_registry.get("reply_agent") or AgentCard(agent_id="reply_agent", name="回单生成Agent", description=""))

    # ==================================================================
    # Main Pipeline
    # ==================================================================

    async def process_ticket(
        self,
        ticket_id: str,
        trace: TraceCollector,
        event_queue: asyncio.Queue | None = None,
    ) -> dict:
        """Execute the full 5-agent pipeline on a ticket.

        Args:
            ticket_id: The ticket to process.
            trace: TraceCollector for recording execution steps.
            event_queue: Optional asyncio.Queue for real-time SSE event streaming.
                         Each item is a dict: {'event': 'agent_start'|'agent_complete'|..., 'data': {...}}

        Returns:
            Dict with keys: all AiProcessResult fields, _status, _total_duration_ms
        """
        overall_start = time.time()

        # Helper to push SSE events
        async def push(event: str, data: dict):
            if event_queue is not None:
                await event_queue.put({"event": event, "data": data})

        # Load ticket from DB
        ticket = await self._load_ticket(ticket_id)
        if ticket is None:
            return self._error_result(f"工单 {ticket_id} 不存在", trace)

        # ================================================================
        # Pre-check: HIGH risk tickets skip auto-processing entirely
        # ================================================================
        if ticket.risk_level == RiskLevel.HIGH or ticket.risk_level == RiskLevel.HIGH.value:
            logger.info(f"[Orchestrator] Ticket {ticket_id} is HIGH risk — escalating")
            trace.add_step(
                agent="审核校验Agent", agent_id="verify_agent",
                summary="高风险工单，跳过自动处理，直接转人工审核",
                duration="0ms", status=TraceStatus.SKIPPED
            )

            result = AiProcessResult(
                workflow_name="escalated_flow",
                risk_decision="高风险工单，已转人工审核",
                verify_checks=[
                    VerifyCheck(label="自动处理", status="已拦截"),
                    VerifyCheck(label="风险等级", status="需复核"),
                ],
                requires_human_review=True,
            )
            total_ms = int((time.time() - overall_start) * 1000)
            await push("workflow_complete", {"ticket_id": ticket_id, "status": TicketState.ESCALATED.value, "total_duration_ms": total_ms, "result": result.model_dump()})
            return {
                **result.model_dump(),
                "_status": TicketState.ESCALATED.value,
                "_total_duration_ms": total_ms,
            }

        # ================================================================
        # Step 1: IntentAgent
        # ================================================================
        intent_result = await self._run_agent_step(
            "intent_agent", "意图识别Agent",
            self.intent_agent,
            {"ticket_content": ticket.content},
            trace, push,
        )

        # ================================================================
        # Step 2: ExtractAgent
        # ================================================================
        extract_result = await self._run_agent_step(
            "extract_agent", "字段抽取Agent",
            self.extract_agent,
            {
                "ticket_content": ticket.content,
                "intent_type": intent_result.get("type", "UNKNOWN"),
                "intent_label": intent_result.get("label", "未知"),
            },
            trace, push,
        )

        # ================================================================
        # Step 3: VerifyAgent (runs BEFORE tool, to assess risk early)
        # ================================================================
        verify_result = await self._run_agent_step(
            "verify_agent", "审核校验Agent",
            self.verify_agent,
            {
                "ticket": {
                    "risk_level": ticket.risk_level,
                    "risk_label": ticket.risk_label,
                    "scene": ticket.scene,
                },
                "intent": intent_result,
                "fields": extract_result.get("fields", []),
            },
            trace, push,
        )

        # ================================================================
        # Decision: escalate high risk or pause for medium risk
        # ================================================================
        risk_level = verify_result.get("risk_level", "low")
        can_auto = verify_result.get("can_auto_proceed", True)

        if not can_auto:
            logger.info(f"[Orchestrator] VerifyAgent blocked — escalating")
            trace.add_step(
                agent="审核校验Agent", agent_id="verify_agent",
                summary=verify_result.get("risk_decision", "需人工处理"),
                duration="0ms", status=TraceStatus.SKIPPED,
            )
            return self._build_result(
                ticket, intent_result, extract_result, None, verify_result,
                "", status=TicketState.ESCALATED.value,
                total_start=overall_start,
            )

        # For medium risk: pause and wait for human confirmation
        if risk_level == "medium":
            logger.info(f"[Orchestrator] Medium risk — pausing for human confirmation")
            await push("workflow_paused", {
                "reason": "中风险操作需人工确认后继续",
                "ticket_id": ticket_id,
                "paused_at": "verify_agent",
            })
            return self._build_result(
                ticket, intent_result, extract_result, None, verify_result,
                "", status=TicketState.PENDING_HUMAN_CONFIRM.value,
                total_start=overall_start,
            )

        # ================================================================
        # Step 4: ToolCallingAgent
        # ================================================================
        available_tools = tool_registry.get_all_summaries()
        tool_agent_result = await self._run_agent_step(
            "tool_agent", "工具调用Agent",
            self.tool_agent,
            {
                "intent": intent_result,
                "fields": extract_result.get("fields", []),
                "available_tools": available_tools,
            },
            trace, push,
        )

        # Execute the selected tool (or skip)
        tool_result = None
        if not tool_agent_result.get("skip"):
            tool_name = tool_agent_result.get("tool_name", "")
            tool_params = tool_agent_result.get("tool_params", {})
            if tool_name:
                logger.info(f"[Orchestrator] Executing tool: {tool_name}")
                tool_result = await mock_executor.execute(tool_name, tool_params)

        # ================================================================
        # Step 5: ReplyAgent
        # ================================================================
        reply_result = await self._run_agent_step(
            "reply_agent", "回单生成Agent",
            self.reply_agent,
            {
                "intent": intent_result,
                "fields": extract_result.get("fields", []),
                "tool_result": tool_result.model_dump() if tool_result else None,
                "verify_result": verify_result,
            },
            trace, push,
        )

        # ================================================================
        # Build final result
        # ================================================================
        return self._build_result(
            ticket, intent_result, extract_result,
            tool_result, verify_result,
            reply_result.get("reply_draft", ""),
            status=TicketState.PENDING_HUMAN_REVIEW.value,
            total_start=overall_start,
        )

    # ==================================================================
    # Helpers
    # ==================================================================

    async def _load_ticket(self, ticket_id: str) -> Optional[Ticket]:
        """Load a ticket from the database."""
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT * FROM tickets WHERE id = ?", (ticket_id,)
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return Ticket(
                id=row["id"], no=row["no"], title=row["title"],
                customer_name=row["customer_name"], phone=row["phone"],
                card_last4=row["card_last4"], scene=row["scene"],
                created_at=row["created_at"], risk_label=row["risk_label"],
                risk_level=row["risk_level"], status=TicketStatus(row["status"]),
                content=row["content"],
            )

    async def _run_agent_step(
        self,
        agent_id: str,
        agent_name: str,
        agent,
        input_data: dict,
        trace: TraceCollector,
        push=None,
    ) -> dict:
        """Run a single agent step with trace collection and real-time SSE push."""
        start = time.time()

        # Push agent_start event
        if push:
            await push("agent_start", {"agent_id": agent_id, "agent_name": agent_name, "timestamp": time.time()})
            await push("agent_thinking", {"agent_id": agent_id, "message": f"正在执行{agent_name}..."})

        # Add trace step (RUNNING)
        trace.add_step(
            agent=agent_name, agent_id=agent_id,
            summary="执行中...", duration="等待返回",
            status=TraceStatus.RUNNING,
        )

        try:
            result = await agent.run(input_data)
            elapsed_ms = int((time.time() - start) * 1000)
            summary = self._build_step_summary(agent_id, result)

            # Update trace to SUCCESS
            trace.update_last(summary, f"{elapsed_ms}ms", TraceStatus.SUCCESS)

            # Push agent_complete event
            if push:
                await push("agent_complete", {
                    "agent_id": agent_id,
                    "summary": summary,
                    "duration_ms": elapsed_ms,
                    "result": result,
                })

            logger.info(f"[Orchestrator] {agent_name} completed in {elapsed_ms}ms")
            return result

        except Exception as e:
            elapsed_ms = int((time.time() - start) * 1000)
            error_msg = f"执行失败: {str(e)[:100]}"
            trace.update_last(error_msg, f"{elapsed_ms}ms", TraceStatus.FAILED)

            if push:
                await push("error", {"agent_id": agent_id, "message": error_msg, "code": type(e).__name__})

            logger.exception(f"[Orchestrator] {agent_name} failed")
            return {}

    def _build_step_summary(self, agent_id: str, result: dict) -> str:
        """Generate a human-readable summary of what the agent did."""
        if agent_id == "intent_agent":
            return f"已识别为{result.get('label', '未知')}场景（置信度 {result.get('confidence', 0):.0%}）"
        elif agent_id == "extract_agent":
            fields = result.get("fields", [])
            valid = [f for f in fields if f.get("value", "未提及") != "未提及"]
            return f"已提取 {len(valid)}/{len(fields)} 个有效字段"
        elif agent_id == "tool_agent":
            if result.get("skip"):
                return f"跳过工具调用: {result.get('skip_reason', '')}"
            return f"已选择工具: {result.get('tool_name', '无')}"
        elif agent_id == "verify_agent":
            return result.get("risk_decision", "校验完成")
        elif agent_id == "reply_agent":
            draft = result.get("reply_draft", "")
            return f"已生成回单草稿（{len(draft)}字）"
        return "处理完成"

    def _build_result(
        self,
        ticket: Ticket,
        intent_result: dict,
        extract_result: dict,
        tool_result,
        verify_result: dict,
        reply_draft: str,
        status: str,
        total_start: float,
    ) -> dict:
        """Assemble the final AiProcessResult with all pipeline outputs."""
        intent = IntentResult(
            type=intent_result.get("type", "UNKNOWN"),
            label=intent_result.get("label", "未知"),
            confidence=intent_result.get("confidence", 0.0),
            workflow_name=intent_result.get("workflow_name", ""),
            reason=intent_result.get("reason", ""),
        )

        fields = [
            FieldResult(**f)
            for f in extract_result.get("fields", [])
        ]

        checks = [
            VerifyCheck(**c)
            for c in verify_result.get("checks", [])
        ]

        tool_evidence = ""
        tool_name = ""
        tool_request = {}
        tool_response = {}
        if tool_result:
            tool_evidence = (
                f"{tool_result.tool_name} 调用成功，"
                f"证据编号 {tool_result.evidence_id}"
            )
            tool_name = tool_result.tool_name
            tool_response = tool_result.data

        result = AiProcessResult(
            workflow_name=intent.workflow_name,
            risk_decision=verify_result.get("risk_decision", ""),
            intent=intent,
            fields=fields,
            tool_evidence=tool_evidence,
            tool_name=tool_name,
            tool_request=tool_request,
            tool_response=tool_response,
            verify_checks=checks,
            reply_draft=reply_draft,
            requires_human_review=True,
        )

        total_ms = int((time.time() - total_start) * 1000)

        return {
            **result.model_dump(),
            "_status": status,
            "_total_duration_ms": total_ms,
        }

    def _error_result(self, message: str, trace: TraceCollector) -> dict:
        """Build an error result."""
        trace.add_step(
            agent="编排器", agent_id="orchestrator",
            summary=message, duration="0ms",
            status=TraceStatus.FAILED,
        )
        result = AiProcessResult(
            workflow_name="error_flow",
            risk_decision=message,
            requires_human_review=True,
        )
        return {
            **result.model_dump(),
            "_status": TicketState.ESCALATED.value,
            "_total_duration_ms": 0,
        }


# Module-level singleton
orchestrator = Orchestrator()
