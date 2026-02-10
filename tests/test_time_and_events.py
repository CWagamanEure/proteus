from proteus.core.clock import EventClock, EventScheduler
from proteus.core.events import Event, EventType, replay_events


def test_event_clock_rejects_negative_advance() -> None:
    clock = EventClock()
    try:
        clock.advance(-1)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_scheduler_orders_by_ts_priority_then_seq() -> None:
    scheduler = EventScheduler()

    e1 = scheduler.schedule(
        Event(event_id="a", ts_ms=10, event_type=EventType.ORDER),
        priority=1,
    )
    e2 = scheduler.schedule(
        Event(event_id="b", ts_ms=10, event_type=EventType.FILL),
        priority=0,
    )
    e3 = scheduler.schedule(
        Event(event_id="c", ts_ms=5, event_type=EventType.NEWS),
        priority=9,
    )
    e4 = scheduler.schedule(
        Event(event_id="d", ts_ms=10, event_type=EventType.CANCEL),
        priority=0,
    )

    # should be first c, then b+d (tiebreak), then a
    out = [
        scheduler.pop_next(),
        scheduler.pop_next(),
        scheduler.pop_next(),
        scheduler.pop_next(),
    ]
    assert [e.event_id for e in out if e is not None] == [
        e3.event_id,
        e2.event_id,
        e4.event_id,
        e1.event_id,
    ]
    assert out[0] is not None and out[1] is not None and out[2] is not None and out[3] is not None
    assert out[0].seq_no > 0 and out[1].seq_no > 0 and out[2].seq_no > 0 and out[3].seq_no > 0


def test_scheduler_cannot_schedule_in_the_past() -> None:
    scheduler = EventScheduler(start_ms=10)
    try:
        scheduler.schedule(Event(event_id="late", ts_ms=9, event_type=EventType.ORDER))
        assert False, "expected ValueError"

    except ValueError:
        pass


def test_replay_reconstructs_state_from_unordered_log() -> None:
    events = [
        Event(
            event_id="3",
            ts_ms=2,
            event_type=EventType.FILL,
            payload={"delta": -1},
            seq_no=2,
        ),
        Event(
            event_id="1",
            ts_ms=1,
            event_type=EventType.ORDER,
            payload={"delta": 5},
            seq_no=1,
        ),
        Event(
            event_id="2",
            ts_ms=2,
            event_type=EventType.FILL,
            payload={"delta": -2},
            seq_no=1,
        ),
    ]

    def reducer(state: int, event: Event) -> int:
        return state + int(event.payload.get("delta", 0))

    final_state = replay_events(events=events, reducer=reducer, initial_state=0)
    assert final_state == 2
