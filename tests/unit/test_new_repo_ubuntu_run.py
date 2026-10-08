"""
new_repo.py run from Ubuntu: where it builds, and whether it admits failure.

Diagnosed from the first Ubuntu run, 2026-10-07 at 6:42 PM Central:

- #4132: the Projects root came back in its Windows spelling, a relative path
  on Linux. The config's sanitizer resolved it against the current directory,
  so the repository was built inside the AssemblyZero checkout.
- #4136: the run then printed [SUCCESS] although the GitHub repo, the push,
  the settings, branch protection and the hook install had all failed.

Issues: #4132, #4136
"""

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "tools"))

import new_repo
from new_repo import (
    failed_steps,
    resolve_project_path,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


# ===========================================================================
# #4132 — where the repository is built
# ===========================================================================


class TestResolveProjectPath:

    def test_real_config_gives_an_absolute_path_beside_this_checkout(self):
        """T1. On any OS, the target is <checkout's parent>/<name>."""
        target = resolve_project_path("foo")
        assert target.is_absolute()
        assert target == REPO_ROOT.parent / "foo"

    def test_asks_for_the_spelling_of_this_os(self, tmp_path):
        with patch.object(new_repo.config, "projects_root",
                          return_value=str(tmp_path)) as root:
            assert resolve_project_path("foo") == tmp_path / "foo"
        root.assert_called_once_with(fmt="auto")

    def test_refuses_a_relative_root(self, tmp_path, monkeypatch):
        """T2. A relative root is refused before anything is created."""
        monkeypatch.chdir(tmp_path)
        with patch.object(new_repo.config, "projects_root",
                          return_value="C-Users-someone-Projects"), \
                pytest.raises(ValueError, match="Nothing was created"):
            resolve_project_path("foo")
        assert list(tmp_path.iterdir()) == []

    def test_refuses_a_windows_root_resolved_against_the_cwd(self, tmp_path):
        """T2. What the sanitizer made of `C:\\...` on Linux: absolute, but
        joined to the current directory, so it does not exist."""
        joined = tmp_path / "C:\\Users\\someone\\Projects"
        with patch.object(new_repo.config, "projects_root", return_value=str(joined)), \
                pytest.raises(ValueError, match="not an existing directory"):
            resolve_project_path("foo")
        assert not joined.exists()


class TestAuditReadsThisOsSpelling:

    def test_audit_reads_the_decisions_file_in_the_spelling_of_this_os(self, tmp_path):
        with patch.object(new_repo.config, "assemblyzero_root",
                          return_value=str(tmp_path)) as root:
            new_repo.audit_structure(tmp_path, "proj")
        assert ("auto",) == tuple(c.kwargs["fmt"] for c in root.call_args_list)


# ===========================================================================
# #4136 — [SUCCESS] only when every step succeeded
# ===========================================================================


class TestIncompleteRunExitsAndAlerts:

    def test_a_failed_local_check_exits_1_without_success(self, tmp_path, capsys,
                                                          operator_alerts):
        """T2. run_command is mocked, so `git init` never runs and the data-dl
        check (real git) fails: a run with one failed step. Before #4136 this
        printed [SUCCESS] and exited 0."""
        with patch.object(new_repo, "config") as cfg, \
                patch("new_repo.run_command",
                      return_value=subprocess.CompletedProcess([], 0, "", "")), \
                patch("sys.argv", ["new_repo.py", "Broken", "--no-github"]):
            cfg.projects_root.return_value = str(tmp_path)
            cfg.projects_root_unix.return_value = "/tmp/projects"
            cfg.assemblyzero_root.return_value = str(tmp_path / "AssemblyZero")
            with pytest.raises(SystemExit) as exc:
                new_repo.main()

        assert exc.value.code == 1
        out, err = capsys.readouterr()
        assert "[SUCCESS]" not in out + err
        assert "[FAILED] Repository 'Broken' is incomplete" in err
        assert "local verification" in err
        assert len(operator_alerts) == 1
        assert operator_alerts[0]["repo"] == "Broken"
        assert "local verification" in operator_alerts[0]["consequence"]


def _all_ok(**overrides):
    flags = {
        "no_github": False,
        "local_checks": (7, 7),
        "github_created": True,
        "push_succeeded": True,
        "repo_settings_ok": True,
        "protection_ok": True,
        "cerberus_status": "OK",
        "hook_results": [],
        "gh_checks": (5, 5),
    }
    flags.update(overrides)
    return flags


class TestFailedSteps:

    def test_a_clean_run_has_none(self):
        assert failed_steps(**_all_ok()) == []

    def test_the_2026_10_07_run_names_every_failure(self):
        """The decrypt failed, so nothing on GitHub happened, and one local
        check (the hook) failed. That run printed [SUCCESS]."""
        failed = failed_steps(**_all_ok(
            local_checks=(6, 7),
            github_created=False,
            push_succeeded=False,
            repo_settings_ok=False,
            protection_ok=False,
            cerberus_status=None,
            gh_checks=(0, 0),
        ))
        assert failed == [
            "local verification (6/7)",
            "GitHub repo",
            "push",
            "repo settings",
            "branch protection",
        ]

    def test_cerberus_failure_counts(self):
        assert failed_steps(**_all_ok(cerberus_status="PEM_GPG_FAILED")) == [
            "Cerberus secrets (PEM_GPG_FAILED)",
        ]

    def test_failed_hook_counts(self):
        hooks = [(Path("hooks/deploy_token.py"), "FAILED: exit 1"), (Path("hooks/x.py"), "OK")]
        assert failed_steps(**_all_ok(hook_results=hooks)) == ["hook deploy_token"]

    def test_github_side_verification_counts(self):
        assert failed_steps(**_all_ok(gh_checks=(4, 5))) == [
            "GitHub-side verification (4/5)",
        ]

    def test_no_github_judges_only_the_local_checks(self):
        flags = _all_ok(no_github=True, github_created=False, push_succeeded=False,
                        repo_settings_ok=False, protection_ok=False)
        assert failed_steps(**flags) == []
        flags["local_checks"] = (5, 7)
        assert failed_steps(**flags) == ["local verification (5/7)"]
