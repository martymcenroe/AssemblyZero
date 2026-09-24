"""ADR 0217's graft recipe, run for real (#3185).

The recipe's step 2b used to set the orphan's upstream only when the checkout
was parked on another branch. With HEAD on main but local main NOT fast-
forwarded past the squash, HEAD cannot reach the graft either, so step 3's
`git branch -d` refused and git's hint pointed at the banned `-D`. Step 2b now
keys on "can HEAD reach the squash". These tests build that exact state against
a real bare remote and run the recipe's steps.
"""

import subprocess
from pathlib import Path


def git(*args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "init.defaultBranch=main", *args],
        cwd=cwd,
        check=check,
        capture_output=True,
        text=True,
    )


def squash_merged_orphan(tmp_path: Path) -> tuple[Path, str, str]:
    """A clone with local branch `7-x` squash-merged on the remote. Returns (repo, orphan tip, squash)."""
    remote, repo, other = tmp_path / "remote.git", tmp_path / "repo", tmp_path / "other"
    git("init", "--bare", str(remote), cwd=tmp_path)
    git("clone", "-q", str(remote), str(repo), cwd=tmp_path)
    (repo / "a.txt").write_text("a\n")
    git("add", "a.txt", cwd=repo)
    git("commit", "-q", "-m", "init", cwd=repo)
    git("push", "-q", "origin", "main", cwd=repo)
    git("switch", "-q", "-c", "7-x", cwd=repo)
    (repo / "x.txt").write_text("x\n")
    git("add", "x.txt", cwd=repo)
    git("commit", "-q", "-m", "work", cwd=repo)
    tip = git("rev-parse", "HEAD", cwd=repo).stdout.strip()
    git("switch", "-q", "main", cwd=repo)
    # The squash lands on the remote from elsewhere; this clone's local main stays behind.
    git("clone", "-q", str(remote), str(other), cwd=tmp_path)
    (other / "x.txt").write_text("x\n")
    git("add", "x.txt", cwd=other)
    git("commit", "-q", "-m", "squash 7-x", cwd=other)
    git("push", "-q", "origin", "main", cwd=other)
    git("fetch", "-q", "--prune", "origin", cwd=repo)
    squash = git("rev-parse", "origin/main", cwd=repo).stdout.strip()
    return repo, tip, squash


def run_recipe(repo: Path, tip: str, squash: str) -> subprocess.CompletedProcess:
    """Steps 1-5 as the ADR writes them, step 4 unconditional."""
    pre = git("replace", "--list", cwd=repo).stdout.split()
    base = git("rev-parse", f"{squash}^", cwd=repo).stdout.strip()
    git("replace", "--graft", squash, base, tip, cwd=repo)
    if git("merge-base", "--is-ancestor", squash, "HEAD", cwd=repo, check=False).returncode != 0:  # step 2b
        git("branch", "--set-upstream-to=origin/main", "7-x", cwd=repo)
    deleted = git("branch", "-d", "7-x", cwd=repo, check=False)
    git("replace", "-d", squash, cwd=repo)
    assert git("replace", "--list", cwd=repo).stdout.split() == pre  # step 5: no residue
    return deleted


def branches(repo: Path) -> list[str]:
    return git("for-each-ref", "--format=%(refname:short)", "refs/heads", cwd=repo).stdout.split()


def test_stale_local_main_deletes_without_force(tmp_path):
    repo, tip, squash = squash_merged_orphan(tmp_path)
    assert git("branch", "--show-current", cwd=repo).stdout.strip() == "main"
    assert git("merge-base", "--is-ancestor", squash, "HEAD", cwd=repo, check=False).returncode != 0
    result = run_recipe(repo, tip, squash)
    assert result.returncode == 0, result.stderr
    assert "7-x" not in branches(repo)


def test_the_old_condition_refused_this_state(tmp_path):
    """Without step 2b the refusal is exactly #3185's, hint included; and step 4 still leaves no residue."""
    repo, tip, squash = squash_merged_orphan(tmp_path)
    base = git("rev-parse", f"{squash}^", cwd=repo).stdout.strip()
    git("replace", "--graft", squash, base, tip, cwd=repo)
    refused = git("branch", "-d", "7-x", cwd=repo, check=False)
    git("replace", "-d", squash, cwd=repo)
    assert refused.returncode != 0 and "not fully merged" in refused.stderr
    assert "7-x" in branches(repo)
    assert git("replace", "--list", cwd=repo).stdout.strip() == ""


def test_up_to_date_main_needs_no_upstream(tmp_path):
    repo, tip, squash = squash_merged_orphan(tmp_path)
    git("merge", "-q", "--ff-only", "origin/main", cwd=repo)
    assert run_recipe(repo, tip, squash).returncode == 0
    assert "7-x" not in branches(repo)
