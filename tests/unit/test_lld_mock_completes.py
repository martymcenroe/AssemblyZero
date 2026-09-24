"""`--mock` finishes an LLD run (#3533).

The mock drafter returned an issue-shaped document with no `### 2.1`,
`## 11` or `## 12`, so N1.5 rejected every draft and a mock run halted at the
draft cap. `--mock` never reached review or finalize, so it rehearsed none of
the write path. These run the real tool.
"""
from __future__ import annotations

import io
import subprocess
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert result.returncode == 0, f"git {' '.join(args)}: {result.stderr}"
    return result


@pytest.fixture(autouse=True)
def _state_dir(tmp_path, monkeypatch):
    """Keep any halt snapshot out of the real ~/.assemblyzero (#3531)."""
    from assemblyzero.core import resume_contract, state_persistence

    state = tmp_path / "workflow_state"
    monkeypatch.setattr(state_persistence, "STATE_DIR", state)
    monkeypatch.setattr(resume_contract, "STATE_DIR", state)


@pytest.fixture
def target_repo(tmp_path: Path) -> Path:
    origin = tmp_path / "origin.git"
    subprocess.run(
        ["git", "init", "-q", "--bare", "--initial-branch=main", str(origin)],
        capture_output=True, text=True, check=True,
    )
    root = tmp_path / "target"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "Test")
    (root / ".gitignore").write_text("data/\n", encoding="utf-8")
    (root / "README.md").write_text("base\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "base")
    _git(root, "remote", "add", "origin", str(origin))
    _git(root, "push", "-qu", "origin", "main")
    return root


def _generate_draft_module():
    """The module, not the function: the nodes package re-exports the
    function under the module's own name."""
    import importlib

    return importlib.import_module(
        "assemblyzero.workflows.requirements.nodes.generate_draft"
    )


def _run_mock(target: Path) -> tuple[int, str]:
    from tools.run_requirements_workflow import main

    argv = [
        "prog", "--type", "lld", "--issue", "42", "--mock", "--yes",
        "--review", "none", "--repo", str(target), "--base-branch", "main",
    ]
    out = io.StringIO()
    with patch("sys.argv", argv), patch(
        "tools.run_requirements_workflow.resolve_roots",
        return_value=(ROOT, target),
    ), redirect_stdout(out):
        rc = main()
    return rc, out.getvalue()


class TestMockFinishesAnLLDRun:
    def test_a_mock_lld_run_reaches_finalize_and_writes_the_lld(self, target_repo):
        rc, out = _run_mock(target_repo)

        assert "MECHANICAL VALIDATION FAILED" not in out, out
        assert rc == 0, out
        written = list(target_repo.rglob("LLD-042.md"))
        assert written, out

    def test_an_explicit_mock_draft_drafter_keeps_the_failing_draft(self, tmp_path):
        """The e2e loop-to-halt harness names `mock:draft`; it still gets it."""
        gd = _generate_draft_module()
        from assemblyzero.workflows.requirements.state import create_initial_state

        template_dir = tmp_path / "docs" / "templates"
        template_dir.mkdir(parents=True)
        (template_dir / "0102-feature-lld-template.md").write_text("# T", encoding="utf-8")
        state = create_initial_state(
            workflow_type="lld", assemblyzero_root=str(tmp_path),
            target_repo=str(tmp_path), issue_number=42, mock_mode=True,
            drafter="mock:draft",
        )
        state["issue_text"] = "# Issue"
        state["audit_dir"] = str(tmp_path / "audit")

        provider = Mock()
        provider.invoke.return_value = Mock(
            success=True, response="# Draft", error_message=None,
            input_tokens=0, output_tokens=0,
        )
        with patch.object(gd, "get_provider", return_value=provider) as gp:
            gd.generate_draft(state)

        assert gp.call_args.args[0] == "mock:draft"

    def test_the_default_mock_lld_drafter_is_mock_lld(self, tmp_path):
        gd = _generate_draft_module()
        from assemblyzero.workflows.requirements.state import create_initial_state

        template_dir = tmp_path / "docs" / "templates"
        template_dir.mkdir(parents=True)
        (template_dir / "0102-feature-lld-template.md").write_text("# T", encoding="utf-8")
        state = create_initial_state(
            workflow_type="lld", assemblyzero_root=str(tmp_path),
            target_repo=str(tmp_path), issue_number=42, mock_mode=True,
        )
        state["issue_text"] = "# Issue"
        state["audit_dir"] = str(tmp_path / "audit")

        provider = Mock()
        provider.invoke.return_value = Mock(
            success=True, response="# Draft", error_message=None,
            input_tokens=0, output_tokens=0,
        )
        with patch.object(gd, "get_provider", return_value=provider) as gp:
            gd.generate_draft(state)

        assert gp.call_args.args[0] == "mock:lld"
