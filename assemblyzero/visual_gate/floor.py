"""Palette separation-floor arithmetic (#2518 guardrail one).

The target contract's rule (boostgauge ruling #267 is the reference case): no
two palette entries sit closer than the floor in Euclidean RGB distance, so
anti-aliasing cannot flip a nearest-entry classification. A palette delta is
checked HERE, by computation, before any render -- never eyeballed.
"""

from __future__ import annotations

import math


def rgb_distance(a, b) -> float:
    """Euclidean distance in RGB space, the contract's own metric."""
    return math.sqrt(sum((int(a[k]) - int(b[k])) ** 2 for k in range(3)))


def floor_violations(
    candidate, palette: dict, floor: float, *, replacing: str | None = None
) -> list[str]:
    """Every palette entry the candidate would sit under-floor against.

    ``replacing`` names the entry the candidate substitutes, which is excluded
    from the check -- a colour is allowed to be near the value it replaces.
    Returns human-readable findings; empty means the delta clears the floor.
    """
    findings = []
    for name, rgb in palette.items():
        if replacing is not None and name == replacing:
            continue
        d = rgb_distance(candidate, rgb)
        if d < floor:
            findings.append(
                f"candidate {tuple(int(c) for c in candidate)} sits {d:.0f} "
                f"from palette entry '{name}' {tuple(int(c) for c in rgb)} -- "
                f"under the contract's separation floor of {floor:.0f}"
            )
    return findings
