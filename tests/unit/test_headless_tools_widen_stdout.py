"""Every headless-print tool widens its stdout (#2673).

The cp1252 class was repaired sink-by-sink six times before #2662 made the
boundary systemic — and the launcher itself was the seventh kill: it installs
`no_console` (it spawns git/gh detached) but never installed `utf8_console`,
and its requirements-form echo prints raw issue text. boostgauge #384's `→`
killed the launch before the run log existed.

The invariant is mechanical: a tool that needs `no_console` runs headless and
prints reports, which is exactly the class that needs the widened stream. The
sweep matches the IMPORT, not the word — `speedrun_roll.py` carried the word
`utf8_console` in a comment for a month while its stdout stayed cp1252.
"""

from __future__ import annotations

from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2] / "tools"

NO_CONSOLE = "no_console import install"
UTF8_CONSOLE = "utf8_console import install"


def test_every_no_console_tool_also_widens_stdout() -> None:
    offenders: list[str] = []
    for tool in sorted(TOOLS.glob("*.py")):
        source = tool.read_text(encoding="utf-8", errors="replace")
        if NO_CONSOLE in source and UTF8_CONSOLE not in source:
            offenders.append(tool.name)
    assert not offenders, (
        f"tool(s) install no_console without utf8_console — headless print "
        f"tools crash on the first non-cp1252 character in the text they "
        f"echo (#2673): {offenders}"
    )


def test_the_sweep_sees_the_launcher() -> None:
    """The sweep's subject list must actually include the tool that motivated
    it — an empty glob or a moved directory would pass vacuously."""
    swept = {t.name for t in TOOLS.glob("*.py")}
    assert "speedrun_roll.py" in swept
    assert "orchestrate.py" in swept
