"""Ticket state machine."""

from enum import Enum
import logging

logger = logging.getLogger(__name__)


class TicketState(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    PENDING_INFO = "pending_info"
    PENDING_HUMAN_CONFIRM = "pending_human_confirm"
    PENDING_HUMAN_REVIEW = "pending_human_review"
    ESCALATED = "escalated"
    FAILED = "failed"
    CLOSED = "closed"


_TRANSITIONS: dict[TicketState, set[TicketState]] = {
    TicketState.OPEN: {
        TicketState.IN_PROGRESS,
        TicketState.PENDING_INFO,
        TicketState.PENDING_HUMAN_CONFIRM,
        TicketState.PENDING_HUMAN_REVIEW,
        TicketState.ESCALATED,
        TicketState.FAILED,
    },
    TicketState.IN_PROGRESS: {
        TicketState.PENDING_INFO,
        TicketState.PENDING_HUMAN_CONFIRM,
        TicketState.PENDING_HUMAN_REVIEW,
        TicketState.ESCALATED,
        TicketState.FAILED,
    },
    TicketState.PENDING_INFO: {
        TicketState.IN_PROGRESS,
        TicketState.ESCALATED,
        TicketState.CLOSED,
    },
    TicketState.PENDING_HUMAN_CONFIRM: {
        TicketState.IN_PROGRESS,
        TicketState.ESCALATED,
        TicketState.CLOSED,
    },
    TicketState.PENDING_HUMAN_REVIEW: {
        TicketState.IN_PROGRESS,
        TicketState.ESCALATED,
        TicketState.CLOSED,
    },
    TicketState.ESCALATED: {
        TicketState.IN_PROGRESS,
        TicketState.CLOSED,
    },
    TicketState.FAILED: {
        TicketState.IN_PROGRESS,
        TicketState.ESCALATED,
        TicketState.CLOSED,
    },
    TicketState.CLOSED: set(),
}


class TicketStateMachine:
    @classmethod
    def can_transition(cls, from_state: str, to_state: str) -> bool:
        if from_state == to_state:
            return True
        try:
            frm = TicketState(from_state)
            to = TicketState(to_state)
            return to in _TRANSITIONS.get(frm, set())
        except ValueError:
            return False

    @classmethod
    def transition(cls, ticket_id: str, from_state: str, to_state: str) -> str:
        if not cls.can_transition(from_state, to_state):
            raise ValueError(
                f"Invalid transition for ticket {ticket_id}: {from_state} -> {to_state}"
            )
        logger.info("[StateMachine] Ticket %s: %s -> %s", ticket_id, from_state, to_state)
        return to_state

    @classmethod
    def requires_human(cls, state: str) -> bool:
        return TicketState(state) in {
            TicketState.PENDING_INFO,
            TicketState.PENDING_HUMAN_CONFIRM,
            TicketState.PENDING_HUMAN_REVIEW,
            TicketState.ESCALATED,
            TicketState.FAILED,
        }
