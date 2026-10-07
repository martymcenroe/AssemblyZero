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
)


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


def test_claude_md_keeps_the_archival_override():
    text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "tools/archive_worktree_lineage.py --worktree . --issue {ID} --main-repo ." in text
    assert "Merging PRs (Universal)" in text
