"""Central limit order book mechanism stub."""

from __future__ import annotations

from proteus.mechanisms.base import NullMechanism


class CLOBMechanism(NullMechanism):
    """Placeholder CLOB implementation for v1 scaffolding."""

    def __init__(self) -> None:
        super().__init__(name="clob")
