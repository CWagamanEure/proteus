"""Core event and intent schemas shared by agents and mechanisms."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


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
    """Base event with required metadata."""

    event_id: str
    ts_ms: int
    event_type: EventType
    payload: dict[str, Any] = field(default_factory=dict)


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
