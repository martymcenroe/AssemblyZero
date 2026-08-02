"""Acceptance tests for pruning dead LLD status-cache slices (#1971).

The four tests named in the issue body are the acceptance criteria.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from assemblyzero.workflows.requirements.audit import (
    LLD_STATUS_CACHE_VERSION,
    _prune_dead_repo_slices,
    _repo_key,
    lld_status_path,
    load_lld_tracking,
    save_lld_tracking,
)


def _write_cache(target_repo: Path, repos: dict, legacy: dict | None = None) -> Path:
    path = lld_status_path(target_repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": LLD_STATUS_CACHE_VERSION,
        "last_updated": "2026-01-01T00:00:00+00:00",
        "repos": repos,
    }
    if legacy is not None:
        payload["legacy_unscoped"] = legacy
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _slice(issue: str = "7") -> dict:
    return {"issues": {issue: {"status": "approved", "lld_path": f"docs/lld/LLD-{issue}.md"}}}


# --- "dead slice gone, live slice byte-identical" -----------------------


def test_a_dead_slice_is_pruned_and_a_live_one_survives_intact(tmp_path):
    live = tmp_path / "live-repo"
    live.mkdir()
    dead = tmp_path / "deleted-repo"  # never created

    target = tmp_path / "target"
    target.mkdir()

    live_slice = _slice("11")
    _write_cache(target, {
        _repo_key(live): live_slice,
        _repo_key(dead): _slice("99"),
    })

    save_lld_tracking({"version": 1, "last_updated": "x", "issues": {}}, target)

    data = json.loads(lld_status_path(target).read_text(encoding="utf-8"))

    assert _repo_key(dead) not in data["repos"], "a path that is gone cannot be a future target"
    assert data["repos"][_repo_key(live)] == live_slice, "the live slice must be untouched"


def test_the_live_slices_approvals_still_load_after_a_prune(tmp_path):
    live = tmp_path / "live-repo"
    live.mkdir()
    dead = tmp_path / "gone"

    _write_cache(live, {
        _repo_key(live): _slice("11"),
        _repo_key(dead): _slice("99"),
    })

    save_lld_tracking(load_lld_tracking(live), live)

    assert "11" in load_lld_tracking(live)["issues"]


# --- "legacy_unscoped survives a write untouched" -----------------------


def test_legacy_unscoped_is_never_pruned(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    legacy = {"5": {"status": "approved"}}

    _write_cache(target, {_repo_key(tmp_path / "gone"): _slice()}, legacy=legacy)

    save_lld_tracking({"version": 1, "last_updated": "x", "issues": {}}, target)

    data = json.loads(lld_status_path(target).read_text(encoding="utf-8"))
    assert data["legacy_unscoped"] == legacy, (
        "it has no path to test and is retained history, not live cache state"
    )


def test_prune_helper_ignores_legacy_unscoped_entirely():
    raw = {"repos": {}, "legacy_unscoped": {"5": {"status": "approved"}}}
    pruned = _prune_dead_repo_slices(raw, keep="whatever")
    assert pruned == []
    assert raw["legacy_unscoped"] == {"5": {"status": "approved"}}


# --- "a cache with only live slices is unchanged" -----------------------


def test_all_live_slices_are_left_alone(tmp_path):
    a, b = tmp_path / "repo-a", tmp_path / "repo-b"
    a.mkdir()
    b.mkdir()

    raw = {"repos": {_repo_key(a): _slice("1"), _repo_key(b): _slice("2")}}
    before = json.dumps(raw, sort_keys=True)

    pruned = _prune_dead_repo_slices(raw, keep=_repo_key(a))

    assert pruned == []
    assert json.dumps(raw, sort_keys=True) == before, "no gratuitous rewrites"


def test_the_slice_being_written_is_never_pruned(tmp_path):
    """Even if the target somehow fails an existence check mid-run, this run's
    own result must not be discarded underneath it."""
    missing_target = tmp_path / "vanished"
    raw = {"repos": {_repo_key(missing_target): _slice()}}

    pruned = _prune_dead_repo_slices(raw, keep=_repo_key(missing_target))

    assert pruned == []
    assert _repo_key(missing_target) in raw["repos"]


# --- "pruning is logged with the pruned repo path" ----------------------


def test_pruning_names_the_path_it_removed(tmp_path, caplog):
    dead = tmp_path / "deleted-repo"
    raw = {"repos": {_repo_key(dead): _slice()}}

    with caplog.at_level(logging.INFO):
        pruned = _prune_dead_repo_slices(raw, keep="other")

    assert pruned == [_repo_key(dead)]
    assert any(
        _repo_key(dead) in record.getMessage() for record in caplog.records
    ), "an operator seeing an unexpected re-review must be able to find out why"


def test_the_log_says_why_not_just_what(tmp_path, caplog):
    dead = tmp_path / "deleted-repo"
    raw = {"repos": {_repo_key(dead): _slice()}}

    with caplog.at_level(logging.INFO):
        _prune_dead_repo_slices(raw, keep="other")

    combined = " ".join(r.getMessage() for r in caplog.records)
    assert "no longer exists" in combined


# --- robustness -----------------------------------------------------------


def test_a_malformed_repos_key_does_not_raise():
    assert _prune_dead_repo_slices({"repos": "not a dict"}, keep="x") == []
    assert _prune_dead_repo_slices({}, keep="x") == []


def test_growth_is_actually_bounded(tmp_path):
    """The point of the issue: repeated writes must not accumulate dead slices."""
    target = tmp_path / "target"
    target.mkdir()

    repos = {_repo_key(tmp_path / f"gone-{i}"): _slice(str(i)) for i in range(40)}
    repos[_repo_key(target)] = _slice("1")
    _write_cache(target, repos)

    save_lld_tracking(load_lld_tracking(target), target)

    data = json.loads(lld_status_path(target).read_text(encoding="utf-8"))
    assert list(data["repos"]) == [_repo_key(target)], "40 dead slices should be gone"
