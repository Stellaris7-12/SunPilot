"""Compatibility shim for the former ReplyAgent name."""

from agents.notification_agent import NotificationAgent


class ReplyAgent(NotificationAgent):
    """Backward-compatible alias for NotificationAgent."""

