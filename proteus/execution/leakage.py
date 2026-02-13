"""Information leakage policy interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from proteus.core.events import Event, EventType


class LeakagePolicy(ABC):
    """Defines visibility of events to each agent."""

    @abstractmethod
    def is_visible(self, event: Event, agent_id: str, mechanism_name: str = "clob") -> bool:
        """Return whether the agent can observe this event."""

    @abstractmethod
    def visible_payload(
        self,
        event: Event,
        agent_id: str,
        mechanism_name: str = "clob",
    ) -> dict[str, object]:
        """Return the payload fields visible to one agent"""


@dataclass(frozen=True)
class PublicTapeLeakagePolicy(LeakagePolicy):
    """Policy where all events and payload fields are visible to everyone."""

    def is_visible(self, event: Event, agent_id: str, mechanism_name: str = "clob") -> bool:
        _ = (event, agent_id, mechanism_name)
        return True

    def visible_payload(
        self,
        event: Event,
        agent_id: str,
        mechanism_name: str = "clob",
    ) -> dict[str, object]:
        _ = (agent_id, mechanism_name)
        return dict(event.payload)


@dataclass(frozen=True)
class MechanismLeakageSpec:
    """
    Per-mechanism leakage mapping.

    - public_event_types: full payload visible to all.
    - selective_payload_types: subset visible for private events.
    """

    public_event_types: frozenset[EventType] = field(default_factory=frozenset)
    selective_payload_fields: dict[EventType, frozenset[str]] = field(default_factory=dict)


class MechanismLeakagePolicy(LeakagePolicy):
    """
    Mechanism-specific visibility and field-level leakage policy
    """

    _PARTICIPANT_KEYS: tuple[str, ...] = (
        "agent_id",
        "buy_agent_id",
        "sell_agent_id",
        "requester_id",
        "dealer_id",
    )

    def __init__(
        self,
        *,
        default_spec: MechanismLeakageSpec | None = None,
        per_mechanism: dict[str, MechanismLeakageSpec] | None = None,
    ) -> None:
        self._default_spec = default_spec or MechanismLeakageSpec()
        self._per_mechanism = per_mechanism or {}

    def is_visible(self, event: Event, agent_id: str, mechanism_name: str = "clob") -> bool:
        spec = self._spec_for(mechanism_name)
        if event.event_type in spec.public_event_types:
            return True

        allowed_fields = spec.selective_payload_fields.get(event.event_type)
        if allowed_fields is None:
            return False

        return self._is_participant(event, agent_id) or len(allowed_fields) > 0

    def visible_payload(
        self,
        event: Event,
        agent_id: str,
        mechanism_name: str = "clob",
    ) -> dict[str, object]:
        if not self.is_visible(event, agent_id, mechanism_name):
            return {}

        spec = self._spec_for(mechanism_name)
        if event.event_type in spec.public_event_types:
            return dict(event.payload)

        allowed_fields = spec.selective_payload_fields.get(event.event_type, frozenset())
        visible: dict[str, object] = {}
        for key in allowed_fields:
            if key in event.payload:
                visible[key] = event.payload[key]
        return visible

    def _spec_for(self, mechanism_name: str) -> MechanismLeakageSpec:
        return self._per_mechanism.get(mechanism_name, self._default_spec)

    def _is_participant(self, event: Event, agent_id: str) -> bool:
        for key in self._PARTICIPANT_KEYS:
            if event.payload.get(key) == agent_id:
                return True
        return False


SUPPORTED_MECHANISMS: tuple[str, ...] = ("clob", "fba", "rfq")


def build_default_leakage_policy() -> MechanismLeakagePolicy:
    """
    Default parity policy: all mechanisms share fully public tape assumptions.
    """
    public_spec = MechanismLeakageSpec(public_event_types=frozenset(set(EventType)))
    per_mechanism = {name: public_spec for name in SUPPORTED_MECHANISMS}
    return MechanismLeakagePolicy(default_spec=public_spec, per_mechanism=per_mechanism)


def build_rfq_private_leakage_policy() -> MechanismLeakagePolicy:
    """
    Optional private RFQ for later sweeps:
    RFQ request/quote/accept expose only selected fields.
    """

    public_spec = MechanismLeakageSpec(public_event_types=frozenset(set(EventType)))

    rfq_spec = MechanismLeakageSpec(
        public_event_types=frozenset(
            {
                EventType.NEWS,
                EventType.ORDER,
                EventType.CANCEL,
                EventType.QUOTE,
                EventType.FILL,
                EventType.BATCH_CLEAR,
            }
        ),
        selective_payload_fields={
            EventType.RFQ_REQUEST: frozenset({"request_id", "side", "size", "symbol"}),
            EventType.RFQ_QUOTE: frozenset({"request_id", "price", "ttl_ms", "dealer_id"}),
            EventType.RFQ_ACCEPT: frozenset({"request_id", "accepted", "price"}),
        },
    )

    per_mechanism = {
        "clob": public_spec,
        "fba": public_spec,
        "rfq": rfq_spec,
    }
    return MechanismLeakagePolicy(default_spec=public_spec, per_mechanism=per_mechanism)
