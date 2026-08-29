"""A stage print never dies on the text the stage exists to process (#2662).

boostgauge #379's first roll halted in the LLD stage three attempts out of
three, non-transient:

    LLD stage error: 'charmap' codec can't encode character '\\u2265' in
    position 239: character maps to <undefined>

N0c's model call completed (108.7s on the third attempt) and found conflicts.
The print of the finding killed the gate before the verdict rendered, so the
conflicts themselves are unknown -- the crash consumed the evidence it was
about to state. The sink is `analyze_requirements.py`'s

    print(f"          A: {c.get('criterion_a') or '(not stated)'}")

which emits the model's quoted criterion text verbatim, and #379's decision
table carries U+2265 in every assertion cell.

Sixth kill in one class -- #161, #1163, #1493, #1876, #2367 -- each repaired at
the sink, each outlived by the class, because any NEW print of issue text,
contract text or model output re-creates it. Moving exactly that text is the
pipeline's whole job.

## Why these tests spawn real processes

The defect lives in the boundary between two processes: the launcher redirects
the child's stdout straight to a file handle, and the child owns the encoding
of what lands there. Nothing in-process reproduces that -- `capsys` hands back
`str`, and a `StringIO` has no encoding at all. So every test here runs a real
interpreter with a real redirect and reads the resulting BYTES.

`PYTHONIOENCODING=cp1252` stands in for the Windows locale, which makes the
reproduction deterministic on any host: CI runs Linux, where the ambient
locale is UTF-8 and the defect cannot occur by accident.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

#: U+2265 as it lands in a UTF-8 file. The assertion is on bytes, not on a
#: decoded str: `errors="replace"` anywhere in the chain would still decode to
#: SOMETHING, and a replaced character inside a quoted conflict criterion
#: silently corrupts the evidence an operator rules on.
GE_UTF8 = b"\xe2\x89\xa5"

#: A stage print in the shape N0c uses for a conflict it found.
STAGE_PRINT = (
    'print("          A: the strip step is \\u2265 200 across the horizon")\n'
    'print("OK")\n'
)


def _run_child(tmp_path: Path, script: str, env_extra: dict[str, str]) -> bytes:
    """Run a child exactly as the launcher does: stdout straight to a file.

    `subprocess.Popen(..., stdout=fh)` hands the child a file descriptor, so
    the parent's `encoding=` on that handle governs nothing about what the
    child writes -- which is why boostgauge #379's log carries a raw cp1252
    em-dash (0x97) inside a file the launcher opened as UTF-8.
    """
    child = tmp_path / "child.py"
    child.write_text(script, encoding="utf-8")
    log = tmp_path / "out.log"

    env = dict(os.environ)
    env.pop("PYTHONUTF8", None)
    env.pop("PYTHONIOENCODING", None)
    env.update(env_extra)

    with log.open("wb") as fh:
        proc = subprocess.Popen(
            [sys.executable, str(child)], stdout=fh,
            stderr=subprocess.STDOUT, env=env, cwd=str(tmp_path),
        )
        proc.wait()
    return log.read_bytes()


INSTALL_PREAMBLE = (
    "import sys\n"
    f"sys.path.insert(0, {str(ROOT)!r})\n"
    "from assemblyzero.core.utf8_console import install\n"
    "install()\n"
)


class TestTheKillReproduces:
    """The defect, before anything is claimed about the fix."""

    def test_a_cp1252_child_dies_printing_u2265(self, tmp_path):
        raw = _run_child(tmp_path, STAGE_PRINT, {"PYTHONIOENCODING": "cp1252"})

        assert b"UnicodeEncodeError" in raw
        assert b"charmap" in raw
        assert b"can't encode character" in raw
        assert b"OK" not in raw, "the print after it never ran"

    def test_cp1252_can_encode_the_characters_331_was_dense_in(self, tmp_path):
        """Why twenty-four rolls of #331 never hit this.

        cp1252 HAS the degree sign, the multiplication sign and the section
        sign -- the symbols dominating #331's geometry rows. It does not have
        U+2265, and #379's table is unusually dense in it. The latent defect
        predates #379; #379's character mix is the first to fire it.
        """
        script = 'print("\\u00b0 \\u00d7 \\u00a7")\nprint("OK")\n'
        raw = _run_child(tmp_path, script, {"PYTHONIOENCODING": "cp1252"})

        assert b"UnicodeEncodeError" not in raw
        assert b"OK" in raw


class TestTheReconfigureHalf:
    """`utf8_console.install()` at the orchestrator entry point."""

    def test_it_survives_the_print(self, tmp_path):
        raw = _run_child(
            tmp_path, INSTALL_PREAMBLE + STAGE_PRINT,
            {"PYTHONIOENCODING": "cp1252"},
        )

        assert b"UnicodeEncodeError" not in raw
        assert b"OK" in raw

    def test_the_character_lands_as_real_utf8(self, tmp_path):
        """Not `errors="replace"`. The log is UTF-8-capable and a replaced
        character in a quoted criterion corrupts what the operator rules on."""
        raw = _run_child(
            tmp_path, INSTALL_PREAMBLE + STAGE_PRINT,
            {"PYTHONIOENCODING": "cp1252"},
        )

        assert GE_UTF8 in raw
        assert b"?" not in raw
        assert "\ufffd".encode() not in raw

    def test_it_beats_pythonioencoding(self, tmp_path):
        """The reason this half is load-bearing rather than redundant.

        A stream reconfigure is the last word; the env var is not.
        """
        raw = _run_child(
            tmp_path, INSTALL_PREAMBLE + STAGE_PRINT,
            {"PYTHONIOENCODING": "cp1252", "PYTHONUTF8": "1"},
        )

        assert GE_UTF8 in raw


class TestTheEnvironmentHalf:
    """`PYTHONUTF8=1` in the launcher's child environment."""

    def test_it_survives_the_print(self, tmp_path):
        raw = _run_child(tmp_path, STAGE_PRINT, {"PYTHONUTF8": "1"})

        assert b"UnicodeEncodeError" not in raw
        assert GE_UTF8 in raw

    def test_pythonioencoding_defeats_it(self, tmp_path):
        """Measured, and the reason both halves ship.

        UTF-8 mode loses to PYTHONIOENCODING for stdio -- identical crash,
        identical position. `_child_env` builds on `dict(os.environ)`, so
        whatever the launcher inherits travels down, and a wrapper in this
        fleet is documented to set exactly this variable (dependabot_review's
        note on #2156).
        """
        raw = _run_child(
            tmp_path, STAGE_PRINT,
            {"PYTHONIOENCODING": "cp1252", "PYTHONUTF8": "1"},
        )

        assert b"UnicodeEncodeError" in raw

    def test_it_reaches_default_encoding_file_writes(self, tmp_path):
        """The half the reconfigure cannot cover, and the half every prior
        per-sink print repair never touched. The pipeline writes LLD and spec
        artifacts through exactly this path."""
        script = (
            "from pathlib import Path\n"
            "import sys\n"
            "Path(sys.argv[0]).with_name('written.txt')"
            ".write_text('step is \\u2265 200\\n')\n"
            "print('WROTE')\n"
        )
        raw = _run_child(tmp_path, script, {"PYTHONUTF8": "1"})

        assert b"WROTE" in raw
        assert GE_UTF8 in (tmp_path / "written.txt").read_bytes()

    def test_the_reconfigure_alone_does_not_reach_them(self, tmp_path):
        """Stated as a test so the two halves are never collapsed into one."""
        script = INSTALL_PREAMBLE + (
            "from pathlib import Path\n"
            "import sys\n"
            "try:\n"
            "    Path(sys.argv[0]).with_name('written.txt')"
            ".write_text('step is \\u2265 200\\n')\n"
            "    print('WROTE')\n"
            "except UnicodeEncodeError:\n"
            "    print('FAILED')\n"
        )
        raw = _run_child(tmp_path, script, {"PYTHONIOENCODING": "cp1252"})

        assert b"FAILED" in raw


class TestBothHalvesAreWired:
    """The entry points themselves, so a later edit cannot quietly drop one."""

    def test_the_launcher_sets_utf8_mode_for_the_child(self):
        import speedrun_roll

        assert speedrun_roll._child_env()["PYTHONUTF8"] == "1"

    def test_the_launcher_still_sets_what_it_set_before(self):
        env = __import__("speedrun_roll")._child_env()

        assert env["PYTHONUNBUFFERED"] == "1"
        assert env["CLAUDECODE"] == ""

    def test_the_orchestrator_entry_point_installs_the_reconfigure(self):
        source = (ROOT / "tools" / "orchestrate.py").read_text(encoding="utf-8")

        assert "utf8_console" in source
        assert "_install_utf8_console()" in source

    def test_it_installs_before_the_workflow_imports(self):
        """Before anything can print, the way no_console lands before anything
        can spawn."""
        source = (ROOT / "tools" / "orchestrate.py").read_text(encoding="utf-8")

        assert source.index("_install_utf8_console()") < source.index(
            "from assemblyzero.workflows.orchestrator.graph import"
        )


class TestTheStageThatDied:
    """The real print, driven with the real text shape."""

    @pytest.mark.parametrize("criterion", [
        "channel mean \u2265 100 at each tick midpoint",
        "samples at t=0.485 and t=0.500 differ by \u2265 200",
        "a 1-px transect contains \u2265 1 intermediate luminance",
    ])
    def test_a_quoted_criterion_survives_and_stays_intact(
        self, tmp_path, criterion
    ):
        script = INSTALL_PREAMBLE + (
            f'print("          A: {criterion}")\n'
            'print("OK")\n'
        )
        raw = _run_child(tmp_path, script, {"PYTHONIOENCODING": "cp1252"})

        assert b"UnicodeEncodeError" not in raw
        assert criterion.encode("utf-8") in raw
