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
from models.ai_result import AiProcessResult, FieldEnrichmentResult, FieldResult, IntentResult, VerifyCheck
from models.repositories import ticket_repository, tool_call_repository
from models.ticket import RiskLevel, Ticket, TicketStatus
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

        try:
            workflow_config = load_workflow_config()
            ticket = await self._load_ticket(ticket_id)
            if ticket is None:
                result = self._error_result(f"Ticket {ticket_id} not found", trace, overall_start)
                await self._emit_terminal(push, ticket_id, result)
                return result

            await self._set_ticket_status(ticket, TicketState.IN_PROGRESS.value)

            if ticket.risk_level == RiskLevel.HIGH or ticket.risk_level == RiskLevel.HIGH.value:
                result = await self._handle_high_risk(
                    ticket,
                    trace,
                    overall_start,
                    workflow_config,
                    push,
                )
                await self._emit_terminal(push, ticket_id, result)
                return result

            ticket_context = self._build_ticket_context(ticket)
            intent_result = await self._run_agent_step(
                "classifier_agent",
                "Classifier Agent / 分类与优先级判定",
                self.classifier_agent,
                {
                    "ticket_content": ticket_context,
                    "workflow_config": workflow_config,
                },
                trace,
                push,
            )

            extract_result = await self._run_agent_step(
                "intake_agent",
                "Intake Agent / 接单与信息提取",
                self.intake_agent,
                {
                    "ticket_content": ticket_context,
                    "intent_type": intent_result.get("type", "UNKNOWN"),
                    "intent_label": intent_result.get("label", "未知"),
                    "workflow_config": workflow_config,
                },
                trace,
                push,
            )

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

            early_result = await self._maybe_stop_before_resolution(
                ticket,
                intent_result,
                extract_result,
                verify_result,
                workflow_config,
                trace,
                overall_start,
                confirmed,
                push,
            )
            if early_result:
                return early_result

            available_tool_names = [
                tool.name
                for tool in tool_registry.list_for_intent(
                    intent_result.get("type", "UNKNOWN"),
                    workflow_config,
                )
            ]
            tool_agent_result = await self._run_agent_step(
                "resolution_agent",
                "Resolution Agent / 解决方案与执行",
                self.resolution_agent,
                {
                    "intent": intent_result,
                    "fields": extract_result.get("fields", []),
                    "ticket_content": ticket_context,
                    "ticket": self._ticket_payload(ticket),
                    "available_tool_names": available_tool_names,
                    "available_tools": tool_registry.get_all_summaries(),
                    "workflow_config": workflow_config,
                },
                trace,
                push,
            )

            tool_result = None
            tool_name = tool_agent_result.get("tool_name", "")
            tool_params = tool_agent_result.get("tool_params", {})
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
                    reply_result = await self._run_notification_step(
                        ticket,
                        intent_result,
                        extract_result,
                        None,
                        next_verify,
                        workflow_config,
                        trace,
                        push,
                        status=TicketState.ESCALATED.value,
                        tool_request=tool_params,
                        failure_reason=failure_reason,
                    )
                    result = self._build_result(
                        ticket,
                        intent_result,
                        extract_result,
                        None,
                        next_verify,
                        reply_result.get("reply_draft", ""),
                        status=TicketState.ESCALATED.value,
                        total_start=overall_start,
                        tool_request=tool_params,
                        failure_reason=failure_reason,
                        notification=reply_result.get("notification"),
                    )
                    await self._set_ticket_status(ticket, TicketState.ESCALATED.value)
                    await self._emit_terminal(push, ticket_id, result)
                    return result
                tool_name = tool_registry.resolve_tool_name(tool_name) or tool_name
                tool_params = normalized_params
                missing_result = await self._handle_tool_missing_params(
                    ticket,
                    intent_result,
                    extract_result,
                    verify_result,
                    tool_name,
                    tool_params,
                    workflow_config,
                    trace,
                    overall_start,
                    push,
                )
                if missing_result:
                    return missing_result

                logger.info("[Orchestrator] Executing tool: %s", tool_name)
                tool_result = await mock_executor.execute(tool_name, tool_params)
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

                if not tool_result.success or not verify_result.get("can_auto_proceed", True):
                    failure_reason = (
                        verify_result.get("risk_decision")
                        or tool_result.failure_reason
                        or tool_result.message
                        or "工具调用需要人工处理"
                    )
                    reply_result = await self._run_notification_step(
                        ticket,
                        intent_result,
                        extract_result,
                        tool_result.model_dump(),
                        verify_result,
                        workflow_config,
                        trace,
                        push,
                        status=TicketState.ESCALATED.value,
                        tool_request=tool_params,
                        failure_reason=failure_reason,
                    )
                    result = self._build_result(
                        ticket,
                        intent_result,
                        extract_result,
                        tool_result,
                        verify_result,
                        reply_result.get("reply_draft", ""),
                        status=TicketState.ESCALATED.value,
                        total_start=overall_start,
                        tool_request=tool_params,
                        failure_reason=failure_reason,
                        notification=reply_result.get("notification"),
                    )
                    await self._set_ticket_status(ticket, TicketState.ESCALATED.value)
                    await self._emit_terminal(push, ticket_id, result)
                    return result

            reply_result = await self._run_notification_step(
                ticket,
                intent_result,
                extract_result,
                tool_result.model_dump() if tool_result else None,
                verify_result,
                workflow_config,
                trace,
                push,
                status=TicketState.PENDING_HUMAN_REVIEW.value,
                tool_request=tool_params,
            )

            result = self._build_result(
                ticket,
                intent_result,
                extract_result,
                tool_result,
                verify_result,
                reply_result.get("reply_draft", ""),
                status=TicketState.PENDING_HUMAN_REVIEW.value,
                total_start=overall_start,
                tool_request=tool_params,
                notification=reply_result.get("notification"),
            )
            await self._set_ticket_status(ticket, TicketState.PENDING_HUMAN_REVIEW.value)
            await self._emit_terminal(push, ticket_id, result)
            return result

        except Exception as exc:
            logger.exception("[Orchestrator] Workflow failed for ticket %s", ticket_id)
            result = self._error_result(str(exc), trace, overall_start)
            try:
                ticket = await self._load_ticket(ticket_id)
                if ticket is not None:
                    await self._set_ticket_status(ticket, TicketState.FAILED.value)
            finally:
                await self._emit_terminal(push, ticket_id, result)
            return result

    @staticmethod
    def _build_ticket_context(ticket: Ticket) -> str:
        """Include structured ticket fields so agents do not rely on prose only."""
        parts = [
            ("标题", ticket.title),
            ("场景", ticket.scene),
            ("类目", ticket.category),
            ("子类目", ticket.subcategory),
            ("客户号", ticket.customer_id),
            ("手机号", ticket.phone),
            ("卡尾号", ticket.card_last4),
            ("风险等级", ticket.risk_level),
            ("正文", ticket.content),
        ]
        return "\n".join(f"{label}: {value}" for label, value in parts if value)

    @staticmethod
    def _ticket_payload(ticket: Ticket) -> dict:
        """Return structured ticket context for downstream agents."""
        return {
            "id": ticket.id,
            "no": ticket.no,
            "title": ticket.title,
            "customerId": ticket.customer_id,
            "customerName": ticket.customer_name,
            "phone": ticket.phone,
            "cardLast4": ticket.card_last4,
            "scene": ticket.scene,
            "category": ticket.category,
            "subcategory": ticket.subcategory,
            "priority": ticket.priority,
            "channel": ticket.channel,
            "riskLabel": ticket.risk_label,
            "riskLevel": ticket.risk_level,
            "status": ticket.status.value if hasattr(ticket.status, "value") else str(ticket.status),
            "content": ticket.content,
        }

    async def _run_field_enrichment(
        self,
        ticket: Ticket,
        intent_result: dict,
        extract_result: dict,
        workflow_config: dict,
        trace: TraceCollector,
        push,
    ):
        scenario = workflow_config.get("scenarios", {}).get(intent_result.get("type", "UNKNOWN"), {})
        tool_name = scenario.get("recommended_tool", "")
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
        return await self._run_agent_step(
            "escalation_agent",
            "Escalation Agent / 升级与兜底",
            self.escalation_agent,
            {
                "ticket": {
                    "risk_level": ticket.risk_level,
                    "risk_label": ticket.risk_label,
                    "scene": ticket.scene,
                },
                "intent": intent_result,
                "fields": extract_result.get("fields", []),
                "tool_result": tool_result,
                "workflow_config": workflow_config,
            },
            trace,
            push,
        )

    async def _maybe_stop_before_resolution(
        self,
        ticket: Ticket,
        intent_result: dict,
        extract_result: dict,
        verify_result: dict,
        workflow_config: dict,
        trace: TraceCollector,
        overall_start: float,
        confirmed: bool,
        push,
    ) -> dict | None:
        if verify_result.get("needs_more_info"):
            reply_result = await self._run_notification_step(
                ticket,
                intent_result,
                extract_result,
                None,
                verify_result,
                workflow_config,
                trace,
                push,
                status=TicketState.PENDING_INFO.value,
                missing_fields=verify_result.get("missing_fields", []),
                failure_reason=verify_result.get("risk_decision", ""),
                pause_type="missing_info",
            )
            result = self._build_result(
                ticket,
                intent_result,
                extract_result,
                None,
                verify_result,
                reply_result.get("reply_draft", ""),
                status=TicketState.PENDING_INFO.value,
                total_start=overall_start,
                missing_fields=verify_result.get("missing_fields", []),
                failure_reason=verify_result.get("risk_decision", ""),
                pause_type="missing_info",
                notification=reply_result.get("notification"),
            )
            await self._set_ticket_status(ticket, TicketState.PENDING_INFO.value)
            await self._emit_terminal(push, ticket.id, result)
            return result

        risk_level = verify_result.get("risk_level", "low")
        can_auto = verify_result.get("can_auto_proceed", True)

        if not can_auto:
            failure_reason = verify_result.get("risk_decision", "需要人工处理")
            reply_result = await self._run_notification_step(
                ticket,
                intent_result,
                extract_result,
                None,
                verify_result,
                workflow_config,
                trace,
                push,
                status=TicketState.ESCALATED.value,
                failure_reason=failure_reason,
            )
            result = self._build_result(
                ticket,
                intent_result,
                extract_result,
                None,
                verify_result,
                reply_result.get("reply_draft", ""),
                status=TicketState.ESCALATED.value,
                total_start=overall_start,
                failure_reason=failure_reason,
                notification=reply_result.get("notification"),
            )
            await self._set_ticket_status(ticket, TicketState.ESCALATED.value)
            await self._emit_terminal(push, ticket.id, result)
            return result

        if risk_level == "medium" and not confirmed:
            reply_result = await self._run_notification_step(
                ticket,
                intent_result,
                extract_result,
                None,
                verify_result,
                workflow_config,
                trace,
                push,
                status=TicketState.PENDING_HUMAN_CONFIRM.value,
                pause_type="human_confirm",
            )
            result = self._build_result(
                ticket,
                intent_result,
                extract_result,
                None,
                verify_result,
                reply_result.get("reply_draft", ""),
                status=TicketState.PENDING_HUMAN_CONFIRM.value,
                total_start=overall_start,
                pause_type="human_confirm",
                notification=reply_result.get("notification"),
            )
            await self._set_ticket_status(ticket, TicketState.PENDING_HUMAN_CONFIRM.value)
            await self._emit_terminal(push, ticket.id, result)
            return result

        return None

    async def _handle_tool_missing_params(
        self,
        ticket: Ticket,
        intent_result: dict,
        extract_result: dict,
        verify_result: dict,
        tool_name: str,
        tool_params: dict,
        workflow_config: dict,
        trace: TraceCollector,
        overall_start: float,
        push,
    ) -> dict | None:
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
            intent_result,
            extract_result,
            None,
            next_verify,
            workflow_config,
            trace,
            push,
            status=TicketState.PENDING_INFO.value,
            tool_request=tool_params,
            missing_fields=missing_fields,
            failure_reason=next_verify["risk_decision"],
            pause_type="missing_info",
        )
        result = self._build_result(
            ticket,
            intent_result,
            extract_result,
            None,
            next_verify,
            reply_result.get("reply_draft", follow_up),
            status=TicketState.PENDING_INFO.value,
            total_start=overall_start,
            tool_request=tool_params,
            missing_fields=missing_fields,
            failure_reason=next_verify["risk_decision"],
            pause_type="missing_info",
            notification=reply_result.get("notification"),
        )
        await self._set_ticket_status(ticket, TicketState.PENDING_INFO.value)
        await self._emit_terminal(push, ticket.id, result)
        return result

    async def _handle_high_risk(
        self,
        ticket: Ticket,
        trace: TraceCollector,
        total_start: float,
        workflow_config: dict,
        push,
    ) -> dict:
        trace.add_step(
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
        reply_result = await self._run_notification_step(
            ticket,
            {
                "type": "HIGH_RISK",
                "label": ticket.scene or "高风险工单",
                "confidence": 1.0,
                "workflow_name": "manual_escalation_flow",
                "reason": ticket.risk_label,
            },
            {"fields": []},
            None,
            verify_result,
            workflow_config,
            trace,
            push,
            status=TicketState.ESCALATED.value,
            failure_reason="高风险工单，已转人工审核",
        )
        result = self._build_result(
            ticket,
            {
                "type": "HIGH_RISK",
                "label": ticket.scene or "高风险工单",
                "confidence": 1.0,
                "workflow_name": "manual_escalation_flow",
                "reason": ticket.risk_label,
            },
            {},
            None,
            verify_result,
            reply_result.get("reply_draft", ""),
            status=TicketState.ESCALATED.value,
            total_start=total_start,
            failure_reason="高风险工单，已转人工审核",
            notification=reply_result.get("notification"),
        )
        await self._set_ticket_status(ticket, TicketState.ESCALATED.value)
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
            {
                "ticket": {
                    "id": ticket.id,
                    "no": ticket.no,
                    "title": ticket.title,
                    "customer_name": ticket.customer_name,
                    "scene": ticket.scene,
                    "risk_level": ticket.risk_level,
                    "risk_label": ticket.risk_label,
                },
                "intent": intent_result,
                "fields": extract_result.get("fields", []),
                "tool_result": tool_result,
                "tool_request": tool_request or {},
                "verify_result": verify_result,
                "workflow_config": workflow_config,
                "status": status,
                "missing_fields": missing_fields or [],
                "failure_reason": failure_reason,
                "pause_type": pause_type,
            },
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
            result = await agent.run(input_data)
        except Exception as exc:
            elapsed_ms = int((time.time() - start) * 1000)
            summary = f"{agent_name}执行失败：{exc}"
            trace.update_last(summary, f"{elapsed_ms}ms", TraceStatus.FAILED)
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
