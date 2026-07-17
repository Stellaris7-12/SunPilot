"""Compatibility shim for the former ExtractAgent name."""

from agents.intake_agent import IntakeAgent


class ExtractAgent(IntakeAgent):
    """Backward-compatible alias for IntakeAgent."""

