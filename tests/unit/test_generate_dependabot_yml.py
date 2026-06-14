"""Unit tests for tools/generate_dependabot_yml.py (#1569).

All network is mocked — no real GitHub calls, no PAT decryption. Lives in
tests/unit/ so CI's fast gate runs it (#1580).
"""
import base64
import re
import sys
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import generate_dependabot_yml as g  # noqa: E402

# The exact parasitic regex pr-sentinel uses to extract Closes directives.
SENTINEL_RE = re.compile(r"\b(close[sd]?)\s+#(\d+)", re.IGNORECASE)


def _resp(status_code=200, json_data=None):
    m = mock.Mock()
    m.status_code = status_code
    m.json.return_value = json_data or {}
    m.raise_for_status = mock.Mock()
    return m


# ── render reuse ─────────────────────────────────────────────────────


def test_render_reuses_scaffolder_format():
    """The backfilled file is byte-identical to what new_repo_setup emits."""
    ecosystems = g.ecosystems_for_markers({"pyproject.toml"})
    content = g.render_dependabot_yml(ecosystems)
    assert content.startswith("# Dependabot version-update configuration.")
    assert "version: 2" in content
    assert 'package-ecosystem: "pip"' in content
    assert 'package-ecosystem: "github-actions"' in content
    # No marker -> npm/docker absent.
    assert 'package-ecosystem: "npm"' not in content


def test_ecosystems_for_markers_order_and_github_actions():
    """Order follows _DEPENDABOT_ECOSYSTEMS; github-actions always last."""
    out = g.ecosystems_for_markers({"Dockerfile", "pyproject.toml"})
    assert out == [
        ("pip", "python"),
        ("docker", "docker"),
        ("github-actions", "github-actions"),
    ]
    # Empty marker set still yields github-actions.
    assert g.ecosystems_for_markers(set()) == [("github-actions", "github-actions")]


# ── HTTP helpers ─────────────────────────────────────────────────────


def test_file_exists_on_branch_404_is_false():
    with mock.patch.object(g.requests, "get", return_value=_resp(404)):
        assert g.file_exists_on_branch("r", "x", "main", "pat") is False


def test_file_exists_on_branch_200_is_true():
    with mock.patch.object(g.requests, "get", return_value=_resp(200, {"sha": "a"})):
        assert g.file_exists_on_branch("r", "x", "main", "pat") is True


def test_put_new_file_normalizes_crlf_and_sends_no_sha():
    with mock.patch.object(g.requests, "put", return_value=_resp(201)) as put:
        g.put_new_file_on_branch("r", "p", "a\r\nb\r\n", "msg", "br", "pat")
    body = put.call_args.kwargs["json"]
    assert "sha" not in body  # create, not update
    assert body["branch"] == "br"
    decoded = base64.b64decode(body["content"]).decode("utf-8")
    assert decoded == "a\nb\n"  # CRLF normalized to LF


def test_merge_pr_returns_sha():
    with mock.patch.object(g.requests, "put", return_value=_resp(200, {"sha": "deadbeef"})):
        assert g.merge_pr("r", 1, "pat") == "deadbeef"


def test_wait_for_mergeable_accepts_unstable():
    with mock.patch.object(g, "get_mergeable_state", side_effect=["unknown", "unstable"]):
        state = g.wait_for_mergeable("r", 1, "pat", timeout_s=100, sleep_fn=lambda *_: None)
    assert state == "unstable"


def test_wait_for_mergeable_returns_dirty_immediately():
    with mock.patch.object(g, "get_mergeable_state", return_value="dirty") as gms:
        state = g.wait_for_mergeable("r", 1, "pat", timeout_s=100, sleep_fn=lambda *_: None)
    assert state == "dirty"
    assert gms.call_count == 1


# ── ecosystem detection over the API ─────────────────────────────────


def test_detect_ecosystems_via_api_probes_markers():
    def fake_exists(repo, path, branch, pat):
        return path == "pyproject.toml"

    with mock.patch.object(g, "file_exists_on_branch", side_effect=fake_exists):
        out = g.detect_ecosystems_via_api("r", "main", "pat")
    assert out == [("pip", "python"), ("github-actions", "github-actions")]


# ── process_repo orchestration ───────────────────────────────────────


def _patch_repo_io(file_exists=False, existing_pr=None, ecosystems=None):
    """Patch every per-repo IO function. Returns the ExitStack-managed mocks."""
    ecosystems = ecosystems or [("pip", "python"), ("github-actions", "github-actions")]
    patches = {
        "get_default_branch": mock.patch.object(g, "get_default_branch", return_value="main"),
        "file_exists_on_branch": mock.patch.object(g, "file_exists_on_branch", return_value=file_exists),
        "find_existing_backfill_pr": mock.patch.object(g, "find_existing_backfill_pr", return_value=existing_pr),
        "detect_ecosystems_via_api": mock.patch.object(g, "detect_ecosystems_via_api", return_value=ecosystems),
        "create_issue": mock.patch.object(g, "create_issue", return_value=42),
        "get_branch_head": mock.patch.object(g, "get_branch_head", return_value="basesha"),
        "create_branch": mock.patch.object(g, "create_branch"),
        "put_new_file_on_branch": mock.patch.object(g, "put_new_file_on_branch"),
        "create_pr": mock.patch.object(g, "create_pr", return_value=99),
        "wait_for_mergeable": mock.patch.object(g, "wait_for_mergeable", return_value="clean"),
        "merge_pr": mock.patch.object(g, "merge_pr", return_value="mergesha0"),
    }
    return patches


def test_process_repo_dry_run_makes_no_mutations():
    patches = _patch_repo_io()
    with patches["get_default_branch"], patches["file_exists_on_branch"], \
         patches["find_existing_backfill_pr"], patches["detect_ecosystems_via_api"], \
         patches["create_issue"] as create_issue, patches["create_pr"] as create_pr, \
         patches["put_new_file_on_branch"] as put_file, patches["merge_pr"] as merge:
        result = g.process_repo("career", "pat", apply=False)
    assert result.ok and not result.skipped
    assert result.status.startswith("WOULD create")
    create_issue.assert_not_called()
    create_pr.assert_not_called()
    put_file.assert_not_called()
    merge.assert_not_called()


def test_process_repo_skips_when_file_exists():
    patches = _patch_repo_io(file_exists=True)
    with patches["get_default_branch"], patches["file_exists_on_branch"], \
         patches["find_existing_backfill_pr"], patches["create_issue"] as create_issue:
        result = g.process_repo("career", "pat", apply=True)
    assert result.skipped and result.ok
    assert "already has" in result.status
    create_issue.assert_not_called()


def test_process_repo_skips_when_open_pr_exists():
    patches = _patch_repo_io(file_exists=False, existing_pr=7)
    with patches["get_default_branch"], patches["file_exists_on_branch"], \
         patches["find_existing_backfill_pr"], patches["create_issue"] as create_issue:
        result = g.process_repo("career", "pat", apply=True)
    assert result.skipped and result.ok
    assert "#7" in result.status
    create_issue.assert_not_called()


def test_process_repo_apply_full_flow_and_pr_body_is_sentinel_safe():
    patches = _patch_repo_io()
    with patches["get_default_branch"], patches["file_exists_on_branch"], \
         patches["find_existing_backfill_pr"], patches["detect_ecosystems_via_api"], \
         patches["create_issue"], patches["get_branch_head"], \
         patches["create_branch"] as create_branch, \
         patches["put_new_file_on_branch"] as put_file, \
         patches["create_pr"] as create_pr, patches["wait_for_mergeable"], \
         patches["merge_pr"] as merge:
        result = g.process_repo("career", "pat", apply=True)

    assert result.ok and not result.skipped
    # Branch named off the issue number.
    create_branch.assert_called_once()
    assert create_branch.call_args.args[1] == "42-add-dependabot-yml"
    # File content is the rendered yml.
    put_content = put_file.call_args.args[2]
    assert "version: 2" in put_content
    # PR body closes exactly the new issue, and the sentinel regex finds
    # exactly ONE match (no parasitic extraction of the AZ#1569 cross-ref).
    pr_body = create_pr.call_args.args[4]
    matches = SENTINEL_RE.findall(pr_body)
    assert matches == [("Closes", "42")]
    assert "AssemblyZero#1569" in pr_body  # cross-ref present but not a trigger
    merge.assert_called_once()
    assert "#99" in result.status


# ── CLI ──────────────────────────────────────────────────────────────


@contextmanager
def _fake_pat():
    yield "faketoken"


def test_main_dry_run_single_repo_exits_zero():
    with mock.patch.object(g, "classic_pat_session", _fake_pat), \
         mock.patch.object(g, "process_repo",
                           return_value=g.BackfillResult("foo", "WOULD create ...", ok=True)) as pr:
        rc = g.main(["--repo", "martymcenroe/foo"])
    assert rc == 0
    # Owner stripped before processing.
    assert pr.call_args.args[0] == "foo"


def test_main_rejects_repo_without_slash():
    rc = g.main(["--repo", "noslash"])
    assert rc == 1


def test_main_returns_2_on_per_repo_error():
    with mock.patch.object(g, "classic_pat_session", _fake_pat), \
         mock.patch.object(g, "process_repo",
                           return_value=g.BackfillResult("foo", "ERROR: boom", ok=False)):
        rc = g.main(["--repo", "martymcenroe/foo"])
    assert rc == 2
