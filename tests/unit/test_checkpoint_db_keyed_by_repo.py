"""A real run's checkpoint database is keyed by repository and issue (#3548).

Until 2026-09-24 it was `~/.assemblyzero/testing_{issue}.db`, keyed by the
issue alone, so two target repositories that each had an issue 42 shared one
database and a `--resume` in one could load the other's checkpoints. #3547
moved the `--mock` database into the target's `data/mock-runs/`; this moves
the real one into the target's `data/speedrun/checkpoints/`, following
#1970's reasoning for the LLD approval cache.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.run_implement_from_lld import (
    checkpoint_db_for_run,
    get_checkpoint_db_path,
    legacy_checkpoint_db_path,
    legacy_checkpoint_notice,
)


@pytest.fixture(autouse=True)
def _no_env_override(monkeypatch):
    monkeypatch.delenv("ASSEMBLYZERO_WORKFLOW_DB", raising=False)


@pytest.fixture
def two_repos(tmp_path) -> tuple[Path, Path]:
    a = tmp_path / "repo-a"
    b = tmp_path / "repo-b"
    a.mkdir()
    b.mkdir()
    return a, b


@pytest.fixture
def fake_home(tmp_path, monkeypatch) -> Path:
    home = tmp_path / "home"
    (home / ".assemblyzero").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    return home


class TestKeyedByRepositoryAndIssue:
    """Requirement 1."""

    def test_two_repositories_running_issue_42_get_different_databases(self, two_repos):
        a, b = two_repos

        path_a = checkpoint_db_for_run(None, 42, False, a)
        path_b = checkpoint_db_for_run(None, 42, False, b)

        assert path_a != path_b
        assert path_a == a / "data" / "speedrun" / "checkpoints" / "testing_42.db"
        assert path_b == b / "data" / "speedrun" / "checkpoints" / "testing_42.db"

    def test_a_resume_in_one_repository_cannot_read_the_other(self, two_repos):
        """Acceptance: repo A's run leaves its database; repo B's path for the
        same issue is a different file that does not exist."""
        a, b = two_repos
        path_a = checkpoint_db_for_run(None, 42, False, a)
        path_a.write_bytes(b"repo A's checkpoints")

        path_b = checkpoint_db_for_run(None, 42, False, b)

        assert not path_b.exists()
        assert path_a.read_bytes() == b"repo A's checkpoints"

    def test_the_directory_is_created_under_the_target(self, two_repos):
        a, _ = two_repos

        path = get_checkpoint_db_path(42, a)

        assert path.parent.is_dir()
        assert path.parent == a / "data" / "speedrun" / "checkpoints"

    def test_nothing_lands_in_the_home_directory(self, two_repos, fake_home):
        a, _ = two_repos

        checkpoint_db_for_run(None, 42, False, a)

        assert list((fake_home / ".assemblyzero").iterdir()) == []


class TestTheOverridesStillWin:
    """Requirement 2."""

    def test_the_environment_variable_wins(self, two_repos, tmp_path, monkeypatch):
        a, _ = two_repos
        override = tmp_path / "elsewhere" / "custom.db"
        monkeypatch.setenv("ASSEMBLYZERO_WORKFLOW_DB", str(override))

        assert checkpoint_db_for_run(None, 42, False, a) == override

    def test_db_path_wins_over_everything(self, two_repos, tmp_path, monkeypatch):
        a, _ = two_repos
        monkeypatch.setenv("ASSEMBLYZERO_WORKFLOW_DB", str(tmp_path / "env.db"))
        chosen = tmp_path / "chosen.db"

        assert checkpoint_db_for_run(str(chosen), 42, False, a) == chosen

    def test_a_mock_run_is_unchanged(self, two_repos):
        """#3547's location, untouched."""
        a, _ = two_repos

        assert checkpoint_db_for_run(None, 42, True, a) == (
            a / "data" / "mock-runs" / "impl-42" / "checkpoints.db"
        )


class TestTheLegacyDatabaseIsNamedAndIgnored:
    """Requirement 3: an existing ~/.assemblyzero/testing_{issue}.db is not
    silently read for a different repository."""

    def test_it_is_never_the_default_even_when_it_exists(self, two_repos, fake_home):
        a, _ = two_repos
        legacy = fake_home / ".assemblyzero" / "testing_42.db"
        legacy.write_bytes(b"some other repository's checkpoints")

        assert checkpoint_db_for_run(None, 42, False, a) != legacy
        assert legacy_checkpoint_db_path(42) == legacy

    def test_the_run_names_it_and_the_flag_that_would_use_it(self, fake_home):
        legacy = fake_home / ".assemblyzero" / "testing_42.db"
        legacy.write_bytes(b"x")

        notice = legacy_checkpoint_notice(42, None, False)

        assert notice is not None
        assert str(legacy) in notice
        assert "Ignoring" in notice
        assert f"--db-path {legacy}" in notice

    def test_no_notice_when_it_does_not_exist(self, fake_home):
        assert legacy_checkpoint_notice(42, None, False) is None

    def test_no_notice_when_the_run_chose_its_database(self, fake_home):
        (fake_home / ".assemblyzero" / "testing_42.db").write_bytes(b"x")

        assert legacy_checkpoint_notice(42, "/somewhere/else.db", False) is None

    def test_no_notice_for_a_mock_run(self, fake_home):
        (fake_home / ".assemblyzero" / "testing_42.db").write_bytes(b"x")

        assert legacy_checkpoint_notice(42, None, True) is None

    def test_issue_zero_names_the_generic_file(self, fake_home):
        assert legacy_checkpoint_db_path(0) == fake_home / ".assemblyzero" / "testing_workflow.db"
