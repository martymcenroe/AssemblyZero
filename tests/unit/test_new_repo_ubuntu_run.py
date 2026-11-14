"""
new_repo.py run from Ubuntu: where it builds, and whether it admits failure.

Diagnosed from the first Ubuntu run, 2026-10-07 at 6:42 PM Central:

- #4132: the Projects root came back in its Windows spelling, a relative path
  on Linux. The config's sanitizer resolved it against the current directory,
  so the repository was built inside the AssemblyZero checkout.
- #4136: the run then printed [SUCCESS] although the GitHub repo, the push,
  the settings, branch protection and the hook install had all failed.

Issues: #4132, #4136, #4763
"""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "tools"))

import assemblyzero_config
import new_repo
from new_repo import (
    failed_steps,
    resolve_project_path,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _real_config(monkeypatch, path: Path, content=None):
    """A real AssemblyZeroConfig that reads `path` (#4763).

    `content` is written there first: a dict as JSON, a str as it stands, and
    None writes no file at all.
    """
    if isinstance(content, dict):
        path.write_text(json.dumps(content), encoding="utf-8")
    elif content is not None:
        path.write_text(content, encoding="utf-8")
    monkeypatch.setattr(assemblyzero_config, "CONFIG_PATH", path)
    return assemblyzero_config.AssemblyZeroConfig()


def _real_git_init(cmd, cwd=None, check=True):
    """run_command that really runs `git init` and answers everything else as a
    success, as test_new_repo.run_with_real_git_init does (#4136)."""
    if cmd[:2] == ["git", "init"]:
        subprocess.run(["git", "init", "-q"], cwd=cwd, check=True)
    return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")


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

    def test_a_configured_new_repo_root_is_where_it_builds(self, tmp_path):
        """T1 (#4763). new_repo_root, in the spelling of this OS, is the parent."""
        with patch.object(new_repo.config, "load_error", None), \
                patch.object(new_repo.config, "new_repo_root",
                             return_value=str(tmp_path)) as root:
            assert resolve_project_path("foo") == tmp_path / "foo"
        root.assert_called_once_with(fmt="auto")

    def test_with_no_config_file_it_builds_in_the_projects_root(self, tmp_path, monkeypatch):
        """T1 (#4763). No config file: the Projects root, as before the key existed."""
        cfg = _real_config(monkeypatch, tmp_path / "absent.json")
        monkeypatch.setattr(new_repo, "config", cfg)
        assert cfg.load_error is None
        assert resolve_project_path("foo") == Path(cfg.projects_root(fmt="auto")) / "foo"

    def test_a_file_holding_only_new_repo_root_is_honoured(self, tmp_path, monkeypatch):
        """T1 (#4763). A file that sets new_repo_root alone loads, and is used."""
        root = tmp_path / "ext4"
        root.mkdir()
        cfg = _real_config(monkeypatch, tmp_path / "config.json", {
            "version": "1.0",
            "paths": {"new_repo_root": {"unix": str(root), "windows": str(root)}},
        })
        monkeypatch.setattr(new_repo, "config", cfg)
        assert cfg.load_error is None
        assert resolve_project_path("foo") == root / "foo"

    def test_a_config_file_that_is_not_json_stops_the_run_first(
            self, tmp_path, monkeypatch, capsys):
        """T1 (#4763). A file that exists and is rejected may have meant to move
        the root. main() exits 1 naming it, and runs no command."""
        bad = tmp_path / "config.json"
        cfg = _real_config(monkeypatch, bad, "{ not json")
        monkeypatch.setattr(new_repo, "config", cfg)
        with patch("new_repo.run_command") as run, \
                patch("sys.argv", ["new_repo.py", "BadConfig4763", "--no-github"]), \
                pytest.raises(SystemExit) as exc:
            new_repo.main()
        assert exc.value.code == 1
        err = capsys.readouterr().err
        assert str(bad) in err
        assert "not valid JSON" in err
        assert "Nothing was created" in err
        run.assert_not_called()
        assert not (Path(cfg.projects_root(fmt="auto")) / "BadConfig4763").exists()

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
            cfg.load_error = None
            cfg.new_repo_root.return_value = str(tmp_path)
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
            gh_checks=(0, 0),
        ))
        assert failed == [
            "local verification (6/7)",
            "GitHub repo",
            "push",
            "repo settings",
            "branch protection",
        ]

    def test_no_cerberus_step_is_judged(self):
        """The scaffolder deploys no Cerberus secret (#4728), so no step names one."""
        with pytest.raises(TypeError):
            failed_steps(**_all_ok(cerberus_status="PEM_GPG_FAILED"))

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


# ===========================================================================
# #4763 — a repository under a configured root names only paths real there
# ===========================================================================

# The fleet's Projects root in every spelling a scaffold could carry, the last
# one as JSON escapes the Windows spelling.
FLEET_ROOT_SPELLINGS = (
    "/mnt/c/Users/mcwiz/Projects",
    "/c/Users/mcwiz/Projects",
    "C:\\Users\\mcwiz\\Projects",
    "C:\\\\Users\\\\mcwiz\\\\Projects",
)


@pytest.mark.skipif(sys.platform == "win32", reason="an ext4 root exists only off Windows")
class TestScaffoldUnderAnExt4Root:

    @pytest.mark.parametrize("distro", ["Ubuntu", None], ids=["in-wsl", "no-distro"])
    def test_every_path_written_is_real_where_the_repository_is(
            self, tmp_path, monkeypatch, distro):
        """T2 (#4763). A real config whose new_repo_root and assemblyzero_root
        are temporary directories. Nothing the scaffold writes names the fleet's
        Projects root, and project.json names where the repository is."""
        root = tmp_path / "ext4"
        az = tmp_path / "AssemblyZero"
        root.mkdir()
        az.mkdir()
        cfg = _real_config(monkeypatch, tmp_path / "config.json", {
            "version": "1.0",
            "paths": {
                "new_repo_root": {"unix": str(root), "windows": str(root)},
                "assemblyzero_root": {"unix": str(az), "windows": str(az)},
            },
        })
        assert cfg.load_error is None
        monkeypatch.setattr(new_repo, "config", cfg)
        if distro:
            monkeypatch.setenv("WSL_DISTRO_NAME", distro)
        else:
            monkeypatch.delenv("WSL_DISTRO_NAME", raising=False)

        with patch("new_repo.run_command", side_effect=_real_git_init), \
                patch("sys.argv", ["new_repo.py", "ExtRepo", "--no-github"]):
            try:
                new_repo.main()
            except SystemExit as e:  # a full local run exits through sys.exit
                assert not e.code, f"the scaffold exited {e.code}"

        project = root / "ExtRepo"
        posix = project.as_posix()
        written = [p for p in project.rglob("*")
                   if p.is_file() and ".git" not in p.relative_to(project).parts]
        assert written, "the scaffold wrote no files"
        for path in written:
            text = path.read_bytes().decode("utf-8", errors="replace")
            for spelling in FLEET_ROOT_SPELLINGS:
                assert spelling not in text, f"{path.relative_to(project)} names {spelling}"

        variables = json.loads(
            (project / ".claude" / "project.json").read_text(encoding="utf-8"))["variables"]
        assert variables["PROJECT_ROOT"] == posix
        assert variables["TOOLS_DIR"] == f"{posix}/tools"
        if distro:
            assert variables["PROJECT_ROOT_WINDOWS"] == (
                "\\\\wsl.localhost\\Ubuntu" + posix.replace("/", "\\"))
        else:
            assert variables["PROJECT_ROOT_WINDOWS"] == posix
        claude_md = (project / "CLAUDE.md").read_text(encoding="utf-8")
        assert f"**Project Root (Unix):** `{posix}`" in claude_md


def test_a_repository_on_a_windows_drive_keeps_its_drive_spellings(tmp_path, monkeypatch):
    """#4763. The default case is unchanged: a repository in the Projects root
    seen from Ubuntu gets its /mnt/c and C:\\ spellings, even inside WSL."""
    monkeypatch.setattr(new_repo, "config", _real_config(monkeypatch, tmp_path / "absent.json"))
    monkeypatch.setenv("WSL_DISTRO_NAME", "Ubuntu")
    variables = new_repo.project_json_content(
        Path("/mnt/c/Users/mcwiz/Projects/Foo"), "Foo", "someone")["variables"]
    assert variables["PROJECT_ROOT"] == "/mnt/c/Users/mcwiz/Projects/Foo"
    assert variables["TOOLS_DIR"] == "/mnt/c/Users/mcwiz/Projects/Foo/tools"
    assert variables["PROJECT_ROOT_WINDOWS"] == "C:\\Users\\mcwiz\\Projects\\Foo"
