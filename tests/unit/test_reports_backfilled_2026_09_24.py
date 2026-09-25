"""The eighteen PRs of 2026-09-24 that landed past the report gate have
their reports (#3559).

The pre-commit report gate matched only a command beginning `git commit`,
and a commit from a worktree is shaped `cd <worktree> && git commit`, so on
2026-09-24 eighteen PRs merged with no `docs/reports/{issue}/`. The
reports were backfilled from the PR bodies on 2026-09-25; this pins that
every pair exists and says it was backfilled.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "docs" / "reports"

#: (issue directory, PR) for every PR in the #3559 table. The #3539 PR
#: closed #3518, #3231 and #3528; its reports sit under 3518.
BACKFILLED: tuple[tuple[int, int], ...] = (
    (3503, 3520), (3505, 3521), (3515, 3522), (3514, 3524), (3507, 3525),
    (3508, 3526), (3523, 3529), (3513, 3530), (3511, 3532), (3533, 3534),
    (3512, 3535), (3510, 3537), (3509, 3538), (3518, 3539), (3506, 3540),
    (3541, 3542), (3504, 3543), (3536, 3544),
)


@pytest.mark.parametrize(("issue", "pr"), BACKFILLED)
def test_both_reports_exist_and_name_their_pr(issue: int, pr: int):
    for name in ("implementation-report.md", "test-report.md"):
        path = REPORTS / str(issue) / name
        assert path.is_file(), path
        text = path.read_text(encoding="utf-8")
        assert "Backfilled 2026-09-25" in text, path
        assert f"PR #{pr}" in text, path


def test_the_table_has_eighteen_rows():
    assert len(BACKFILLED) == 18
    assert len({issue for issue, _ in BACKFILLED}) == 18
