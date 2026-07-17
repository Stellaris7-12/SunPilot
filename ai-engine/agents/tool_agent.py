"""Compatibility shim for the former ToolCallingAgent name."""

from agents.resolution_agent import ResolutionAgent


class ToolCallingAgent(ResolutionAgent):
    """Backward-compatible alias for ResolutionAgent."""

