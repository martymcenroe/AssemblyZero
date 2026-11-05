"""AssemblyZero's rule files never teach landing a PR by hand (#3803).

The merge driver pushes, opens the PR, merges, removes the worktree and deletes
the branch. An agent rereads CLAUDE.md and runbook 0935 when a landing has gone
wrong, so a command block in either that merges, checks out, deletes or skips
CI sends it into a refused command or a worse mess.
"""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FILES = [ROOT / "CLAUDE.md", ROOT / "docs" / "runbooks" / "0935-pr-stuck-recovery.md"]

# A closed set: every hand-landing or refused form these two files have carried.
FORBIDDEN = (
    "gh pr merge",
    "gh pr create",
    "git checkout",
    "git worktree remove",
    "git branch -d",
    "git push",
    "update-branch",
    "[skip ci]",
    "--body ",
    "echo ",
    "gh pr close",  # woke the retired Auto Review (#4189)
    "gh pr reopen",
)

RUNBOOK = FILES[1]

# A closed set: the words that mark a mention of Auto Review as history (#4189).
RETIRED_CONTEXT = ("retired", "skipped", "Earlier versions", "#3663")


def bash_blocks(text: str) -> list[str]:
    """The bodies of the ```bash fences: the commands a reader is told to run."""
    blocks, inside, current = [], False, []
    for line in text.splitlines():
        fence = line.strip()
        if not inside and fence == "```bash":
            inside, current = True, []
        elif inside and fence == "```":
            blocks.append("\n".join(current))
            inside = False
        elif inside:
            current.append(line)
    return blocks


def offenders(text: str) -> list[str]:
    return [form for block in bash_blocks(text) for form in FORBIDDEN if form in block]


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_no_command_block_lands_by_hand(path):
    assert offenders(path.read_text(encoding="utf-8")) == []


def test_the_check_finds_a_hand_merge():
    fixture = "intro\n```bash\ngh pr merge 1 --squash\ngit commit -m \"x [skip ci]\"\n```\n"
    assert offenders(fixture) == ["gh pr merge", "[skip ci]"]


def test_a_quoted_block_is_not_a_command():
    assert offenders("```text\necho quoted from a workflow\n```\n") == []


def decision_tree(text: str) -> str:
    """The fenced block under the runbook's "Diagnostic Decision Tree" heading."""
    after = text.split("## Diagnostic Decision Tree", 1)[1]
    return after.split("```", 2)[1]


def test_runbook_mentions_auto_review_only_as_retired():
    """#4189 test 1: #3663 retired Auto Review, so every line naming it is history."""
    lines = RUNBOOK.read_text(encoding="utf-8").splitlines()
    live = [
        line for line in lines
        if "Auto Review" in line and not any(word in line for word in RETIRED_CONTEXT)
    ]
    assert live == []


def test_runbook_tree_has_the_no_review_branch():
    """#4189 test 2: a skipped Auto Review with no review has its own branch."""
    tree = decision_tree(RUNBOOK.read_text(encoding="utf-8"))
    assert "REVIEW_REQUIRED" in tree
    assert "No Review At All" in tree


def no_review_section(text: str) -> str:
    """The runbook's "No Review At All" section, up to the next heading."""
    after = text.split("## No Review At All", 1)[1]
    return after.split("\n## ", 1)[0]


def test_no_review_section_counts_the_checks():
    """#4562 T1: the section counts the head commit's contexts against its jobs."""
    section = no_review_section(RUNBOOK.read_text(encoding="utf-8"))
    assert "issue-reference" in section
    assert "driver-provenance" in section
    commands = "\n".join(bash_blocks(section))
    assert "totalCount" in commands
    assert "--json jobs" in commands
    assert "**No more contexts than jobs:**" in section
    assert "**More contexts than jobs:**" in section


def test_no_review_section_needs_the_log_only_when_the_checks_are_present():
    """#4562 T1: the operator's log is named only where pr-sentinel's checks are present."""
    section = no_review_section(RUNBOOK.read_text(encoding="utf-8"))
    needs_log = [line for line in section.splitlines() if "only the operator can read" in line]
    assert needs_log
    assert all("checks are present" in line for line in needs_log)


def test_runbook_tree_splits_the_no_review_branch():
    """#4562 T2: the tree's "No Review At All" branch carries both outcomes of the count."""
    tree = decision_tree(RUNBOOK.read_text(encoding="utf-8"))
    assert "never saw the PR" in tree
    assert "saw it and did not" in tree


def test_claude_md_keeps_the_archival_override():
    text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "tools/archive_worktree_lineage.py --worktree . --issue {ID} --main-repo ." in text
    assert "Merging PRs (Universal)" in text
