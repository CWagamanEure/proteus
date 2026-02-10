"""Core event and intent schemas shared by agents and mechanisms."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypeVar


class EventType(Enum):
    NEWS = "news"
    ORDER = "order"
    CANCEL = "cancel"
    QUOTE = "quote"
    FILL = "fill"
    BATCH_CLEAR = "batch_clear"
    RFQ_REQUEST = "rfq_request"
    RFQ_QUOTE = "rfq_quote"
    RFQ_ACCEPT = "rfq_accept"


class Side(Enum):
    BUY = "buy"
    SELL = "sell"


@dataclass(frozen=True)
class Event:
    """
    Base event with required metadata.

    Ordering policy:
    1. 'ts_ms' ascending (millisecond precision)
    2. 'seq_no' ascending (deterministic tie-break within same timestamp)
    3. 'event_id' ascending (final stable tie-break)
    """

    event_id: str
    ts_ms: int
    event_type: EventType
    payload: dict[str, Any] = field(default_factory=dict)
    seq_no: int = 0

    def __post_init__(self) -> None:
        if self.ts_ms < 0:
            raise ValueError("ts_ms must be non-negative")
        if self.seq_no < 0:
            raise ValueError("seq_no must be non-negative")


@dataclass(frozen=True)
class OrderIntent:
    """Agent order intent consumed by a mechanism."""

    intent_id: str
    agent_id: str
    ts_ms: int
    side: Side
    price: float
    size: float
    tif: str = "GTC"


@dataclass(frozen=True)
class CancelIntent:
    """Agent cancellation intent consumed by a mechanism."""

    intent_id: str
    agent_id: str
    ts_ms: int
    order_id: str


@dataclass(frozen=True)
class Fill:
    """Execution fill emitted by a mechanism."""

    fill_id: str
    ts_ms: int
    buy_agent_id: str
    sell_agent_id: str
    price: float
    size: float


def event_sort_key(event: Event) -> tuple[int, int, str]:
    """
    Event ordering key for deterministic replay.
    """
    return (event.ts_ms, event.seq_no, event.event_id)


StateT = TypeVar("StateT")


def replay_events(
    events: Iterable[Event],
    reducer: Callable[[StateT, Event], StateT],
    initial_state: StateT,
) -> StateT:
    """
    Rebuild state from an event log using deterministic ordering.
    """

    state = initial_state
    for event in sorted(events, key=event_sort_key):
        state = reducer(state, event)
    return state
