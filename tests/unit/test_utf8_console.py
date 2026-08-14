"""The console never kills the checker that is using it (#2367).

`check_requirements_form.py` died with `UnicodeEncodeError` on a true minus
sign, U+2212, which the boostgauge aesthetic doc's binding angle formula
contains -- so the checker crashed on documents quoting the standard it
enforces. Under a pipe (every agent invocation, every CI step) Python encodes
stdout with the locale encoding, cp1252 on this fleet, and cp1252 has 256 code
points.

Every positive claim here has its falsifier beside it: each test that shows the
widened stream carrying a character is paired with proof that the same write
raises on the same stream unwidened. Without that pair the suite would pass just
as happily against a stream that was never narrow.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from assemblyzero.core import utf8_console  # noqa: E402

# The characters that actually shipped in the binding doc, plus a few from the
# same family. None of them exist in cp1252.
MINUS = "−"
HARD = MINUS + "≡θ→\U0001f600"


def cp1252_stream() -> io.TextIOWrapper:
    """A stdout as narrow as the one the operator's console really hands us."""
    return io.TextIOWrapper(io.BytesIO(), encoding="cp1252", newline="")


class TestTheStreamIsGenuinelyNarrowToStartWith:
    """The falsifiers. If these stop raising, every test below proves nothing."""

    def test_a_bare_cp1252_stream_dies_on_a_minus_sign(self):
        stream = cp1252_stream()
        with pytest.raises(UnicodeEncodeError):
            stream.write(MINUS)
            stream.flush()

    def test_it_dies_on_the_whole_family(self):
        stream = cp1252_stream()
        with pytest.raises(UnicodeEncodeError):
            stream.write(HARD)
            stream.flush()


class TestWidening:
    def test_a_widened_stream_carries_the_minus_sign(self):
        stream = cp1252_stream()
        assert utf8_console.widen(stream) is True
        stream.write(MINUS)
        stream.flush()
        assert stream.buffer.getvalue().decode("utf-8") == MINUS

    def test_it_carries_the_whole_family_losslessly(self):
        stream = cp1252_stream()
        utf8_console.widen(stream)
        stream.write(HARD)
        stream.flush()
        # Lossless, not merely non-crashing -- tier 1 must not degrade to '?'.
        assert stream.buffer.getvalue().decode("utf-8") == HARD

    def test_widening_twice_is_the_same_as_once(self):
        stream = cp1252_stream()
        utf8_console.widen(stream)
        utf8_console.widen(stream)
        stream.write(MINUS)
        stream.flush()
        assert stream.buffer.getvalue().decode("utf-8") == MINUS

    def test_a_stream_that_cannot_be_reconfigured_is_left_alone(self):
        class Plain:
            def __init__(self):
                self.written = []

            def write(self, text):
                self.written.append(text)

        plain = Plain()
        assert utf8_console.widen(plain) is False
        plain.write(MINUS)
        assert plain.written == [MINUS]

    def test_none_is_not_an_error(self):
        """sys.stderr can be None under pythonw."""
        assert utf8_console.widen(None) is False


class TestTheFallbackTier:
    """If UTF-8 is refused, output degrades to '?' rather than to a traceback."""

    def test_it_falls_back_to_replace_when_the_encoding_is_refused(self):
        stream = cp1252_stream()
        real = stream.reconfigure
        calls = []

        def picky(**kwargs):
            calls.append(kwargs)
            if "encoding" in kwargs:
                raise ValueError("this stream's encoding is fixed")
            return real(**kwargs)

        stream.reconfigure = picky
        assert utf8_console.widen(stream) is True

        # Tier 1 was tried and refused; tier 2 set errors alone.
        assert "encoding" in calls[0]
        assert calls[1] == {"errors": "replace"}

        stream.write(MINUS)
        stream.flush()
        assert stream.buffer.getvalue() == b"?"

    def test_a_stream_that_refuses_everything_reports_failure_quietly(self):
        stream = cp1252_stream()

        def refuse(**kwargs):
            raise ValueError("no")

        stream.reconfigure = refuse
        # No exception escapes -- the report tool must not die in its own
        # defensive code either.
        assert utf8_console.widen(stream) is False


class TestInstall:
    def test_it_widens_both_stdout_and_stderr(self, monkeypatch):
        out, err = cp1252_stream(), cp1252_stream()
        monkeypatch.setattr(sys, "stdout", out)
        monkeypatch.setattr(sys, "stderr", err)

        utf8_console.install()

        out.write(MINUS)
        err.write(MINUS)
        out.flush()
        err.flush()
        assert out.buffer.getvalue().decode("utf-8") == MINUS
        assert err.buffer.getvalue().decode("utf-8") == MINUS

    def test_it_acts_again_after_the_stream_is_replaced(self, monkeypatch):
        """No installed-once guard: pytest swaps stdout between tests, and a
        second entry point in the same process must still be protected."""
        monkeypatch.setattr(sys, "stdout", cp1252_stream())
        utf8_console.install()

        fresh = cp1252_stream()
        monkeypatch.setattr(sys, "stdout", fresh)
        utf8_console.install()

        fresh.write(MINUS)
        fresh.flush()
        assert fresh.buffer.getvalue().decode("utf-8") == MINUS


class TestTheFormCheckerSurvivesItsOwnBindingDoc:
    """The acceptance criterion, end to end through the real entry point."""

    # A bare statement with no modal verb, so it cannot match an EARS pattern
    # under this matcher or any plausible successor to it -- the violation that
    # quotes the line back is what carries the minus sign into the report, which
    # is exactly how the live crash happened while #1 was being converted.
    BODY = (
        "## Requirements\n"
        "\n"
        f"- The needle angle is 225° {MINUS} 2.7° × value.\n"
        "\n"
        "## Acceptance Criteria\n"
        "\n"
        f"- [ ] the needle sits at 225° {MINUS} 2.7° × value\n"
    )

    def rendered_report(self) -> str:
        from assemblyzero.workflows.requirements import form_check as fc

        report = fc.check_form(self.BODY)
        assert not report.ok, (
            "the fixture must fail so the report quotes the offending line; "
            "if the matcher changed, pick a sentence it still rejects"
        )
        return fc.render_report(report, "aesthetic.md")

    def test_this_report_genuinely_kills_an_unwidened_stream(self):
        """The falsifier. Establishes that the text below is hostile to cp1252,
        so the passing run afterwards is the fix working and not a tame input."""
        narrow = cp1252_stream()
        with pytest.raises(UnicodeEncodeError):
            narrow.write(self.rendered_report())
            narrow.flush()

    def test_it_renders_a_report_quoting_a_true_minus_sign(
        self, tmp_path, monkeypatch
    ):
        import check_requirements_form as tool

        doc = tmp_path / "aesthetic.md"
        doc.write_text(self.BODY, encoding="utf-8")

        out = cp1252_stream()
        monkeypatch.setattr(sys, "stdout", out)
        # The tool installs at import, against whatever stdout it was launched
        # with -- which is the right order for a real CLI run. pytest replaces
        # stdout long after that import, so re-run the entry point's own first
        # act to reproduce the launch condition rather than the test harness's.
        tool._install_utf8_console()

        # Would raise UnicodeEncodeError before #2367.
        tool.main(["--file", str(doc)])

        out.flush()
        rendered = out.buffer.getvalue().decode("utf-8")
        assert MINUS in rendered, "the report must quote the character verbatim"
        assert "Requirements form check" in rendered


class TestEveryReportRendererInstallsIt:
    """A program, not an inspection.

    The sweep this issue asked for is only worth doing once if a new report
    tool cannot silently reopen the hole. The rule is mechanical: a tool that
    prints the output of a `render*()` function is printing text it did not
    author, so it must widen its console first.
    """

    PRINTS_A_RENDERING = re.compile(r"print\(\s*render\w*\(")

    def renderers(self) -> list[Path]:
        found = [
            path
            for path in sorted((ROOT / "tools").glob("*.py"))
            if self.PRINTS_A_RENDERING.search(path.read_text(encoding="utf-8"))
        ]
        assert found, "the scan found no report renderers, so it checked nothing"
        return found

    def test_the_known_renderers_are_all_found(self):
        """Pins the scan itself. If a rename drops a tool out of the sweep, this
        fails rather than the guard below silently checking a shorter list."""
        assert {p.name for p in self.renderers()} == {
            "check_requirements.py",
            "check_requirements_form.py",
            "heal_report.py",
            "prompt_failure_report.py",
            "prompt_revision_rank.py",
            "speedrun_overlay.py",
            "stash_audit.py",
        }

    @pytest.mark.parametrize(
        "name",
        [
            "check_requirements.py",
            "check_requirements_form.py",
            "heal_report.py",
            "prompt_failure_report.py",
            "prompt_revision_rank.py",
            "speedrun_overlay.py",
            "stash_audit.py",
        ],
    )
    def test_each_renderer_installs_the_widening(self, name):
        source = (ROOT / "tools" / name).read_text(encoding="utf-8")
        assert "_install_utf8_console()" in source, (
            f"{name} prints a rendered report but never widens its console"
        )

    def test_the_install_precedes_the_first_print(self):
        """Order matters the same way it does for no_console: a module imported
        first could print during import."""
        for path in self.renderers():
            source = path.read_text(encoding="utf-8")
            install_at = source.index("_install_utf8_console()")
            print_at = self.PRINTS_A_RENDERING.search(source).start()
            assert install_at < print_at, f"{path.name} prints before widening"
