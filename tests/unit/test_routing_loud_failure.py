"""routing.py under standard 0034 (ADR 0236), the #3585 sweep.

Ledger 0908 names one site in this module and judges it compliant: a file
path that is not a string raises TypeError, naming the type, before any seat
is chosen. It stays as it is; this pins it. The test name carries the
ledger's line number at its base ``79e18ad1``.
"""

from __future__ import annotations

import pytest

from assemblyzero.workflows.testing.nodes.implementation.routing import (
    CODE_SEAT,
    SMALL_SEAT,
    select_seat_for_file,
)


def test_62_a_path_that_is_not_a_string_raises_naming_its_type():
    with pytest.raises(TypeError, match="got NoneType"):
        select_seat_for_file(None)  # type: ignore[arg-type]


def test_the_seats_are_unchanged():
    assert select_seat_for_file("src/pkg/__init__.py") == SMALL_SEAT
    assert select_seat_for_file("src/pkg/widget.py") == CODE_SEAT
