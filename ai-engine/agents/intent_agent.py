"""Compatibility shim for the former IntentAgent name."""

from agents.classifier_agent import ClassifierAgent


class IntentAgent(ClassifierAgent):
    """Backward-compatible alias for ClassifierAgent."""

