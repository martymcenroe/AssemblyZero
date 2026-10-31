"""A checkpoint in a repository that ignores data/ commits its work (#3585).

`commit_checkpoint` excludes workflow-internal paths (`EXCLUDED_PATHS`) from
`git add -A`. Naming a path the repository already ignores in a pathspec makes
`git add` exit 1 ("The following paths are ignored"), though nothing is wrong:
`-A` never stages an ignored file. Since #3810 a failed `git add` raises, so
every checkpoint in a repository that ignores `data/` (most of them) halted
the run. Only the excluded paths the repository does not ignore are excluded.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from assemblyzero.workflows.testing.checkpoints import commit_checkpoint


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True,
    ).stdout


def _repo(tmp_path: Path, gitignore: str) -> Path:
    repo = tmp_path / "target"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / ".gitignore").write_text(gitignore, encoding="utf-8")
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "base")
    return repo


def test_a_repository_that_ignores_data_still_gets_its_checkpoint(tmp_path):
    repo = _repo(tmp_path, "data/\n")
    (repo / "work.py").write_text("x = 1\n", encoding="utf-8")
    (repo / "data" / "lineage").mkdir(parents=True)
    (repo / "data" / "lineage" / "draft.md").write_text("lineage\n", encoding="utf-8")

    assert commit_checkpoint(repo, 42, "post-scaffold") is True

    committed = _git(repo, "show", "--name-only", "--format=", "HEAD").split()
    assert committed == ["work.py"]


def test_an_excluded_path_the_repository_does_not_ignore_is_still_excluded(tmp_path):
    repo = _repo(tmp_path, "")
    (repo / "work.py").write_text("x = 1\n", encoding="utf-8")
    (repo / ".assemblyzero").mkdir()
    (repo / ".assemblyzero" / "state.json").write_text("{}\n", encoding="utf-8")

    assert commit_checkpoint(repo, 42, "post-impl") is True

    committed = _git(repo, "show", "--name-only", "--format=", "HEAD").split()
    assert committed == ["work.py"]
