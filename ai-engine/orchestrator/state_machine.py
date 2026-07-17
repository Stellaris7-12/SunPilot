"""Ticket state machine — defines valid states and transitions.

States:
    OPEN → IN_PROGRESS → PENDING_HUMAN_CONFIRM ⇄ IN_PROGRESS
                        → PENDING_HUMAN_REVIEW → CLOSED
                        → ESCALATED → CLOSED
"""

from enum import Enum
import logging

logger = logging.getLogger(__name__)


class TicketState(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    PENDING_HUMAN_CONFIRM = "pending_human_confirm"
    PENDING_HUMAN_REVIEW = "pending_human_review"
    ESCALATED = "escalated"
    CLOSED = "closed"


# Valid transitions: from_state → {to_states}
_TRANSITIONS: dict[TicketState, set[TicketState]] = {
    TicketState.OPEN: {
        TicketState.IN_PROGRESS,
    },
    TicketState.IN_PROGRESS: {
        TicketState.PENDING_HUMAN_CONFIRM,
        TicketState.PENDING_HUMAN_REVIEW,
        TicketState.ESCALATED,
    },
    TicketState.PENDING_HUMAN_CONFIRM: {
        TicketState.IN_PROGRESS,       # Resume after confirm
        TicketState.ESCALATED,         # Reject → escalate
    },
    TicketState.PENDING_HUMAN_REVIEW: {
        TicketState.CLOSED,            # Human approves
    },
    TicketState.ESCALATED: {
        TicketState.CLOSED,            # Human resolves escalated case
    },
    TicketState.CLOSED: set(),         # Terminal
}


class TicketStateMachine:
    """Validates and executes ticket state transitions."""

    @classmethod
    def can_transition(cls, from_state: str, to_state: str) -> bool:
        """Check if a transition is valid."""
        try:
            frm = TicketState(from_state)
            to = TicketState(to_state)
            return to in _TRANSITIONS.get(frm, set())
        except ValueError:
            return False

    @classmethod
    def transition(cls, ticket_id: str, from_state: str, to_state: str) -> str:
        """Validate and return the new state.

        Returns:
            The new state string if valid.

        Raises:
            ValueError: If the transition is not allowed.
        """
        if not cls.can_transition(from_state, to_state):
            raise ValueError(
                f"Invalid transition for ticket {ticket_id}: "
                f"{from_state} → {to_state}"
            )
        logger.info(
            f"[StateMachine] Ticket {ticket_id}: {from_state} → {to_state}"
        )
        return to_state

    @classmethod
    def requires_human(cls, state: str) -> bool:
        """Check if the current state requires human interaction."""
        return TicketState(state) in {
            TicketState.PENDING_HUMAN_CONFIRM,
            TicketState.PENDING_HUMAN_REVIEW,
            TicketState.ESCALATED,
        }
