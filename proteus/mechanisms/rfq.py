"""Request-for-quote mechanism stub."""

from __future__ import annotations

from proteus.mechanisms.base import NullMechanism


class RFQMechanism(NullMechanism):
    """Placeholder RFQ implementation for v1 scaffolding."""

    def __init__(self) -> None:
        super().__init__(name="rfq")
