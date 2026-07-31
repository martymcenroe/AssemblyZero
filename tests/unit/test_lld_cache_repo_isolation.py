"""The LLD approval cache lives inside the repo it describes (#1970, #1160).

#1151 moved this cache to `~/.claude/assemblyzero/lld-status.json` to stop it
dirtying worktrees. That solved a visible problem by creating four hidden ones:
one file shared by every target repo, outside version control, invisible to the
operator, and untouched by every cleanup tool including speedrun_reset.

The damage was measurable. #1160 found entries keyed by bare issue number, so
two repos' issue #4 shared one entry and every entry survived every repo reset.
#1970 found 42 slices in the live file, all pytest temp directories, because
isolation depended on each test file remembering to monkeypatch a constant --
and two files forgot. Before repo-scoping, those test writes had been
OVERWRITING real approvals: the production cache carried issue numbers 42, 50,
77, 99, 100, 200, 300.

The cache is now `<target_repo>/data/assemblyzero/lld-status.json`. Note what
this file no longer needs: an isolation fixture. A test whose target repo is
`tmp_path` writes under `tmp_path`. Isolation stopped being something to
remember and became something the design guarantees.
"""

import json
import subprocess
from pathlib import Path

import pytest

from assemblyzero.workflows.requirements.audit import (
    LLD_STATUS_RELATIVE,
    lld_status_path,
    load_lld_tracking,
    save_lld_tracking,
    update_lld_status,
)

APPROVED = {
    "has_gemini_review": True,
    "final_verdict": "APPROVED",
    "last_review_date": "2026-07-31",
    "review_count": 1,
}
UNREVIEWED = {"has_gemini_review": False, "final_verdict": None, "review_count": 0}


def _git(cwd, *args):
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=str(cwd), check=True, capture_output=True, text=True,
    )


@pytest.fixture
def repo_a(tmp_path):
    p = tmp_path / "boostgauge"
    p.mkdir()
    return p


@pytest.fixture
def repo_b(tmp_path):
    p = tmp_path / "someotherrepo"
    p.mkdir()
    return p


class TestTheCacheIsInsideTheRepo:
    def test_path_resolves_under_the_target_repo(self, repo_a):
        assert lld_status_path(repo_a) == repo_a / LLD_STATUS_RELATIVE

    def test_it_is_not_in_the_users_home(self, repo_a):
        assert Path.home() / ".claude" not in lld_status_path(repo_a).parents

    def test_the_constant_is_relative(self):
        """An absolute constant is exactly how this escaped into ~/.claude."""
        assert not LLD_STATUS_RELATIVE.is_absolute()

    def test_writing_creates_it_inside_the_repo(self, repo_a):
        update_lld_status(4, "docs/lld/active/LLD-004.md", APPROVED, repo_a)

        assert (repo_a / LLD_STATUS_RELATIVE).is_file()

    def test_it_lands_under_data_which_is_gitignored_fleet_wide(self):
        """The universal CLAUDE.md names data/ as the destination for
        agent-written state, precisely so it is visible but never committed."""
        assert LLD_STATUS_RELATIVE.parts[0] == "data"


class TestCollisionIsStructurallyImpossible:
    """Two repos cannot share an entry because they no longer share a file."""

    def test_two_repos_have_separate_files(self, repo_a, repo_b):
        assert lld_status_path(repo_a) != lld_status_path(repo_b)

    def test_one_repos_approval_is_invisible_to_another(self, repo_a, repo_b):
        update_lld_status(4, "docs/lld/active/LLD-004.md", APPROVED, repo_a)

        assert load_lld_tracking(repo_b)["issues"] == {}

    def test_same_issue_number_in_both_repos_does_not_clash(self, repo_a, repo_b):
        update_lld_status(4, "docs/lld/active/LLD-004.md", APPROVED, repo_a)
        update_lld_status(4, "docs/lld/active/LLD-004.md", UNREVIEWED, repo_b)

        assert load_lld_tracking(repo_a)["issues"]["4"]["status"] == "approved"
        assert load_lld_tracking(repo_b)["issues"]["4"]["status"] == "draft"

    def test_a_repos_own_approval_round_trips(self, repo_a):
        update_lld_status(4, "docs/lld/active/LLD-004.md", APPROVED, repo_a)

        assert load_lld_tracking(repo_a)["issues"]["4"]["status"] == "approved"


class TestWorktreesShareTheMainRepoCache:
    """The pipeline runs stages from `{repo}-{issue}` worktrees. Per-worktree
    caches would make an approval recorded in one invisible to the next."""

    @pytest.fixture
    def repo(self, tmp_path):
        r = tmp_path / "target"
        r.mkdir()
        _git(r, "init", "-b", "main")
        (r / "README.md").write_text("x", encoding="utf-8")
        _git(r, "add", "-A")
        _git(r, "commit", "-m", "init")
        return r

    def test_a_worktree_resolves_to_the_main_repos_cache(self, repo, tmp_path):
        worktree = tmp_path / "target-7"
        _git(repo, "worktree", "add", str(worktree), "-b", "issue-7")

        assert lld_status_path(worktree) == lld_status_path(repo)

    def test_an_approval_written_from_a_worktree_is_visible_in_the_repo(
        self, repo, tmp_path
    ):
        worktree = tmp_path / "target-7"
        _git(repo, "worktree", "add", str(worktree), "-b", "issue-7")

        update_lld_status(7, "docs/lld/active/LLD-007.md", APPROVED, worktree)

        assert load_lld_tracking(repo)["issues"]["7"]["status"] == "approved"

    def test_a_non_git_directory_still_resolves(self, tmp_path):
        """`git rev-parse` fails outside a repo; the path must still resolve
        rather than raising, so plain-directory callers keep working."""
        plain = tmp_path / "not-a-repo"
        plain.mkdir()

        assert lld_status_path(plain) == plain / LLD_STATUS_RELATIVE


class TestLegacyFlatFileMigration:
    """A pre-#1160 flat file records no repo, so its entries cannot be
    attributed. Kept on disk, served to nobody."""

    def _write_legacy(self, repo):
        path = repo / LLD_STATUS_RELATIVE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "version": "1.0",
            "last_updated": "2026-07-29T00:00:00Z",
            "issues": {"4": {
                "lld_path": "docs/lld/active/LLD-004.md",
                "status": "approved", "has_gemini_review": True,
                "final_verdict": "APPROVED", "last_review_date": "2026-07-30",
                "review_count": 1,
            }},
        }), encoding="utf-8")

    def test_legacy_entries_are_not_served(self, repo_a):
        self._write_legacy(repo_a)

        assert load_lld_tracking(repo_a)["issues"] == {}

    def test_an_unattributable_approval_does_not_skip_review(self, repo_a):
        """The direction that matters: honouring it would skip a review the
        workflow was told to perform. Dropping it costs one review."""
        self._write_legacy(repo_a)

        assert "4" not in load_lld_tracking(repo_a)["issues"]

    def test_legacy_entries_are_preserved_on_disk(self, repo_a):
        self._write_legacy(repo_a)
        update_lld_status(9, "docs/lld/active/LLD-009.md", APPROVED, repo_a)

        raw = json.loads((repo_a / LLD_STATUS_RELATIVE).read_text(encoding="utf-8"))
        assert raw["legacy_unscoped"]["4"]["final_verdict"] == "APPROVED"


class TestFileLevelRobustness:
    def test_missing_file_yields_empty(self, repo_a):
        assert load_lld_tracking(repo_a)["issues"] == {}

    def test_corrupt_file_yields_empty(self, repo_a):
        path = repo_a / LLD_STATUS_RELATIVE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("not json {", encoding="utf-8")

        assert load_lld_tracking(repo_a)["issues"] == {}

    def test_non_dict_file_yields_empty(self, repo_a):
        path = repo_a / LLD_STATUS_RELATIVE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("[1, 2, 3]", encoding="utf-8")

        assert load_lld_tracking(repo_a)["issues"] == {}

    def test_save_creates_the_directory(self, repo_a):
        assert not (repo_a / LLD_STATUS_RELATIVE).exists()

        save_lld_tracking({"issues": {}}, repo_a)

        assert (repo_a / LLD_STATUS_RELATIVE).is_file()

    def test_round_trip_through_save_and_load(self, repo_a):
        tracking = load_lld_tracking(repo_a)
        tracking["issues"]["7"] = {
            "lld_path": "docs/lld/active/LLD-007.md", "status": "blocked",
            "has_gemini_review": True, "final_verdict": "REJECTED",
            "last_review_date": "2026-07-31", "review_count": 2,
        }
        save_lld_tracking(tracking, repo_a)

        assert load_lld_tracking(repo_a)["issues"]["7"]["status"] == "blocked"
