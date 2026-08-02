"""The micro suite the launch health check times (#1920).

It is deliberately trivial and deliberately owned by the health check rather
than borrowed from the real suite. Two properties matter:

- **It must never fail for a code reason.** A canary that goes red when someone
  breaks an unrelated feature would block every roll on the fleet, so it asserts
  nothing about this project.
- **It must stay tiny and stable.** Its runtime IS the measurement. Adding work
  here silently moves the nominal for every machine.

What it actually measures is that this box can still spawn a process, import
pytest, collect, and finish. That is exactly what stopped working on
2026-07-29, when pytest died mid-suite and then stopped completing at all.
"""


def test_canary_arithmetic():
    assert sum(range(100)) == 4950


def test_canary_strings():
    assert "speedrun".upper() == "SPEEDRUN"


def test_canary_collections():
    assert sorted({3, 1, 2}) == [1, 2, 3]
