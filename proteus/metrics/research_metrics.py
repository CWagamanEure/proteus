"""Stub research metrics for agent rationality analysis."""

from __future__ import annotations

from math import nan
from statistics import mean

from proteus.agents.base import AgentDecisionDiagnostic

RESEARCH_STUB_METRICS: tuple[str, ...] = (
    "agent_ev_alignment_mean_abs_error",
    "agent_belief_calibration_brier",
    "agent_ex_post_regret_mean",
)


def compute_research_stub_metrics(
    diagnostics: list[AgentDecisionDiagnostic],
) -> dict[str, float]:
    """
    Compute placeholder rationality metrics from diagnostic traces.

    These metrics are scaffolding only and are expected to be refined as
    strategy models become concrete in PT-008 and later analysis tickets.
    """

    out = {name: nan for name in RESEARCH_STUB_METRICS}
    if not diagnostics:
        return out

    ev_errors = [
        abs(row.expected_value - row.realized_value)
        for row in diagnostics
        if row.expected_value is not None and row.realized_value is not None
    ]
    if ev_errors:
        out["agent_ev_alignment_mean_abs_error"] = mean(ev_errors)

    brier_terms = [
        (row.belief - row.outcome) ** 2
        for row in diagnostics
        if row.belief is not None and row.outcome is not None
    ]
    if brier_terms:
        out["agent_belief_calibration_brier"] = mean(brier_terms)

    regrets = [
        max(0.0, row.realized_value - row.expected_value)
        for row in diagnostics
        if row.expected_value is not None and row.realized_value is not None
    ]
    if regrets:
        out["agent_ex_post_regret_mean"] = mean(regrets)

    return out
