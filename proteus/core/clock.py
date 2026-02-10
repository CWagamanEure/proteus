"""Simulation clock primitives."""

from __future__ import annotations

import heapq
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace

from proteus.core.events import Event


class Clock(ABC):
    """Abstract simulation clock."""

    @property
    @abstractmethod
    def now_ms(self) -> int:
        """Current simulation time in milliseconds."""

    @abstractmethod
    def advance(self, delta_ms: int) -> int:
        """Advance clock and return the new timestamp."""


class EventClock(Clock):
    """Minimal deterministic clock implementation."""

    def __init__(self) -> None:
        self._now_ms = 0

    @property
    def now_ms(self) -> int:
        return self._now_ms

    def advance(self, delta_ms: int) -> int:
        if delta_ms < 0:
            raise ValueError("delta_ms must be non-negative")
        self._now_ms += delta_ms
        return self._now_ms


@dataclass(order=True)
class _ScheduledEvent:
    """
    Heap item ordering policy:
    1. 'ts_ms'
    2. 'priority' (lower value wins)
    3. 'seq_no' (submission order tie_break)
    """

    ts_ms: int
    priority: int
    seq_no: int
    event: Event = field(compare=False)


class EventScheduler:
    """
    Deterministic event scheduler with tie-break policy.

    Timestamp precision is milliseconds
    """

    def __init__(self, start_ms: int = 0) -> None:
        if start_ms < 0:
            raise ValueError("start_ms must be non-negative")
        self._clock = EventClock()
        if start_ms:
            self._clock.advance(start_ms)
        self._queue: list[_ScheduledEvent] = []
        self._next_seq: int = 1

    @property
    def now_ms(self) -> int:
        return self._clock.now_ms

    def schedule(self, event: Event, priority: int = 0) -> Event:
        if event.ts_ms < self.now_ms:
            raise ValueError("cannot schedule in the past")
        seq = self._next_seq
        self._next_seq += 1
        scheduled_event = replace(event, seq_no=seq)
        heapq.heappush(
            self._queue,
            _ScheduledEvent(
                ts_ms=scheduled_event.ts_ms,
                priority=priority,
                seq_no=seq,
                event=scheduled_event,
            ),
        )
        return scheduled_event

    def has_pending(self) -> bool:
        return bool(self._queue)

    def peek_next_ts(self) -> int | None:
        if not self._queue:
            return None
        return self._queue[0].ts_ms

    def pop_next(self) -> Event | None:
        if not self._queue:
            return None
        next = heapq.heappop(self._queue)
        self._clock.advance(next.ts_ms - self.now_ms)
        return next.event
