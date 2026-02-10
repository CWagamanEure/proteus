"""Dual-flow batch mechanism stub."""

from __future__ import annotations

from proteus.mechanisms.base import NullMechanism


class DualFlowFBAMechanism(NullMechanism):
    """Placeholder dual-flow FBA implementation for v1 scaffolding."""

    def __init__(self) -> None:
        super().__init__(name="dual_flow_fba")
