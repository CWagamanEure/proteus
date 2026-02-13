from __future__ import annotations

from proteus.core.events import Event, EventType
from proteus.execution.latency import (
    ConfigurableLatencyModel,
    ConstantLatencyModel,
    LatencyProfile,
    build_default_latency_model,
)
from proteus.execution.leakage import (
    PublicTapeLeakagePolicy,
    build_default_leakage_policy,
    build_rfq_private_leakage_policy,
)


def test_constant_latency_model_includes_ack() -> None:
    model = ConstantLatencyModel(submission_ms=2, ack_ms=3, fill_ms=5)
    assert model.submission_delay_ms("clob") == 2
    assert model.ack_delay_ms("clob") == 3
    assert model.fill_delay_ms("clob") == 5


def test_configurable_latency_model_reproducible_with_seed() -> None:
    per = {
        "clob": LatencyProfile(submission_ms=1, ack_ms=2, fill_ms=3, jitter_ms=2),
    }
    a = ConfigurableLatencyModel(per_mechanism=per, seed=11)
    b = ConfigurableLatencyModel(per_mechanism=per, seed=11)

    draws_a = [
        (a.submission_delay_ms("clob"), a.ack_delay_ms("clob"), a.fill_delay_ms("clob"))
        for _ in range(6)
    ]
    draws_b = [
        (b.submission_delay_ms("clob"), b.ack_delay_ms("clob"), b.fill_delay_ms("clob"))
        for _ in range(6)
    ]
    assert draws_a == draws_b


def test_default_latency_model_parity_across_mechanisms() -> None:
    model = build_default_latency_model()
    clob = (
        model.submission_delay_ms("clob"),
        model.ack_delay_ms("clob"),
        model.fill_delay_ms("clob"),
    )
    fba = (
        model.submission_delay_ms("fba"),
        model.ack_delay_ms("fba"),
        model.fill_delay_ms("fba"),
    )
    rfq = (
        model.submission_delay_ms("rfq"),
        model.ack_delay_ms("rfq"),
        model.fill_delay_ms("rfq"),
    )
    assert clob == fba == rfq == (1, 1, 1)


def test_public_tape_policy_shows_full_payload() -> None:
    event = Event(
        event_id="e1",
        ts_ms=1,
        event_type=EventType.FILL,
        payload={"price": 0.5, "size": 2.0, "buy_agent_id": "a"},
    )
    policy = PublicTapeLeakagePolicy()
    assert policy.is_visible(event, "x", "clob")
    assert policy.visible_payload(event, "x", "clob") == event.payload


def test_default_leakage_policy_parity_across_mechanisms() -> None:
    event = Event(
        event_id="q1",
        ts_ms=3,
        event_type=EventType.RFQ_QUOTE,
        payload={
            "request_id": "r1",
            "price": 0.49,
            "dealer_id": "d1",
            "secret": "hidden",
        },
    )
    policy = build_default_leakage_policy()
    c = policy.visible_payload(event, "u1", "clob")
    f = policy.visible_payload(event, "u1", "fba")
    r = policy.visible_payload(event, "u1", "rfq")
    assert c == f == r == event.payload


def test_rfq_private_policy_filters_private_event_fields() -> None:
    event = Event(
        event_id="q2",
        ts_ms=4,
        event_type=EventType.RFQ_QUOTE,
        payload={
            "request_id": "r2",
            "price": 0.52,
            "ttl_ms": 250,
            "dealer_id": "dealer-1",
            "internal_score": 0.91,
        },
    )
    policy = build_rfq_private_leakage_policy()
    visible = policy.visible_payload(event, "observer", "rfq")
    assert "request_id" in visible
    assert "price" in visible
    assert "ttl_ms" in visible
    assert "dealer_id" in visible
    assert "internal_score" not in visible
