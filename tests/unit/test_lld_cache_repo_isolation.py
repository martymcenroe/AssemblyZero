"""The LLD status cache is scoped per target repo (#1160).

PR #1156 moved LLD_STATUS_FILE to an absolute path under ~/.claude. The caller
pattern `target_repo / LLD_STATUS_FILE` then collapsed to that absolute path --
Python's `/` discards the left operand when the right is absolute -- so
`target_repo` was silently ignored on every read and write. Entries were keyed
by bare issue number with no repo recorded anywhere, which meant:

  - boostgauge #4 and any other repo's #4 shared one entry, each overwriting
    the other's approval state;
  - the whole file outlived every repo reset, because `speedrun_reset.py` has
    no reason to know about a cache in the home directory.

The constant's own comment asserted that "each entry self-identifies via
issue_number / target_repo". It did not; no entry carried a repo at all. These
tests exist so that claim is enforced rather than asserted.
"""

import json
from pathlib import Path

import pytest

from assemblyzero.workflows.requirements.audit import (
    load_lld_tracking,
    save_lld_tracking,
    update_lld_status,
)


@pytest.fixture(autouse=True)
def _shared_cache_file(monkeypatch, tmp_path: Path) -> Path:
    """One shared cache file, as in production -- NOT one per repo.

    Pointing this at a per-test path would hide the very collision under test.
    """
    cache = tmp_path / "home" / ".claude" / "assemblyzero" / "lld-status.json"
    monkeypatch.setattr(
        "assemblyzero.workflows.requirements.audit.LLD_STATUS_FILE", cache
    )
    return cache


@pytest.fixture
def repo_a(tmp_path: Path) -> Path:
    path = tmp_path / "boostgauge"
    path.mkdir()
    return path


@pytest.fixture
def repo_b(tmp_path: Path) -> Path:
    path = tmp_path / "someotherrepo"
    path.mkdir()
    return path


APPROVED = {
    "has_gemini_review": True,
    "final_verdict": "APPROVED",
    "last_review_date": "2026-07-30",
    "review_count": 1,
}
UNREVIEWED = {"has_gemini_review": False, "final_verdict": None, "review_count": 0}


class TestTwoReposSameIssueNumber:
    """The founding collision: issue #4 exists in more than one repo."""

    def test_one_repos_approval_is_not_visible_to_another(
        self, repo_a, repo_b
    ):
        update_lld_status(4, "docs/lld/active/LLD-004.md", APPROVED, repo_a)

        assert load_lld_tracking(repo_b)["issues"] == {}

    def test_one_repos_approval_is_visible_to_itself(self, repo_a):
        update_lld_status(4, "docs/lld/active/LLD-004.md", APPROVED, repo_a)

        entry = load_lld_tracking(repo_a)["issues"]["4"]
        assert entry["status"] == "approved"

    def test_writing_one_repo_does_not_clobber_another(self, repo_a, repo_b):
        update_lld_status(4, "docs/lld/active/LLD-004.md", APPROVED, repo_a)
        update_lld_status(4, "docs/lld/active/LLD-004.md", UNREVIEWED, repo_b)

        assert load_lld_tracking(repo_a)["issues"]["4"]["status"] == "approved"
        assert load_lld_tracking(repo_b)["issues"]["4"]["status"] == "draft"

    def test_both_slices_coexist_in_one_file(self, repo_a, repo_b, _shared_cache_file):
        update_lld_status(4, "docs/lld/active/LLD-004.md", APPROVED, repo_a)
        update_lld_status(9, "docs/lld/active/LLD-009.md", APPROVED, repo_b)

        raw = json.loads(_shared_cache_file.read_text(encoding="utf-8"))
        assert len(raw["repos"]) == 2, raw
        assert raw["version"] == "2.0"


class TestRepoKeyNormalisation:
    def test_same_repo_via_a_relative_path_hits_the_same_slice(
        self, repo_a, monkeypatch
    ):
        update_lld_status(4, "docs/lld/active/LLD-004.md", APPROVED, repo_a)

        monkeypatch.chdir(repo_a.parent)
        assert load_lld_tracking(Path(repo_a.name))["issues"]["4"]["status"] == (
            "approved"
        )

    def test_trailing_separator_hits_the_same_slice(self, repo_a):
        update_lld_status(4, "docs/lld/active/LLD-004.md", APPROVED, repo_a)

        assert load_lld_tracking(Path(str(repo_a) + "/"))["issues"] != {}


class TestLegacyUnscopedMigration:
    """A pre-#1160 flat file records no repo, so its entries cannot be
    attributed. They are kept on disk and served to nobody."""

    def _write_legacy(self, cache: Path) -> None:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(
            json.dumps(
                {
                    "version": "1.0",
                    "last_updated": "2026-07-29T00:00:00Z",
                    "issues": {
                        "4": {
                            "lld_path": "docs\\lld\\active\\LLD-004.md",
                            "status": "approved",
                            "has_gemini_review": True,
                            "final_verdict": "APPROVED",
                            "last_review_date": "2026-07-30",
                            "review_count": 1,
                        }
                    },
                }
            ),
            encoding="utf-8",
        )

    def test_legacy_entries_are_not_served_to_any_repo(
        self, repo_a, repo_b, _shared_cache_file
    ):
        self._write_legacy(_shared_cache_file)

        assert load_lld_tracking(repo_a)["issues"] == {}
        assert load_lld_tracking(repo_b)["issues"] == {}

    def test_legacy_entries_are_preserved_on_disk(
        self, repo_a, _shared_cache_file
    ):
        """Not served is not the same as destroyed -- the operator's file keeps
        its history."""
        self._write_legacy(_shared_cache_file)

        update_lld_status(9, "docs/lld/active/LLD-009.md", APPROVED, repo_a)

        raw = json.loads(_shared_cache_file.read_text(encoding="utf-8"))
        assert raw["legacy_unscoped"]["4"]["final_verdict"] == "APPROVED"
        assert raw["repos"][Path(repo_a).resolve().as_posix()]["issues"]["9"]

    def test_an_unattributable_approval_does_not_skip_review(self, repo_a, _shared_cache_file):
        """The direction that matters. Honouring a legacy approval would skip a
        review the workflow was told to perform; dropping it costs one review."""
        self._write_legacy(_shared_cache_file)

        assert "4" not in load_lld_tracking(repo_a)["issues"]


class TestFileLevelRobustness:
    def test_missing_file_yields_empty_slice(self, repo_a):
        assert load_lld_tracking(repo_a)["issues"] == {}

    def test_corrupt_file_yields_empty_slice(self, repo_a, _shared_cache_file):
        _shared_cache_file.parent.mkdir(parents=True, exist_ok=True)
        _shared_cache_file.write_text("not json {", encoding="utf-8")

        assert load_lld_tracking(repo_a)["issues"] == {}

    def test_non_dict_file_yields_empty_slice(self, repo_a, _shared_cache_file):
        _shared_cache_file.parent.mkdir(parents=True, exist_ok=True)
        _shared_cache_file.write_text("[1, 2, 3]", encoding="utf-8")

        assert load_lld_tracking(repo_a)["issues"] == {}

    def test_save_creates_the_directory(self, repo_a, _shared_cache_file):
        assert not _shared_cache_file.exists()

        save_lld_tracking({"issues": {}}, repo_a)

        assert _shared_cache_file.exists()

    def test_round_trip_through_save_and_load(self, repo_a):
        tracking = load_lld_tracking(repo_a)
        tracking["issues"]["7"] = {
            "lld_path": "docs/lld/active/LLD-007.md",
            "status": "blocked",
            "has_gemini_review": True,
            "final_verdict": "REJECTED",
            "last_review_date": "2026-07-30",
            "review_count": 2,
        }
        save_lld_tracking(tracking, repo_a)

        assert load_lld_tracking(repo_a)["issues"]["7"]["status"] == "blocked"
