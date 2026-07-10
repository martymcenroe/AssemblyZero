"""Unit tests for tools/fleet_remove_claude_key.py (#1730, generalized #1733).

A scripted fake runner stands in for gh — no live GitHub. The fake maps
(method, path-substring) to canned CompletedProcess results and records
every call so tests can assert exactly which mutations were (not) attempted.
"""
from __future__ import annotations

import base64
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from fleet_remove_claude_key import (  # noqa: E402
    compute_new_content,
    find_existing_pr,
    process_repo,
    wait_for_mergeable,
)


def b64(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


CONFIG_WITH_MODEL = (
    '{\n'
    '  "profile": "default",\n'
    '  "claude": {\n'
    '    "model": "opus",\n'
    '    "effort": "max"\n'
    '  },\n'
    '  "assemblyZero": true\n'
    '}\n'
)

# Post-model-sweep shape: effort is the only claude key left.
CONFIG_WITH_EFFORT = (
    '{\n'
    '  "profile": "default",\n'
    '  "claude": {\n'
    '    "effort": "max"\n'
    '  },\n'
    '  "assemblyZero": true\n'
    '}\n'
)


# ---------------------------------------------------------------------------
# compute_new_content — the pure edit, both keys
# ---------------------------------------------------------------------------

class TestComputeNewContent:
    def test_removes_only_model_preserving_siblings_and_order(self):
        out = compute_new_content(b64(CONFIG_WITH_MODEL), "model")
        cfg = json.loads(out)
        assert "model" not in cfg["claude"]
        assert cfg["claude"]["effort"] == "max"
        assert list(cfg.keys()) == ["profile", "claude", "assemblyZero"]

    def test_removes_only_effort_preserving_siblings_and_order(self):
        out = compute_new_content(b64(CONFIG_WITH_MODEL), "effort")
        cfg = json.loads(out)
        assert "effort" not in cfg["claude"]
        assert cfg["claude"]["model"] == "opus"
        assert list(cfg.keys()) == ["profile", "claude", "assemblyZero"]

    def test_effort_removal_on_post_model_sweep_config_leaves_empty_block(self):
        out = compute_new_content(b64(CONFIG_WITH_EFFORT), "effort")
        assert json.loads(out)["claude"] == {}

    def test_house_style_indent_lf_trailing_newline(self):
        out = compute_new_content(b64(CONFIG_WITH_EFFORT), "effort")
        assert out.endswith("}\n")
        assert "\r" not in out
        assert '  "profile"' in out  # 2-space indent

    def test_none_when_key_absent(self):
        assert compute_new_content(b64(CONFIG_WITH_EFFORT), "model") is None

    def test_none_when_no_claude_block(self):
        cfg = '{\n  "profile": "default"\n}\n'
        assert compute_new_content(b64(cfg), "effort") is None

    def test_none_when_claude_is_not_a_dict(self):
        assert compute_new_content(b64('{\n  "claude": "max"\n}\n'), "effort") is None

    def test_contents_api_wrapped_base64_accepted(self):
        # The Contents API returns base64 with embedded newlines.
        wrapped = "\n".join(
            b64(CONFIG_WITH_MODEL)[i:i + 20]
            for i in range(0, len(b64(CONFIG_WITH_MODEL)), 20)
        )
        out = compute_new_content(wrapped, "model")
        assert "model" not in json.loads(out)["claude"]

    def test_non_ascii_preserved_unescaped(self):
        cfg = '{\n  "claude": {\n    "effort": "max"\n  },\n  "note": "café"\n}\n'
        out = compute_new_content(b64(cfg), "effort")
        assert "café" in out
        assert "\\u" not in out


# ---------------------------------------------------------------------------
# Fake gh runner
# ---------------------------------------------------------------------------

class FakeRunner:
    """Maps (method, path-substring) -> response; records every gh argv."""

    def __init__(self, routes: list[tuple[str, str, int, object]]):
        self.routes = routes
        self.calls: list[list[str]] = []
        self.inputs: list = []  # index-aligned with calls: the stdin payloads

    def __call__(self, cmd, *, timeout=0, input=None):
        self.calls.append(list(cmd))
        self.inputs.append(input)
        path = cmd[2]
        method = "GET"
        if "-X" in cmd:
            method = cmd[cmd.index("-X") + 1]
        for m, frag, rc, body in self.routes:
            if m == method and frag in path:
                stdout = body if isinstance(body, str) else json.dumps(body)
                stderr = "HTTP 404: Not Found" if rc != 0 else ""
                return subprocess.CompletedProcess(cmd, rc, stdout, stderr)
        raise AssertionError(f"unrouted gh call: {method} {path}")

    def mutations(self) -> list[list[str]]:
        return [c for c in self.calls if "-X" in c]


REPO_META = {"default_branch": "main"}
CONTENTS_EFFORT = {"content": b64(CONFIG_WITH_EFFORT), "sha": "abc123"}


# ---------------------------------------------------------------------------
# process_repo — skip paths and dry-run safety (driven with key=effort)
# ---------------------------------------------------------------------------

class TestSkipPaths:
    def test_missing_repo_skips(self):
        r = FakeRunner([("GET", "repos/martymcenroe/ghost", 1, "")])
        assert "not found" in process_repo(r, "ghost", apply=True, key="effort")
        assert r.mutations() == []

    def test_missing_config_file_skips(self):
        r = FakeRunner([
            ("GET", "/contents/", 1, ""),
            ("GET", "repos/martymcenroe/bare", 0, REPO_META),
        ])
        assert ".unleashed.json" in process_repo(r, "bare", apply=True, key="effort")
        assert r.mutations() == []

    def test_key_already_absent_skips(self):
        clean = {"content": b64('{\n  "claude": {}\n}\n'), "sha": "abc"}
        r = FakeRunner([
            ("GET", "/contents/", 0, clean),
            ("GET", "repos/martymcenroe/done", 0, REPO_META),
        ])
        out = process_repo(r, "done", apply=True, key="effort")
        assert "claude.effort already absent" in out
        assert r.mutations() == []

    def test_open_pr_from_prior_run_same_key_skips(self):
        r = FakeRunner([
            ("GET", "/contents/", 0, CONTENTS_EFFORT),
            ("GET", "/pulls?state=open", 0,
             [{"number": 7, "head": {"ref": "5-remove-claude-effort"}}]),
            ("GET", "repos/martymcenroe/mid", 0, REPO_META),
        ])
        assert "open PR #7" in process_repo(r, "mid", apply=True, key="effort")
        assert r.mutations() == []

    def test_open_pr_for_other_key_does_not_block(self):
        # A leftover model-sweep PR must not mask the effort sweep.
        r = FakeRunner([
            ("GET", "/contents/", 0, CONTENTS_EFFORT),
            ("GET", "/pulls?state=open", 0,
             [{"number": 7, "head": {"ref": "5-remove-claude-model"}}]),
            ("GET", "repos/martymcenroe/mid", 0, REPO_META),
        ])
        out = process_repo(r, "mid", apply=False, key="effort")
        assert out.startswith("dry-run")

    def test_dry_run_issues_no_mutating_calls(self):
        r = FakeRunner([
            ("GET", "/contents/", 0, CONTENTS_EFFORT),
            ("GET", "/pulls?state=open", 0, []),
            ("GET", "repos/martymcenroe/live", 0, REPO_META),
        ])
        out = process_repo(r, "live", apply=False, key="effort")
        assert out.startswith("dry-run")
        assert r.mutations() == []


# ---------------------------------------------------------------------------
# process_repo — happy path (key=effort)
# ---------------------------------------------------------------------------

class TestHappyPath:
    def _runner(self) -> FakeRunner:
        return FakeRunner([
            ("GET", "/contents/", 0, CONTENTS_EFFORT),
            ("GET", "/pulls?state=open", 0, []),
            ("POST", "/issues", 0, {"number": 41}),
            ("GET", "/git/ref/heads/main", 0, {"object": {"sha": "f" * 40}}),
            ("POST", "/git/refs", 0, {}),
            ("PUT", "/contents/", 0, {}),
            ("POST", "/pulls", 0, {"number": 42}),
            ("PUT", "/pulls/42/merge", 0, {"merged": True}),
            ("GET", "/pulls/42", 0,
             {"mergeable_state": "clean", "merged": True,
              "merge_commit_sha": "deadbeefcafe"}),
            ("GET", "repos/martymcenroe/live", 0, REPO_META),
        ])

    def test_full_cycle_reports_issue_pr_and_squash(self):
        out = process_repo(self._runner(), "live", apply=True, key="effort")
        assert out == "merged: issue #41, PR #42, squash deadbeef"

    def test_branch_named_after_issue_and_key(self):
        r = self._runner()
        process_repo(r, "live", apply=True, key="effort")
        ref_idx = [i for i, c in enumerate(r.calls) if c[2].endswith("/git/refs")]
        assert len(ref_idx) == 1
        payload = json.loads(r.inputs[ref_idx[0]])
        assert payload["ref"] == "refs/heads/41-remove-claude-effort"

    def test_no_force_tokens_in_any_gh_argv(self):
        r = self._runner()
        process_repo(r, "live", apply=True, key="effort")
        banned = {"-D", "--force", "--force-with-lease", "--admin", "--no-verify"}
        for call in r.calls:
            assert not banned.intersection(call), call

    def test_unstable_state_is_mergeable(self):
        r = self._runner()
        r.routes.insert(0, ("GET", "/pulls/42", 0,
                            {"mergeable_state": "unstable", "merged": True,
                             "merge_commit_sha": "deadbeefcafe"}))
        out = process_repo(r, "live", apply=True, key="effort")
        assert out.startswith("merged:")


# ---------------------------------------------------------------------------
# wait_for_mergeable — bounded poll
# ---------------------------------------------------------------------------

class TestWaitForMergeable:
    def test_dirty_short_circuits(self):
        r = FakeRunner([("GET", "/pulls/9", 0, {"mergeable_state": "dirty"})])
        assert wait_for_mergeable(r, "x", 9) == "dirty"

    def test_timeout_reports_last_state(self):
        r = FakeRunner([("GET", "/pulls/9", 0, {"mergeable_state": "blocked"})])
        clock = iter([0, 5, 10, 999]).__next__
        out = wait_for_mergeable(r, "x", 9, timeout_s=12,
                                 sleep=lambda s: None, clock=clock)
        assert out == "timeout:blocked"


# ---------------------------------------------------------------------------
# find_existing_pr — key-scoped suffix matching
# ---------------------------------------------------------------------------

def test_find_existing_pr_matches_requested_key_only():
    r = FakeRunner([
        ("GET", "/pulls?state=open", 0,
         [{"number": 3, "head": {"ref": "12-remove-claude-model"}},
          {"number": 4, "head": {"ref": "13-remove-claude-effort"}}]),
    ])
    assert find_existing_pr(r, "x", "effort") == 4
    assert find_existing_pr(r, "x", "model") == 3


def test_find_existing_pr_none_when_no_match():
    r = FakeRunner([("GET", "/pulls?state=open", 0, [])])
    assert find_existing_pr(r, "x", "effort") is None
