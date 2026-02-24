"""Mechanism parity preflight checks for cross-mechanism experiments."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from proteus.core.config import ScenarioConfig


def diff_scenario_parity_keys(
    reference: ScenarioConfig,
    candidate: ScenarioConfig,
) -> list[str]:
    """
    Return dotted config keys that violate the parity contract.

    Parity contract intentionally ignores:
    - scenario_id (metadata, often mechanism-specific)
    - mechanism.* (the treatment variable for parity comparisons)
    """

    ref_payload = _parity_payload(reference)
    cand_payload = _parity_payload(candidate)

    diffs: list[str] = []
    _diff_values(ref_payload, cand_payload, prefix="", out=diffs)
    return sorted(set(diffs))


def assert_scenario_parity(
    *,
    reference: ScenarioConfig,
    candidate: ScenarioConfig,
) -> None:
    """Raise with exact differing keys when parity is violated."""

    diffs = diff_scenario_parity_keys(reference, candidate)
    if not diffs:
        return

    ref_mech = reference.mechanism.name
    cand_mech = candidate.mechanism.name
    diff_keys = ", ".join(diffs)
    raise ValueError(
        "Mechanism parity preflight failed "
        f"(reference={reference.scenario_id}/{ref_mech}, "
        f"candidate={candidate.scenario_id}/{cand_mech}); "
        f"differing keys: {diff_keys}"
    )


def _parity_payload(scenario: ScenarioConfig) -> dict[str, Any]:
    payload = asdict(scenario)
    payload.pop("scenario_id", None)
    payload.pop("mechanism", None)
    return payload


def _diff_values(left: Any, right: Any, *, prefix: str, out: list[str]) -> None:
    if isinstance(left, dict) and isinstance(right, dict):
        keys = sorted(set(left.keys()) | set(right.keys()))
        for key in keys:
            next_prefix = f"{prefix}.{key}" if prefix else str(key)
            if key not in left or key not in right:
                out.append(next_prefix)
                continue
            _diff_values(left[key], right[key], prefix=next_prefix, out=out)
        return

    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            out.append(f"{prefix}.length" if prefix else "length")
        for idx, (lval, rval) in enumerate(zip(left, right)):
            next_prefix = f"{prefix}[{idx}]" if prefix else f"[{idx}]"
            _diff_values(lval, rval, prefix=next_prefix, out=out)
        if len(left) != len(right):
            longer_len = max(len(left), len(right))
            shorter_len = min(len(left), len(right))
            for idx in range(shorter_len, longer_len):
                out.append(f"{prefix}[{idx}]" if prefix else f"[{idx}]")
        return

    if left != right:
        out.append(prefix or "<root>")
