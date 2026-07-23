"""Orchestrator for the ticket-processing agent pipeline."""

import asyncio
import logging
import time
from typing import Optional

from agents.agent_registry import agent_registry
from agents.classifier_agent import ClassifierAgent
from agents.escalation_agent import EscalationAgent
from agents.intake_agent import IntakeAgent
from agents.notification_agent import NotificationAgent
from agents.resolution_agent import ResolutionAgent
from models.agent_card import AgentCard
from models.agent_contracts import (
    ClassifierInput,
    EscalationInput,
    IntakeInput,
    NotificationInput,
    ResolutionInput,
    TicketContext,
    coerce_intake_result,
    coerce_intent_result,
    coerce_risk_decision,
    coerce_tool_plan,
)
from models.ai_result import (
    AiProcessResult,
    FieldEnrichmentResult,
    FieldResult,
    IntentResult,
    PageTaskActionEnvelope,
    PageTaskEnvelope,
    VerifyCheck,
)
from models.repositories import agent_execution_log_repository, ticket_repository, tool_call_repository
from models.ticket import RiskLevel, Ticket, TicketStatus
from models.workflow import workflow_scenario
from orchestrator.pipeline_context import PipelineContext
from orchestrator.schema_validator import validate_agent_payload
from orchestrator.state_machine import TicketState, TicketStateMachine
from orchestrator.trace import TraceCollector, TraceStatus
from orchestrator.workflow_config import load_workflow_config
from tools.mock_executor import mock_executor
from tools.registry import tool_registry

logger = logging.getLogger(__name__)


class Orchestrator:
    """Coordinates the business-agent ticket-processing pipeline."""

    def __init__(self):
        self.classifier_agent = ClassifierAgent(
            agent_registry.get("classifier_agent")
            or AgentCard(agent_id="classifier_agent", name="Classifier Agent", description="")
        )
        self.intake_agent = IntakeAgent(
            agent_registry.get("intake_agent")
            or AgentCard(agent_id="intake_agent", name="Intake Agent", description="")
        )
        self.resolution_agent = ResolutionAgent(
            agent_registry.get("resolution_agent")
            or AgentCard(agent_id="resolution_agent", name="Resolution Agent", description="")
        )
        self.escalation_agent = EscalationAgent(
            agent_registry.get("escalation_agent")
            or AgentCard(agent_id="escalation_agent", name="Escalation Agent", description="")
        )
        self.notification_agent = NotificationAgent(
            agent_registry.get("notification_agent")
            or AgentCard(agent_id="notification_agent", name="Notification Agent", description="")
        )

        # Backward-compatible aliases for tests or older local scripts.
        self.intent_agent = self.classifier_agent
        self.extract_agent = self.intake_agent
        self.tool_agent = self.resolution_agent
        self.verify_agent = self.escalation_agent
        self.reply_agent = self.notification_agent

    async def process_ticket(
        self,
        ticket_id: str,
        trace: TraceCollector,
        event_queue: asyncio.Queue | None = None,
        *,
        confirmed: bool = False,
    ) -> dict:
        overall_start = time.time()

        async def push(event: str, data: dict):
            if event_queue is not None:
                await event_queue.put({"event": event, "data": data})

        ctx = PipelineContext(
            ticket_id=ticket_id,
            trace=trace,
            push=push,
            overall_start=overall_start,
            confirmed=confirmed,
        )

        try:
            workflow_config = load_workflow_config()
            ctx.workflow_config = workflow_config
            ticket = await self._load_ticket(ticket_id)
            if ticket is None:
                return await self._fail(ctx, f"Ticket {ticket_id} not found")
            ctx.ticket = ticket

            await self._set_ticket_status(ticket, TicketState.IN_PROGRESS.value)

            if ticket.risk_level == RiskLevel.HIGH or ticket.risk_level == RiskLevel.HIGH.value:
                result = await self._handle_high_risk(ctx)
                await self._emit_terminal(push, ticket_id, result)
                return result

            ticket_context = self._build_ticket_context(ticket)
            ctx.ticket_context = ticket_context
            intent_result = await self._run_agent_step(
                "classifier_agent",
                "Classifier Agent / 分类与优先级判定",
                self.classifier_agent,
                ClassifierInput(
                    ticket_content=ticket_context,
                    workflow_config=workflow_config,
                ).to_agent_dict(),
                trace,
                push,
            )
            intent_result = coerce_intent_result(intent_result)
            ctx.intent_result = intent_result

            extract_result = await self._run_agent_step(
                "intake_agent",
                "Intake Agent / 接单与信息提取",
                self.intake_agent,
                IntakeInput(
                    ticket_content=ticket_context,
                    intent_type=intent_result.get("type", "UNKNOWN"),
                    intent_label=intent_result.get("label", "未知"),
                    workflow_config=workflow_config,
                ).to_agent_dict(),
                trace,
                push,
            )
            extract_result = coerce_intake_result(extract_result)
            ctx.extract_result = extract_result

            await self._run_field_enrichment(
                ticket,
                intent_result,
                extract_result,
                workflow_config,
                trace,
                push,
            )

            verify_result = await self._run_escalation_step(
                ticket,
                intent_result,
                extract_result,
                workflow_config,
                trace,
                push,
            )
            ctx.verify_result = verify_result

            early_result = await self._maybe_stop_before_resolution(ctx)
            if early_result:
                return early_result

            available_tool_names = [
                tool.name
                for tool in tool_registry.list_for_intent(
                    intent_result.get("type", "UNKNOWN"),
                    workflow_config,
                )
            ]
            ctx.available_tool_names = available_tool_names
            tool_agent_result = await self._run_agent_step(
                "resolution_agent",
                "Resolution Agent / 解决方案与执行",
                self.resolution_agent,
                ResolutionInput(
                    intent=intent_result,
                    fields=extract_result.get("fields", []),
                    ticket_content=ticket_context,
                    ticket=self._ticket_payload(ticket),
                    available_tool_names=available_tool_names,
                    available_tools=tool_registry.get_all_summaries(),
                    workflow_config=workflow_config,
                ).to_agent_dict(),
                trace,
                push,
            )
            tool_agent_result = coerce_tool_plan(tool_agent_result)

            tool_result = None
            tool_name = tool_agent_result.get("tool_name", "")
            tool_params = tool_agent_result.get("tool_params", {})
            ctx.tool_params = tool_params
            if not tool_agent_result.get("skip") and tool_name:
                allowed_tool_names = tool_agent_result.get("available_tool_names") or available_tool_names
                is_valid_call, validation_message, normalized_params = tool_registry.validate_tool_call(
                    tool_name,
                    tool_params,
                    allowed_tool_names=allowed_tool_names,
                    allow_missing_required=True,
                )
                if not is_valid_call:
                    failure_reason = validation_message
                    next_verify = {
                        **verify_result,
                        "checks": [
                            *verify_result.get("checks", []),
                            {
                                "label": f"工具调用校验失败: {tool_name}",
                                "status": "已拦截",
                            },
                        ],
                        "risk_decision": failure_reason,
                        "can_auto_proceed": False,
                        "needs_more_info": False,
                    }
                    return await self._escalate(
                        ctx,
                        failure_reason,
                        verify_result=next_verify,
                        tool_request=tool_params,
                    )
                tool_name = tool_registry.resolve_tool_name(tool_name) or tool_name
                tool_params = normalized_params
                ctx.tool_params = tool_params
                missing_result = await self._handle_tool_missing_params(
                    ctx,
                    tool_name,
                    tool_params,
                )
                if missing_result:
                    return missing_result

                logger.info("[Orchestrator] Executing tool: %s", tool_name)
                tool_result = await mock_executor.execute(tool_name, tool_params)
                ctx.tool_result = tool_result
                await self._persist_tool_call(ticket.id, tool_name, tool_params, tool_result)

                verify_result = await self._run_escalation_step(
                    ticket,
                    intent_result,
                    extract_result,
                    workflow_config,
                    trace,
                    push,
                    tool_result=tool_result,
                )
                ctx.verify_result = verify_result

                if not tool_result.success or not verify_result.get("can_auto_proceed", True):
                    failure_reason = (
                        verify_result.get("risk_decision")
                        or tool_result.failure_reason
                        or tool_result.message
                        or "工具调用需要人工处理"
                    )
                    return await self._escalate(
                        ctx,
                        failure_reason,
                        tool_result=tool_result,
                        tool_request=tool_params,
                    )

            return await self._finish_review(ctx, tool_result=tool_result, tool_request=tool_params)

        except Exception as exc:
            logger.exception("[Orchestrator] Workflow failed for ticket %s", ticket_id)
            return await self._fail(ctx, str(exc))

    @staticmethod
    def _build_ticket_context(ticket: Ticket) -> str:
        """Include structured ticket fields so agents do not rely on prose only."""
        return TicketContext.from_ticket(ticket).to_summary_text()

    @staticmethod
    def _ticket_payload(ticket: Ticket) -> dict:
        """Return structured ticket context for downstream agents."""
        return TicketContext.from_ticket(ticket).to_resolution_ticket()

    async def _run_field_enrichment(
        self,
        ticket: Ticket,
        intent_result: dict,
        extract_result: dict,
        workflow_config: dict,
        trace: TraceCollector,
        push,
    ):
        scenario = workflow_scenario(workflow_config, intent_result.get("type", "UNKNOWN"))
        tool_name = scenario.recommended_tool
        if not tool_name:
            return
        enrich = getattr(mock_executor, "enrich_params", None)
        if not callable(enrich):
            return
        params = {
            field.get("name"): field.get("value")
            for field in extract_result.get("fields", [])
        }
        enriched_params, enrichment_result = await enrich(tool_name, params, ticket)
        if not enrichment_result.get("filledFields"):
            return

        field_by_name = {field.get("name"): field for field in extract_result.get("fields", [])}
        for name, value in enrichment_result["filledFields"].items():
            if name in field_by_name:
                field_by_name[name]["value"] = str(value)
            else:
                extract_result.setdefault("fields", []).append({
                    "label": name,
                    "name": name,
                    "value": str(value),
                })
        extract_result["_field_enrichment"] = enrichment_result
        if push:
            await push("agent_complete", {
                "agent_id": "field_enrichment",
                "summary": f"Filled {len(enrichment_result['filledFields'])} field(s)",
                "duration_ms": 0,
                "status": TraceStatus.SUCCESS.value,
                "result": enrichment_result,
            })
        trace.add_step(
            agent="Field Enrichment / 字段补全",
            agent_id="field_enrichment",
            summary=(
                "Filled "
                f"{len(enrichment_result.get('filledFields', {}))} field(s) via "
                f"{', '.join(enrichment_result.get('sourceTools', []))}"
            ),
            duration="0ms",
            status=TraceStatus.SUCCESS,
        )

    async def _run_escalation_step(
        self,
        ticket: Ticket,
        intent_result: dict,
        extract_result: dict,
        workflow_config: dict,
        trace: TraceCollector,
        push,
        *,
        tool_result=None,
    ) -> dict:
        tool_payload = tool_result.model_dump() if hasattr(tool_result, "model_dump") else tool_result
        result = await self._run_agent_step(
            "escalation_agent",
            "Escalation Agent / 升级与兜底",
            self.escalation_agent,
            EscalationInput(
                ticket=TicketContext.from_ticket(ticket).to_risk_ticket(),
                intent=intent_result,
                fields=extract_result.get("fields", []),
                tool_result=tool_payload,
                workflow_config=workflow_config,
            ).to_agent_dict(),
            trace,
            push,
        )
        return coerce_risk_decision(result)

    async def _pause(
        self,
        ctx: PipelineContext,
        *,
        status: str,
        reason: str = "",
        pause_type: str | None = None,
        missing_fields: list[str] | None = None,
        tool_request: dict | None = None,
    ) -> dict:
        if ctx.ticket is None:
            return await self._fail(ctx, "PipelineContext missing ticket")
        return await self._complete_with_notification(
            ticket=ctx.ticket,
            intent_result=ctx.intent_result,
            extract_result=ctx.extract_result,
            tool_result=ctx.tool_result,
            verify_result=ctx.verify_result,
            workflow_config=ctx.workflow_config,
            trace=ctx.trace,
            total_start=ctx.overall_start,
            push=ctx.push,
            status=status,
            tool_request=tool_request,
            missing_fields=missing_fields,
            failure_reason=reason,
            pause_type=pause_type,
        )

    async def _escalate(
        self,
        ctx: PipelineContext,
        reason: str,
        *,
        verify_result: dict | None = None,
        tool_result=None,
        tool_request: dict | None = None,
        emit_terminal: bool = True,
    ) -> dict:
        verify_result = verify_result or ctx.verify_result
        ctx.verify_result = verify_result
        ctx.tool_result = tool_result
        if ctx.ticket is None:
            return await self._fail(ctx, "PipelineContext missing ticket")
        return await self._complete_with_notification(
            ticket=ctx.ticket,
            intent_result=ctx.intent_result,
            extract_result=ctx.extract_result,
            tool_result=tool_result,
            verify_result=verify_result,
            workflow_config=ctx.workflow_config,
            trace=ctx.trace,
            total_start=ctx.overall_start,
            push=ctx.push,
            status=TicketState.ESCALATED.value,
            tool_request=tool_request,
            failure_reason=reason,
            emit_terminal=emit_terminal,
        )

    async def _finish_review(
        self,
        ctx: PipelineContext,
        *,
        tool_result=None,
        tool_request: dict | None = None,
    ) -> dict:
        ctx.tool_result = tool_result
        if ctx.ticket is None:
            return await self._fail(ctx, "PipelineContext missing ticket")
        return await self._complete_with_notification(
            ticket=ctx.ticket,
            intent_result=ctx.intent_result,
            extract_result=ctx.extract_result,
            tool_result=tool_result,
            verify_result=ctx.verify_result,
            workflow_config=ctx.workflow_config,
            trace=ctx.trace,
            total_start=ctx.overall_start,
            push=ctx.push,
            status=TicketState.PENDING_HUMAN_REVIEW.value,
            tool_request=tool_request,
        )

    async def _fail(self, ctx: PipelineContext, error: str) -> dict:
        result = self._error_result(error, ctx.trace, ctx.overall_start)
        if ctx.ticket is None:
            ctx.ticket = await self._load_ticket(ctx.ticket_id)
        if ctx.ticket is not None:
            await self._set_ticket_status(ctx.ticket, TicketState.FAILED.value)
        await self._emit_terminal(ctx.push, ctx.ticket_id, result)
        return result

    async def _maybe_stop_before_resolution(
        self,
        ctx: PipelineContext,
    ) -> dict | None:
        verify_result = ctx.verify_result
        if verify_result.get("needs_more_info"):
            return await self._pause(
                ctx,
                status=TicketState.PENDING_INFO.value,
                missing_fields=verify_result.get("missing_fields", []),
                reason=verify_result.get("risk_decision", ""),
                pause_type="missing_info",
            )

        risk_level = verify_result.get("risk_level", "low")
        can_auto = verify_result.get("can_auto_proceed", True)

        if not can_auto:
            failure_reason = verify_result.get("risk_decision", "需要人工处理")
            return await self._escalate(ctx, failure_reason, verify_result=verify_result)

        if risk_level == "medium" and not ctx.confirmed:
            return await self._pause(
                ctx,
                status=TicketState.PENDING_HUMAN_CONFIRM.value,
                pause_type="human_confirm",
            )

        return None

    async def _handle_tool_missing_params(
        self,
        ctx: PipelineContext,
        tool_name: str,
        tool_params: dict,
    ) -> dict | None:
        if ctx.ticket is None:
            return await self._fail(ctx, "PipelineContext missing ticket")
        ticket = ctx.ticket
        extract_result = ctx.extract_result
        verify_result = ctx.verify_result
        missing_params = tool_registry.get_missing_required_params(tool_name, tool_params)
        if missing_params:
            enrich = getattr(mock_executor, "enrich_params", None)
            if callable(enrich):
                enriched_params, enrichment_result = await enrich(tool_name, tool_params, ticket)
            else:
                enriched_params, enrichment_result = tool_params, {}
            if enrichment_result.get("filledFields"):
                tool_params.clear()
                tool_params.update(enriched_params)
                extract_result["_field_enrichment"] = enrichment_result
                ctx.trace.add_step(
                    agent="Field Enrichment / 字段补全",
                    agent_id="field_enrichment",
                    summary=(
                        "Filled "
                        f"{len(enrichment_result.get('filledFields', {}))} field(s) via "
                        f"{', '.join(enrichment_result.get('sourceTools', []))}"
                    ),
                    duration="0ms",
                    status=TraceStatus.SUCCESS,
                )
                missing_params = tool_registry.get_missing_required_params(tool_name, tool_params)
        if not missing_params:
            return None

        missing_fields = [item["name"] for item in missing_params]
        follow_up_builder = getattr(self.intake_agent, "build_follow_up_prompt", None)
        if callable(follow_up_builder):
            follow_up = follow_up_builder(missing_params)
        else:
            details = [
                item.get("description") or item.get("name")
                for item in missing_params
            ]
            follow_up = "为继续办理该工单，请补充以下信息：" + "、".join(details)
        next_verify = {
            **verify_result,
            "checks": [
                *verify_result.get("checks", []),
                {
                    "label": f"工具参数缺失: {', '.join(missing_fields)}",
                    "status": "待补充",
                },
            ],
            "risk_decision": "工具执行参数不足，需要回到接单环节补充信息",
            "missing_fields": missing_fields,
            "needs_more_info": True,
            "can_auto_proceed": False,
        }
        reply_result = await self._run_notification_step(
            ticket,
            ctx.intent_result,
            extract_result,
            None,
            next_verify,
            ctx.workflow_config,
            ctx.trace,
            ctx.push,
            status=TicketState.PENDING_INFO.value,
            tool_request=tool_params,
            missing_fields=missing_fields,
            failure_reason=next_verify["risk_decision"],
            pause_type="missing_info",
        )
        ctx.verify_result = next_verify
        return await self._complete_with_notification(
            ticket=ticket,
            intent_result=ctx.intent_result,
            extract_result=extract_result,
            tool_result=None,
            verify_result=next_verify,
            workflow_config=ctx.workflow_config,
            trace=ctx.trace,
            total_start=ctx.overall_start,
            push=ctx.push,
            status=TicketState.PENDING_INFO.value,
            tool_request=tool_params,
            missing_fields=missing_fields,
            failure_reason=next_verify["risk_decision"],
            pause_type="missing_info",
            reply_result=reply_result,
            fallback_reply=follow_up,
        )

    async def _handle_high_risk(
        self,
        ctx: PipelineContext,
    ) -> dict:
        if ctx.ticket is None:
            return await self._fail(ctx, "PipelineContext missing ticket")
        ticket = ctx.ticket
        ctx.trace.add_step(
            agent="Escalation Agent / 升级与兜底",
            agent_id="escalation_agent",
            summary="高风险工单，跳过自动处理并升级人工",
            duration="0ms",
            status=TraceStatus.SKIPPED,
        )
        verify_result = {
            "risk_decision": "高风险工单，已转人工审核",
            "risk_level": "high",
            "can_auto_proceed": False,
            "missing_fields": [],
            "needs_more_info": False,
            "checks": [
                {"label": "自动处理", "status": "已拦截"},
                {"label": "风险等级", "status": "需复核"},
            ],
        }
        intent_result = {
            "type": "HIGH_RISK",
            "label": ticket.scene or "高风险工单",
            "confidence": 1.0,
            "workflow_name": "manual_escalation_flow",
            "reason": ticket.risk_label,
        }
        ctx.intent_result = intent_result
        ctx.extract_result = {}
        ctx.verify_result = verify_result
        return await self._escalate(
            ctx,
            "高风险工单，已转人工审核",
            verify_result=verify_result,
            emit_terminal=False,
        )

    async def _complete_with_notification(
        self,
        *,
        ticket: Ticket,
        intent_result: dict,
        extract_result: dict,
        tool_result,
        verify_result: dict,
        workflow_config: dict,
        trace: TraceCollector,
        total_start: float,
        push,
        status: str,
        tool_request: dict | None = None,
        missing_fields: list[str] | None = None,
        failure_reason: str = "",
        pause_type: str | None = None,
        reply_result: dict | None = None,
        fallback_reply: str = "",
        emit_terminal: bool = True,
    ) -> dict:
        """Build notification/result, update status, and optionally emit terminal SSE."""
        tool_payload = tool_result.model_dump() if hasattr(tool_result, "model_dump") else tool_result
        if reply_result is None:
            reply_result = await self._run_notification_step(
                ticket,
                intent_result,
                extract_result,
                tool_payload,
                verify_result,
                workflow_config,
                trace,
                push,
                status=status,
                tool_request=tool_request,
                missing_fields=missing_fields,
                failure_reason=failure_reason,
                pause_type=pause_type,
            )
        result = self._build_result(
            ticket,
            intent_result,
            extract_result,
            tool_result,
            verify_result,
            reply_result.get("reply_draft", fallback_reply),
            status=status,
            total_start=total_start,
            tool_request=tool_request,
            missing_fields=missing_fields,
            failure_reason=failure_reason,
            pause_type=pause_type,
            notification=reply_result.get("notification"),
        )
        await self._set_ticket_status(ticket, status)
        if emit_terminal:
            await self._emit_terminal(push, ticket.id, result)
        return result

    async def _load_ticket(self, ticket_id: str) -> Optional[Ticket]:
        row = await ticket_repository.get_ticket(ticket_id)
        if row is None:
            return None
        return Ticket(
            id=row["id"],
            no=row["no"],
            title=row["title"],
            customer_id=row.get("customer_id") or "",
            customer_name=row["customer_name"],
            phone=row["phone"],
            card_last4=row["card_last4"],
            scene=row["scene"],
            category=row.get("category") or "",
            subcategory=row.get("subcategory") or "",
            priority=row.get("priority") or "normal",
            channel=row.get("channel") or "",
            assignee=row.get("assignee") or "",
            department=row.get("department") or "",
            created_at=row["created_at"],
            due_at=row.get("due_at") or "",
            updated_at=row.get("updated_at") or "",
            risk_label=row["risk_label"],
            risk_level=row["risk_level"],
            status=TicketStatus(row["status"]),
            content=row["content"],
            closed_at=row.get("closed_at") or "",
            final_reply=row.get("final_reply") or "",
            cancel_reason=row.get("cancel_reason") or "",
        )

    async def _set_ticket_status(self, ticket: Ticket, next_status: str):
        current_status = ticket.status.value if hasattr(ticket.status, "value") else str(ticket.status)
        if not TicketStateMachine.can_transition(current_status, next_status):
            logger.warning(
                "Skipping invalid status transition for %s: %s -> %s",
                ticket.id,
                current_status,
                next_status,
            )
            return
        await ticket_repository.update_status(ticket.id, next_status)
        ticket.status = TicketStatus(next_status)

    async def _run_notification_step(
        self,
        ticket: Ticket,
        intent_result: dict,
        extract_result: dict,
        tool_result: dict | None,
        verify_result: dict,
        workflow_config: dict,
        trace: TraceCollector,
        push,
        *,
        status: str,
        tool_request: dict | None = None,
        missing_fields: list[str] | None = None,
        failure_reason: str = "",
        pause_type: str | None = None,
    ) -> dict:
        return await self._run_agent_step(
            "notification_agent",
            "Notification Agent / 通知与回访",
            self.notification_agent,
            NotificationInput(
                ticket=TicketContext.from_ticket(ticket).to_notification_ticket(),
                intent=intent_result,
                fields=extract_result.get("fields", []),
                tool_result=tool_result,
                tool_request=tool_request or {},
                verify_result=verify_result,
                workflow_config=workflow_config,
                status=status,
                missing_fields=missing_fields or [],
                failure_reason=failure_reason,
                pause_type=pause_type,
            ).to_agent_dict(),
            trace,
            push,
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
        start = time.time()
        if push:
            await push("agent_start", {
                "agent_id": agent_id,
                "agent_name": agent_name,
                "timestamp": time.time(),
            })
            await push("agent_thinking", {
                "agent_id": agent_id,
                "message": f"正在执行{agent_name}...",
            })

        trace.add_step(
            agent=agent_name,
            agent_id=agent_id,
            summary="执行中...",
            duration="等待返回",
            status=TraceStatus.RUNNING,
        )

        try:
            agent_card = getattr(agent, "agent_card", None)
            if agent_card is not None:
                validate_agent_payload(
                    input_data,
                    agent_card.input_schema,
                    agent_id=agent_id,
                    direction="input",
                )
            result = await agent.run(input_data)
            if agent_card is not None:
                validate_agent_payload(
                    result,
                    agent_card.output_schema,
                    agent_id=agent_id,
                    direction="output",
                )
        except Exception as exc:
            elapsed_ms = int((time.time() - start) * 1000)
            summary = f"{agent_name}执行失败：{exc}"
            trace.update_last(summary, f"{elapsed_ms}ms", TraceStatus.FAILED)
            await self._record_agent_execution(
                trace,
                agent_id=agent_id,
                agent_name=agent_name,
                input_data=input_data,
                output_data={},
                error_message=str(exc),
                status=TraceStatus.FAILED.value,
                duration_ms=elapsed_ms,
            )
            if push:
                await push("agent_complete", {
                    "agent_id": agent_id,
                    "summary": summary,
                    "duration_ms": elapsed_ms,
                    "status": TraceStatus.FAILED.value,
                    "result": {"error": str(exc)},
                })
            raise

        elapsed_ms = int((time.time() - start) * 1000)
        summary = self._build_step_summary(agent_id, result)
        trace.update_last(summary, f"{elapsed_ms}ms", TraceStatus.SUCCESS)
        await self._record_agent_execution(
            trace,
            agent_id=agent_id,
            agent_name=agent_name,
            input_data=input_data,
            output_data=result,
            status=TraceStatus.SUCCESS.value,
            duration_ms=elapsed_ms,
        )

        if push:
            await push("agent_complete", {
                "agent_id": agent_id,
                "summary": summary,
                "duration_ms": elapsed_ms,
                "status": TraceStatus.SUCCESS.value,
                "result": result,
            })

        logger.info("[Orchestrator] %s completed in %sms", agent_name, elapsed_ms)
        return result

    async def _record_agent_execution(
        self,
        trace: TraceCollector,
        *,
        agent_id: str,
        agent_name: str,
        input_data: dict,
        output_data: dict,
        status: str,
        duration_ms: int,
        error_message: str = "",
    ):
        try:
            await agent_execution_log_repository.insert_agent_execution(
                ticket_id=trace.ticket_id,
                run_id=trace.run_id,
                agent_id=agent_id,
                agent_name=agent_name,
                input_data=input_data,
                output_data=output_data,
                error_message=error_message,
                status=status,
                duration_ms=duration_ms,
            )
        except Exception:
            logger.warning(
                "Failed to persist agent execution log for %s/%s",
                trace.ticket_id,
                agent_id,
                exc_info=True,
            )

    def _build_step_summary(self, agent_id: str, result: dict) -> str:
        if agent_id == "classifier_agent":
            return f"已识别为{result.get('label', '未知')}场景（置信度 {result.get('confidence', 0):.0%}）"
        if agent_id == "intake_agent":
            fields = result.get("fields", [])
            valid = [field for field in fields if field.get("value") not in {"", "未提取", "未提供", None}]
            return f"已提取 {len(valid)}/{len(fields)} 个有效字段"
        if agent_id == "resolution_agent":
            if result.get("skip"):
                return f"跳过工具调用: {result.get('skip_reason', '')}"
            return f"已选择工具: {result.get('tool_name', '无')}"
        if agent_id == "escalation_agent":
            return result.get("risk_decision", "校验完成")
        if agent_id == "notification_agent":
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
        *,
        tool_request: dict | None = None,
        missing_fields: list[str] | None = None,
        failure_reason: str = "",
        pause_type: str | None = None,
        notification: dict | None = None,
    ) -> dict:
        intent = IntentResult(
            type=intent_result.get("type", "UNKNOWN"),
            label=intent_result.get("label", "未知"),
            confidence=float(intent_result.get("confidence", 0.0) or 0.0),
            workflow_name=intent_result.get("workflow_name", ""),
            reason=intent_result.get("reason", ""),
        )

        fields = [FieldResult(**field) for field in extract_result.get("fields", [])]
        checks = [VerifyCheck(**check) for check in verify_result.get("checks", [])]
        enrichment_payload = extract_result.get("_field_enrichment")
        field_enrichment = (
            FieldEnrichmentResult(**enrichment_payload)
            if enrichment_payload
            else None
        )

        tool_evidence = ""
        tool_name = ""
        tool_response = {}
        if tool_result:
            tool_name = tool_result.tool_name
            tool_response = tool_result.model_dump(by_alias=True)
            if tool_result.success:
                tool_evidence = (
                    f"{tool_result.action or tool_result.tool_name}调用成功，"
                    f"证据编号 {tool_result.evidence_id}"
                )
            else:
                tool_evidence = f"{tool_result.tool_name}调用失败：{tool_result.message}"

        requires_human_review = status in {
            TicketState.PENDING_INFO.value,
            TicketState.PENDING_HUMAN_CONFIRM.value,
            TicketState.PENDING_HUMAN_REVIEW.value,
            TicketState.ESCALATED.value,
            TicketState.FAILED.value,
        }
        page_task = self._build_reply_page_task(
            ticket=ticket,
            intent=intent,
            status=status,
            verify_result=verify_result,
            reply_draft=reply_draft,
            tool_response=tool_response,
            field_enrichment=field_enrichment,
            missing_fields=missing_fields or [],
            failure_reason=failure_reason,
        )

        result = AiProcessResult(
            workflow_name=intent.workflow_name,
            risk_decision=verify_result.get("risk_decision", ""),
            intent=intent,
            fields=fields,
            tool_evidence=tool_evidence,
            tool_name=tool_name,
            tool_request=tool_request or {},
            tool_response=tool_response,
            field_enrichment=field_enrichment,
            verify_checks=checks,
            reply_draft=reply_draft,
            notification=notification,
            requires_human_review=requires_human_review,
            missing_fields=missing_fields or [],
            failure_reason=failure_reason,
            page_task=page_task,
        )

        total_ms = int((time.time() - total_start) * 1000)
        return {
            **result.model_dump(),
            "_status": status,
            "_total_duration_ms": total_ms,
            "_terminal_event": self._terminal_event(status),
            "_pause_type": pause_type,
            "_failure_reason": failure_reason,
        }

    @staticmethod
    def _build_reply_page_task(
        *,
        ticket: Ticket,
        intent: IntentResult,
        status: str,
        verify_result: dict,
        reply_draft: str,
        tool_response: dict,
        field_enrichment: FieldEnrichmentResult | None,
        missing_fields: list[str],
        failure_reason: str,
    ) -> PageTaskEnvelope:
        evidence_ids = []
        for value in [
            tool_response.get("evidenceId"),
            tool_response.get("evidence_id"),
            *(field_enrichment.evidence_ids if field_enrichment else []),
        ]:
            if value and value not in evidence_ids:
                evidence_ids.append(str(value))

        if status == TicketState.PENDING_HUMAN_REVIEW.value:
            mode = "auto"
            scene = "ticket-reply"
            stop_reason = ""
            final_action = PageTaskActionEnvelope(
                kind="scrollToRegion",
                target="enterprise-reply",
                label="进入回单复核区",
                required=True,
            )
        elif status == TicketState.PENDING_INFO.value:
            mode = "suggest"
            scene = "ticket-reply"
            stop_reason = "字段不足，需要客户或坐席补充信息"
            final_action = PageTaskActionEnvelope(
                kind="scrollToRegion",
                target="sunpilot-fields",
                label="定位缺失字段",
                required=True,
            )
        else:
            mode = "stop"
            scene = "human-confirm"
            stop_reason = failure_reason or verify_result.get("risk_decision", "需要人工处理")
            final_action = PageTaskActionEnvelope(
                kind="stopForHuman",
                target="human-confirm",
                label="停在人工处理节点",
                required=True,
            )

        actions = []
        if reply_draft:
            actions.append(PageTaskActionEnvelope(
                kind="fillTextarea",
                target="page-agent-reply-draft",
                label="填入客户回单",
                value=reply_draft,
                required=status == TicketState.PENDING_HUMAN_REVIEW.value,
            ))
        actions.extend(
            PageTaskActionEnvelope(
                kind="locateEvidence",
                target="sunpilot-evidence",
                label=f"定位证据 {evidence_id}",
                value=evidence_id,
            )
            for evidence_id in evidence_ids
        )
        actions.append(final_action)

        return PageTaskEnvelope(
            id=f"reply-{ticket.id}",
            source="ai_result",
            scene=scene,
            risk_level=verify_result.get("risk_level", ticket.risk_level or "low"),
            mode=mode,
            business_payload={
                "ticketId": ticket.id,
                "ticketNo": ticket.no,
                "workflowName": intent.workflow_name,
                "intent": intent.model_dump(by_alias=True),
                "riskDecision": verify_result.get("risk_decision", ""),
                "missingFields": missing_fields,
                "evidenceIds": evidence_ids,
                "replyDraft": reply_draft,
                "status": status,
            },
            actions=actions,
            allowed_targets=[
                "page-agent-reply-draft",
                "sunpilot-evidence",
                "sunpilot-fields",
                "enterprise-reply",
                "human-confirm",
            ],
            requires_human_before_submit=True,
            stop_reason=stop_reason,
        )

    def _error_result(self, message: str, trace: TraceCollector, total_start: float) -> dict:
        trace.add_step(
            agent="编排器",
            agent_id="orchestrator",
            summary=message,
            duration="0ms",
            status=TraceStatus.FAILED,
        )
        result = AiProcessResult(
            workflow_name="error_flow",
            risk_decision="流程执行失败",
            requires_human_review=True,
            failure_reason=message,
        )
        total_ms = int((time.time() - total_start) * 1000)
        return {
            **result.model_dump(),
            "_status": TicketState.FAILED.value,
            "_total_duration_ms": total_ms,
            "_terminal_event": "workflow_failed",
            "_pause_type": None,
            "_failure_reason": message,
        }

    async def _emit_terminal(self, push, ticket_id: str, result: dict):
        event = result.get("_terminal_event") or self._terminal_event(result.get("_status", ""))
        data = {
            "ticketId": ticket_id,
            "status": result.get("_status", ""),
            "totalDurationMs": result.get("_total_duration_ms", 0),
            "result": self.public_result(result),
        }
        if result.get("_pause_type"):
            data["pauseType"] = result["_pause_type"]
            data["pausedAt"] = "escalation_agent"
            data["reason"] = result.get("_failure_reason") or result.get("risk_decision", "")
        if result.get("_failure_reason"):
            data["failureReason"] = result["_failure_reason"]
        await push(event, data)

    async def _persist_tool_call(self, ticket_id: str, tool_name: str, request: dict, tool_result):
        await tool_call_repository.insert_tool_call(ticket_id, tool_name, request, tool_result)

    @staticmethod
    def public_result(result: dict) -> dict:
        payload = {key: value for key, value in result.items() if not key.startswith("_")}
        return AiProcessResult(**payload).model_dump(by_alias=True)

    @staticmethod
    def _terminal_event(status: str) -> str:
        if status in {TicketState.PENDING_INFO.value, TicketState.PENDING_HUMAN_CONFIRM.value}:
            return "workflow_paused"
        if status == TicketState.ESCALATED.value:
            return "workflow_escalated"
        if status == TicketState.FAILED.value:
            return "workflow_failed"
        return "workflow_complete"


orchestrator = Orchestrator()
