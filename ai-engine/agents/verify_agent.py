"""Compatibility shim for the former VerifyAgent name."""

from agents.escalation_agent import EscalationAgent


class VerifyAgent(EscalationAgent):
    """Backward-compatible alias for EscalationAgent."""

