"""Runbook 0952 is re-verified, not merely described as verified (#2295).

The document says its flag table was "verified against
`poetry run python tools/speedrun_roll.py --help` rather than transcribed", and
directly above that sentence its canonical launch example passed `--attempts 3`
-- retired by operator ruling #2206, refused at preflight, and correctly
described as retired in the very table below. An operator copying the canonical
example got a preflight refusal from the document written to prevent one.

A verification nothing re-runs is a claim about one afternoon. This file is the
program that keeps it true: it reads the runbook, extracts every command it
tells an operator to run, and puts each one through the real argparse.

Real parsers, not a regex over the source. While investigating #2295 a regex
reading of `add_argument` reported `--issue` as documented-but-nonexistent,
because the flag sits on the line after the call. It is the launcher's most
used flag. That is exactly the false alarm this suite must not produce, so
`build_parser()` was extracted from both tools and is used here directly.
"""
from __future__ import annotations

import re
import shlex
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import speedrun_archive  # noqa: E402
import speedrun_roll  # noqa: E402

RUNBOOK = ROOT / "docs" / "runbooks" / "0952-speedrun-operator-solo.md"

TOOLS = {
    "tools/speedrun_roll.py": speedrun_roll.build_parser,
    "tools/speedrun_archive.py": speedrun_archive.build_parser,
}


@pytest.fixture(scope="module")
def runbook() -> str:
    return RUNBOOK.read_text(encoding="utf-8")


def visible_flags(parser) -> set[str]:
    """Operator-facing long flags. `argparse.SUPPRESS` means not for humans.

    `--detached-stdout` is set by `--detach` on the relaunch and is not
    something anyone types, so requiring the runbook to document it would be a
    false alarm -- the failure mode this suite exists to avoid.
    """
    found = set()
    for action in parser._actions:
        if action.help is not None and "==SUPPRESS==" in str(action.help):
            continue
        if action.dest == "help":
            continue
        found.update(o for o in action.option_strings if o.startswith("--"))
    return found


def code_blocks(runbook: str) -> list[str]:
    """The fenced blocks only.

    Prose mentions commands too -- the flag table's own preamble names
    `speedrun_roll.py --help` -- and those are not things an operator copies as
    a command. Parsing them would extract `--help`, which argparse answers by
    printing usage and raising SystemExit.
    """
    return re.findall(r"```(?:bash)?\n(.*?)```", runbook, re.S)


def commands(runbook: str, tool: str) -> list[list[str]]:
    """Every invocation of `tool` in the runbook's code blocks, as argv.

    Line continuations are joined first, so a multi-line example is read the
    way the operator's shell would read it rather than as its first line.
    """
    out = []
    for block in code_blocks(runbook):
        joined = re.sub(r"\\\s*\n\s*", " ", block)
        for line in joined.splitlines():
            line = line.strip()
            if tool not in line:
                continue
            argv = shlex.split(line)
            out.append(argv[argv.index(tool) + 1 :])
    return out


class TestTheExamplesActuallyParse:
    """The reported bug, and its whole class."""

    def test_the_launch_example_is_present_and_parses(self, runbook):
        found = commands(runbook, "tools/speedrun_roll.py")
        assert found, "no launcher example found -- the extractor is broken"
        for argv in found:
            speedrun_roll.build_parser().parse_known_args(argv)

    def test_the_archive_examples_parse(self, runbook):
        found = commands(runbook, "tools/speedrun_archive.py")
        assert found, "no archive example found -- the extractor is broken"
        for argv in found:
            speedrun_archive.build_parser().parse_args(argv)

    def test_no_example_passes_a_retired_attempts_value(self, runbook):
        """`--attempts` still exists so an explicit `1` parses; anything above
        it refuses at preflight (ruling #2206). The runbook must not ship a
        command that dies there."""
        for argv in commands(runbook, "tools/speedrun_roll.py"):
            args, _ = speedrun_roll.build_parser().parse_known_args(argv)
            assert getattr(args, "attempts", 1) <= 1, (
                f"example passes --attempts {args.attempts}, which refuses at "
                f"preflight: {' '.join(argv)}"
            )

    def test_the_retired_flag_is_gone_from_the_launch_example(self, runbook):
        """Belt and braces on the literal text, since the assertion above would
        also pass if the example were deleted rather than corrected.

        Scoped to the code block. The flag table a few lines below documents
        `--attempts` as retired, which is correct and must stay -- that row is
        how the contradiction was noticed in the first place.
        """
        blocks = [b for b in code_blocks(runbook) if "speedrun_roll.py" in b]
        assert blocks, "the launch example vanished"
        launch = blocks[0]
        assert "--repo" in launch and "--issue" in launch
        assert "--attempts" not in launch


class TestTheFlagTableMatchesTheLauncher:
    def table_flags(self, runbook: str) -> set[str]:
        return set(re.findall(r"^\|\s*`(--[a-z0-9-]+)`\s*\|", runbook, re.M))

    def test_the_table_was_found(self, runbook):
        assert len(self.table_flags(runbook)) > 5, "the table scrape found ~nothing"

    def test_no_documented_flag_is_imaginary(self, runbook):
        real = visible_flags(speedrun_roll.build_parser())
        invented = self.table_flags(runbook) - real
        assert not invented, (
            f"runbook documents flags the launcher does not accept: {sorted(invented)}"
        )

    def test_no_operator_facing_flag_is_undocumented(self, runbook):
        """So a flag added to the launcher cannot quietly go unmentioned."""
        missing = visible_flags(speedrun_roll.build_parser()) - self.table_flags(
            runbook
        )
        assert not missing, (
            f"launcher accepts flags the runbook never mentions: {sorted(missing)}"
        )

    def test_an_internal_flag_is_not_required_to_be_documented(self):
        """--detached-stdout is SUPPRESS: set by --detach on the relaunch, never
        typed. Demanding it appear in the table would be a false alarm."""
        parser = speedrun_roll.build_parser()
        assert "--detached-stdout" not in visible_flags(parser)
        assert "--detached-stdout" in {
            o for a in parser._actions for o in a.option_strings
        }


class TestTheGuardCanFail:
    """A check whose passing state has never been made to fail is not a check."""

    def test_a_planted_imaginary_flag_is_caught(self, runbook):
        planted = runbook + "\n| `--not-a-real-flag` | invented |\n"
        real = visible_flags(speedrun_roll.build_parser())
        table = set(re.findall(r"^\|\s*`(--[a-z0-9-]+)`\s*\|", planted, re.M))
        assert table - real == {"--not-a-real-flag"}

    def test_a_planted_retired_attempts_example_is_caught(self):
        argv = ["--repo", "/x", "--issue", "7", "--attempts", "3"]
        args, _ = speedrun_roll.build_parser().parse_known_args(argv)
        assert args.attempts > 1, "the preflight rule would refuse this"

    def test_the_extractor_joins_line_continuations(self):
        """The launch example spans four lines. Read line-by-line it would
        appear to pass no flags at all, and every assertion above would pass
        vacuously."""
        doc = (
            "```bash\n"
            "poetry run python tools/speedrun_roll.py \\\n"
            "    --repo /tmp/x \\\n"
            "    --issue 7 \\\n"
            "    --detach\n"
            "```\n"
        )
        (argv,) = commands(doc, "tools/speedrun_roll.py")
        assert argv == ["--repo", "/tmp/x", "--issue", "7", "--detach"]
