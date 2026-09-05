"""N0c judges the requirements, not the revision history (#2870).

boostgauge #4, 2026-09-05: launches 21 and 22 halted at the
requirements-consistency gate on text that had passed it on launches 14,
15, 17, 18, 19 and 20. The second halt's reasoning named the cause: "the
historical recommendation mentioned in the revision history."

The revision history is a dated log of rulings; each entry quotes the
superseded sentence it replaced. Handed to the model as requirements, every
one of those sentences reads as a live contradiction of the criterion that
replaced it, and the log grows by one entry per ruling.

The first class tests the cut itself. The second drives `analyze_requirements`
with the provider stubbed at its boundary and asserts what the model was
actually shown.
"""

from __future__ import annotations

import importlib
from types import SimpleNamespace
from unittest.mock import patch

import pytest

# The package re-exports the node FUNCTION under the module's name, so a
# `from ... import analyze_requirements` yields the function. Import the
# module itself.
n0c = importlib.import_module(
    "assemblyzero.workflows.requirements.nodes.analyze_requirements"
)

LIVE = """\
# Collector

## Acceptance criteria

- [ ] < 2% CPU overhead at 2s polling interval: mean process_time over 8 ticks is < 40 ms
- [ ] All process-derived metrics come from a single sweep of the process table per tick
"""

HISTORY = """\
## Revision history

**2026-09-01** — a hand spike measured the sweep at 422 ms against the `< 1%` criterion (20 ms) and recommended `len(psutil.pids())` for process count.

**2026-09-05** — ruling: the CPU criterion is now `< 2%`, 40 ms.
"""

BODY = LIVE + "\n" + HISTORY


class TestTheCut:
    def test_cuts_at_the_revision_history_heading(self):
        kept, excluded = n0c.requirements_text(BODY)

        assert "< 40 ms" in kept
        assert "Revision history" not in kept
        assert "psutil.pids()" not in kept, "the superseded recommendation must not reach the model"
        assert excluded == len(HISTORY.splitlines())

    @pytest.mark.parametrize(
        "heading",
        ["## Revision history", "### REVISION HISTORY", "# Changelog", "## History", "## Rulings", "## Change log"],
    )
    def test_recognises_the_family_of_headings_at_any_level(self, heading):
        kept, excluded = n0c.requirements_text(LIVE + "\n" + heading + "\n\nold text\n")

        assert "old text" not in kept
        assert excluded == 3

    def test_a_body_without_a_history_is_returned_whole(self):
        kept, excluded = n0c.requirements_text(LIVE)

        assert kept == LIVE
        assert excluded == 0

    def test_a_heading_inside_a_code_fence_is_text_not_structure(self):
        body = LIVE + "\n```markdown\n## Revision history\nexample entry\n```\n\n- [ ] one more criterion\n"

        kept, excluded = n0c.requirements_text(body)

        assert "one more criterion" in kept
        assert excluded == 0

    def test_a_word_in_prose_is_not_a_heading(self):
        body = LIVE + "\nThe history of this metric is long.\n- [ ] last criterion\n"

        kept, excluded = n0c.requirements_text(body)

        assert "last criterion" in kept
        assert excluded == 0


class TestWhatTheModelIsShown:
    def _run(self, body: str, capsys):
        shown: list[str] = []

        class _Provider:
            def invoke(self, system_prompt, content, timeout_seconds, **kwargs):
                shown.append(content)
                return SimpleNamespace(
                    success=True,
                    response='{"is_consistent": true, "conflicts": [], "notes": []}',
                    error_message="",
                )

        state = {
            "issue_title": "Collector",
            "issue_body": body,
            "config_drafter": "gemini:3.1-pro",
        }
        with patch("assemblyzero.core.llm_provider.get_provider", return_value=_Provider()):
            result = n0c.analyze_requirements(state)
        return result, shown, capsys.readouterr().out

    def test_the_model_sees_only_the_live_requirements(self, capsys):
        result, shown, out = self._run(BODY, capsys)

        assert result == {}, result
        assert len(shown) == 1
        assert "< 40 ms" in shown[0]
        assert "psutil.pids()" not in shown[0]
        assert "Revision history" not in shown[0]

    def test_the_exclusion_is_named_in_the_log(self, capsys):
        _, _, out = self._run(BODY, capsys)

        assert "excluded as provenance (#2870)" in out
        assert f"revision history ({len(HISTORY.splitlines())} lines)" in out

    def test_a_body_without_a_history_prints_no_exclusion(self, capsys):
        _, shown, out = self._run(LIVE, capsys)

        assert LIVE.strip() in shown[0]
        assert "excluded as provenance" not in out
