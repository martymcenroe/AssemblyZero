"""A halt's files belong to a repository, a mock or a real run, and one run (#4292).

The resume contract, state snapshot and recovery plan were named by workflow
and issue number alone, in one directory for the whole machine. Issue #42 of
one repository and issue #42 of another shared every file, so a contract left
by a halt on one was read by the next spec run on the other; a ``--mock``
run's halt was read by a real run on the same number; and every issue-type
(brief) run shared issue 0.

Each test below builds the halting states by running the real HALT node into
the per-test state directory ``tests/conftest.py`` redirects every binding to
(#3531); nothing here touches the operator's home.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import assemblyzero.core.resume_contract as rc
from assemblyzero.core import halt_paths
from assemblyzero.core.halt_node import create_halt_node
from assemblyzero.core.halt_paths import (
    UnkeyableRun,
    repository_dirname,
    repository_key,
    run_key,
)
from assemblyzero.speedrun.factory_report import read_halt_bundles


def _repo(tmp_path: Path, parent: str, name: str = "app") -> Path:
    """A directory git does not know, which is its own repository root.

    ``parent`` keeps two of the same ``name`` apart: the collision #4292 ends.
    """
    path = tmp_path / parent / name
    path.mkdir(parents=True)
    return path


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _git_repo_with_worktree(tmp_path: Path) -> tuple[Path, Path]:
    primary = _repo(tmp_path, "real", "primary")
    _git("init", "-q", cwd=primary)
    _git("config", "user.email", "t@example.invalid", cwd=primary)
    _git("config", "user.name", "t", cwd=primary)
    (primary / "f.txt").write_text("x", encoding="utf-8")
    _git("add", "f.txt", cwd=primary)
    _git("commit", "-q", "-m", "init", cwd=primary)
    worktree = tmp_path / "real" / "primary-42"
    _git("worktree", "add", "-q", "--detach", str(worktree), cwd=primary)
    return primary, worktree


def _state(repo: Path, issue: int = 42, **extra) -> dict:
    audit = repo / "docs" / "lineage" / "active" / f"{issue}-testing" / "run-1"
    audit.mkdir(parents=True, exist_ok=True)
    return {
        "issue_number": issue,
        "repo_root": str(repo),
        "audit_dir": str(audit),
        "error_message": "Iteration cap: 3 review rounds ended BLOCKED",
        **extra,
    }


def _halt(workflow: str, state: dict) -> dict:
    return create_halt_node(workflow)(state)


def _own_dir(repo: Path, mock: bool = False) -> Path:
    return rc.contract_directory(repo, mock)


def _quiet(_line: str) -> None:
    return None


class TestAContractIsOnlyItsRepositorys:
    """T1 (R1): a contract written for A and issue 42 is not B's issue 42."""

    def test_t1_a_halt_on_a_does_not_verify_or_consume_for_b(
        self, tmp_path, operator_alerts
    ):
        a, b = _repo(tmp_path, "one"), _repo(tmp_path, "two")
        _halt("implementation_spec", _state(a))
        contract_a = rc.contract_path("implementation_spec", 42, _own_dir(a))
        assert contract_a.is_file()
        operator_alerts.clear()

        lines: list[str] = []
        assert rc.check_and_consume(
            "implementation_spec", 42, repo_root=b, log=lines.append
        ) is True
        assert lines == [], "B's run is a fresh run: nothing verified, nothing said"
        assert contract_a.is_file(), "A's contract was not consumed by B's run"
        assert operator_alerts == [], "and B's run was not refused for A's halt"

    def test_t1_a_run_on_a_still_resumes_its_own_halt(self, tmp_path):
        a = _repo(tmp_path, "one")
        _halt("implementation_spec", _state(a))
        contract_a = rc.contract_path("implementation_spec", 42, _own_dir(a))

        lines: list[str] = []
        assert rc.check_and_consume(
            "implementation_spec", 42, repo_root=a, log=lines.append
        ) is True
        assert any("resume contract verified" in line for line in lines)
        assert not contract_a.exists(), "the verified contract is consumed"

    def test_t1_a_contract_for_another_repository_in_this_ones_place_is_refused(
        self, tmp_path, operator_alerts
    ):
        """Only a hand copy, or a directory override, can put it there. It is
        refused by name and left in place; it is never treated as this run's."""
        a, b = _repo(tmp_path, "one"), _repo(tmp_path, "two")
        _halt("implementation_spec", _state(a))
        contract_a = rc.contract_path("implementation_spec", 42, _own_dir(a))
        operator_alerts.clear()

        assert rc.check_and_consume(
            "implementation_spec", 42, repo_root=b,
            directory=contract_a.parent, log=_quiet,
        ) is False
        assert contract_a.is_file()
        assert len(operator_alerts) == 1
        assert repository_key(a) in operator_alerts[0]["cause"]
        assert repository_key(b) in operator_alerts[0]["cause"]

    def test_t1_a_worktree_and_its_primary_checkout_are_one_repository(self, tmp_path):
        primary, worktree = _git_repo_with_worktree(tmp_path)
        assert repository_key(worktree) == repository_key(primary)
        assert repository_dirname(worktree) == repository_dirname(primary)

        _halt("testing", _state(worktree))  # the halt runs in the worktree
        contract = rc.contract_path("testing", 42, _own_dir(primary))
        assert contract.is_file(), "found from the primary checkout"
        lines: list[str] = []
        assert rc.check_and_consume("testing", 42, repo_root=primary, log=lines.append)
        assert any("resume contract verified" in line for line in lines)


class TestAContractFromBeforeTheChange:
    """A contract written before #4292 has no repository field, sits in the
    shared directory under the old name, and is attributed from its audit_dir."""

    def _legacy(self, repo: Path | None, issue: int = 42, audit_dir: str | None = None) -> Path:
        audit = audit_dir if audit_dir is not None else (
            str(repo / "docs" / "lineage" / "active" / f"{issue}-lld" / "t")
        )
        path = rc.STATE_DIR / f"resume-contract-implementation_spec-{issue}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "contract_version": 1, "workflow": "implementation_spec",
            "issue": issue, "halted_at": "2026-10-31T21:30:26+00:00",
            "audit_dir": audit, "inputs": [],
            "counters": {}, "state_snapshot": None,
        }), encoding="utf-8")
        return path

    def test_it_is_not_consumed_by_a_run_on_another_repository(
        self, tmp_path, operator_alerts
    ):
        a, b = _repo(tmp_path, "one"), _repo(tmp_path, "two")
        legacy = self._legacy(a)
        before = legacy.read_bytes()

        lines: list[str] = []
        assert rc.check_and_consume(
            "implementation_spec", 42, repo_root=b, log=lines.append
        ) is True
        assert legacy.read_bytes() == before, "untouched: not moved, not deleted"
        assert any(repository_key(a) in line for line in lines), "and named"
        assert operator_alerts == []

    def test_it_is_still_the_resume_of_the_repository_that_wrote_it(self, tmp_path):
        a = _repo(tmp_path, "one")
        legacy = self._legacy(a)

        lines: list[str] = []
        assert rc.check_and_consume(
            "implementation_spec", 42, repo_root=a, log=lines.append
        ) is True
        assert any("resume contract verified" in line for line in lines)
        assert not legacy.exists(), "consumed, as a verified resume always has"

    def test_a_worktrees_audit_dir_attributes_it_to_the_primary(self, tmp_path):
        primary, worktree = _git_repo_with_worktree(tmp_path)
        legacy = self._legacy(worktree)
        assert rc.check_and_consume(
            "implementation_spec", 42, repo_root=primary, log=_quiet
        ) is True
        assert not legacy.exists()

    def test_one_that_cannot_be_attributed_refuses_by_name(
        self, tmp_path, operator_alerts
    ):
        a = _repo(tmp_path, "one")
        legacy = self._legacy(None, audit_dir="")
        lines: list[str] = []

        assert rc.check_and_consume(
            "implementation_spec", 42, repo_root=a, log=lines.append
        ) is False
        assert legacy.is_file(), "left where it is"
        assert str(legacy) in operator_alerts[0]["cause"]
        assert "cannot be attributed" in operator_alerts[0]["cause"]
        assert any("refusing" in line for line in lines)

    def test_one_whose_repository_git_cannot_read_refuses_by_name(
        self, tmp_path, monkeypatch, operator_alerts
    ):
        a, b = _repo(tmp_path, "one"), _repo(tmp_path, "two")
        legacy = self._legacy(b)
        real = rc.repository_key

        def key(path):
            if Path(path) == b:
                raise OSError("dubious ownership")
            return real(path)

        monkeypatch.setattr(rc, "repository_key", key)
        assert rc.check_and_consume(
            "implementation_spec", 42, repo_root=a, log=_quiet
        ) is False
        assert legacy.is_file()
        assert "dubious ownership" in operator_alerts[0]["cause"]

    def test_one_whose_repository_is_gone_is_not_guessed_at(
        self, tmp_path, operator_alerts
    ):
        a = _repo(tmp_path, "one")
        gone = tmp_path / "removed-worktree"
        self._legacy(None, audit_dir=str(gone / "docs" / "lineage" / "active" / "x"))

        assert rc.check_and_consume(
            "implementation_spec", 42, repo_root=a, log=_quiet
        ) is False
        assert "is gone" in operator_alerts[0]["cause"]

    def test_the_operators_real_files_are_not_rewritten_by_reading_them(self, tmp_path):
        """No migration: a run that reads a legacy contract for another
        repository leaves every byte of the shared directory as it was."""
        a, b = _repo(tmp_path, "one"), _repo(tmp_path, "two")
        legacy = self._legacy(a, issue=462)
        sibling = rc.STATE_DIR / "requirements-462.json"
        sibling.write_text("{}", encoding="utf-8")
        before = {p: p.read_bytes() for p in rc.STATE_DIR.iterdir()}

        rc.check_and_consume("implementation_spec", 462, repo_root=b, log=_quiet)

        assert {p: p.read_bytes() for p in rc.STATE_DIR.iterdir()} == before
        assert legacy.is_file() and sibling.is_file()


class TestHaltFilesDoNotCollideAcrossRepositories:
    """T2 (R2): halts for A#42 and B#42 write distinct paths."""

    def test_t2_two_repositories_of_one_name_write_distinct_paths(self, tmp_path):
        a, b = _repo(tmp_path, "one"), _repo(tmp_path, "two")
        assert a.name == b.name == "app"

        results = {}
        for label, repo in (("a", a), ("b", b)):
            result = _halt("implementation_spec", _state(repo))
            results[label] = {
                "state": Path(result["state_snapshot_path"]),
                "plan": Path(result["recovery_plan_path"]),
                "contract": rc.contract_path(
                    "implementation_spec", 42, _own_dir(repo)
                ),
            }

        for kind in ("state", "plan", "contract"):
            assert results["a"][kind] != results["b"][kind], kind
            assert results["a"][kind].is_file() and results["b"][kind].is_file(), kind
        # Each repository's files are in one directory of its own.
        assert len({p.parent for p in results["a"].values()}) == 1
        assert results["a"]["state"].parent != results["b"]["state"].parent
        # And the second halt did not overwrite the first.
        assert json.loads(results["a"]["state"].read_text(encoding="utf-8"))[
            "repo_root"
        ] == str(a)

    def test_the_directory_name_is_safe_on_windows_and_linux(self, tmp_path):
        weird = _repo(tmp_path, "one", 'a b:c*d?"e<f>g|h. ')
        name = repository_dirname(weird)
        assert not set(name) & set(' :*?"<>|/\\'), name
        assert not name.endswith((".", " "))
        assert len(name) <= 60

    def test_a_halt_that_names_no_repository_stops_and_alerts(
        self, tmp_path, operator_alerts
    ):
        state = _state(_repo(tmp_path, "one"))
        del state["repo_root"]
        with pytest.raises(UnkeyableRun, match="names no repository"):
            _halt("testing", state)
        assert operator_alerts, "the halt could not file itself, and says so"
        assert "could not name its files" in operator_alerts[0]["what"]
        assert not list(rc.STATE_DIR.rglob("*.json")), "nothing filed under a guess"

    def test_the_factory_report_still_finds_a_halts_bundle(self, tmp_path):
        a = _repo(tmp_path, "one")
        _halt("implementation_spec", _state(a))
        found = read_halt_bundles([rc.STATE_DIR], scope_repo=a)
        assert found, "the report reads the per-repository directories"


class TestBriefRunsHaveKeysOfTheirOwn:
    """T3 (R3): an issue-type run has no number; each brief has its own files."""

    def _brief_state(self, repo: Path, brief: str) -> dict:
        (repo / "ideas" / "active").mkdir(parents=True, exist_ok=True)
        (repo / brief).write_text("# brief\n", encoding="utf-8")
        audit = repo / "docs" / "lineage" / "active" / Path(brief).stem
        audit.mkdir(parents=True, exist_ok=True)
        return {
            "issue_number": 0, "brief_file": brief, "repo_root": str(repo),
            "audit_dir": str(audit), "error_message": "Iteration cap: 3 rounds",
        }

    def test_t3_two_briefs_write_distinct_paths(self, tmp_path):
        repo = _repo(tmp_path, "one")
        first = _halt("requirements", self._brief_state(repo, "ideas/active/alpha.md"))
        second = _halt("requirements", self._brief_state(repo, "ideas/active/beta.md"))

        for kind in ("state_snapshot_path", "recovery_plan_path"):
            assert first[kind] != second[kind], kind
            assert Path(first[kind]).is_file() and Path(second[kind]).is_file()
        contracts = sorted(p.name for p in _own_dir(repo).glob("resume-contract-*"))
        assert len(contracts) == 2 and all("-0.json" not in c for c in contracts)
        assert any("alpha" in c for c in contracts) and any("beta" in c for c in contracts)

    def test_t3_two_briefs_of_one_name_in_different_places_differ(self, tmp_path):
        repo = _repo(tmp_path, "one")
        (repo / "x").mkdir()
        (repo / "y").mkdir()
        one = run_key({"repo_root": str(repo), "brief_file": "x/notes.md"})
        two = run_key({"repo_root": str(repo), "brief_file": "y/notes.md"})
        assert one != two and one.startswith("brief-notes-")

    def test_t3_one_brief_rerun_has_the_same_key(self, tmp_path):
        repo = _repo(tmp_path, "one")
        state = {"repo_root": str(repo), "brief_file": "ideas/active/alpha.md"}
        assert run_key(state) == run_key(dict(state))

    def test_t3_an_issue_number_is_its_own_key(self):
        assert run_key({"issue_number": 42}) == "42"

    def test_t3_neither_an_issue_nor_a_brief_has_no_key(self, tmp_path):
        with pytest.raises(UnkeyableRun, match="no issue number and no brief_file"):
            run_key({"issue_number": 0, "repo_root": str(_repo(tmp_path, "one"))})

    def test_t3_the_recovery_plan_names_the_briefs_key_not_zero(self, tmp_path):
        repo = _repo(tmp_path, "one")
        result = _halt("requirements", self._brief_state(repo, "ideas/active/alpha.md"))
        assert "recovery-0-" not in result["recovery_plan_path"]
        assert "recovery-brief-alpha-" in result["recovery_plan_path"]


class TestAMocksHaltNeverReachesARealRun:
    """The comment on #4292: a --mock run's halt must not be a real run's."""

    @pytest.mark.parametrize("flag", [
        {"mock_mode": True},
        {"config_mock_mode": True},
        {"config": {"mock_mode": True}},
    ])
    def test_every_spelling_of_mock_halts_into_the_mock_directory(self, tmp_path, flag):
        repo = _repo(tmp_path, "one")
        result = _halt("testing", _state(repo, **flag))
        assert Path(result["state_snapshot_path"]).parent == _own_dir(repo, True)
        assert rc.contract_path("testing", 42, _own_dir(repo, True)).is_file()
        assert not rc.contract_path("testing", 42, _own_dir(repo, False)).exists()

    def test_a_real_run_does_not_read_a_mocks_contract(self, tmp_path, operator_alerts):
        repo = _repo(tmp_path, "one")
        _halt("testing", _state(repo, mock_mode=True))
        mock_contract = rc.contract_path("testing", 42, _own_dir(repo, True))
        operator_alerts.clear()

        lines: list[str] = []
        assert rc.check_and_consume("testing", 42, repo_root=repo, log=lines.append)
        assert lines == [] and operator_alerts == []
        assert mock_contract.is_file(), "the real run did not consume it"

    def test_a_mock_run_resumes_its_own_halt(self, tmp_path):
        repo = _repo(tmp_path, "one")
        _halt("testing", _state(repo, mock_mode=True))
        lines: list[str] = []
        assert rc.check_and_consume(
            "testing", 42, repo_root=repo, mock=True, log=lines.append
        )
        assert any("resume contract verified" in line for line in lines)

    def test_a_mocks_contract_in_a_real_runs_place_is_refused(
        self, tmp_path, operator_alerts
    ):
        repo = _repo(tmp_path, "one")
        _halt("testing", _state(repo, mock_mode=True))
        mock_dir = _own_dir(repo, True)
        operator_alerts.clear()
        assert rc.check_and_consume(
            "testing", 42, repo_root=repo, directory=mock_dir, log=_quiet
        ) is False
        assert "mock" in operator_alerts[0]["cause"]


def test_state_is_mock_reads_every_workflows_spelling():
    assert not halt_paths.state_is_mock({})
    assert not halt_paths.state_is_mock({"config": {}, "mock_mode": False})
    assert halt_paths.state_is_mock({"mock_mode": True})
