"""Cerberus after Auto Review's retirement (#4723, #4724).

The reusable Auto Review workflow is retired (#3663: its only job is `if: false`) and the
fleet is removing its caller (#4719). The pr-sentinel Worker approves as Cerberus with its own
copy of the App key. So:

- #4724: the per-repository secrets `REVIEWER_APP_ID` and `REVIEWER_APP_PRIVATE_KEY` have no
  reader left (the search is recorded on #4724). `new_repo.py` creates a repository without a
  Cerberus PEM, and a test here fails the moment any workflow other than the two retired Auto
  Review files starts reading either secret again, because then they are required again.
- #4723: `tools/audit_cerberus_health.py` judged each repository's key by its Auto Review
  runs. With no reader, a per-repository key has no health to observe, so the audit is
  retired with its tests, and no live document sends anyone to it.

The scaffold runs in a `tmp_path` sandbox. Every GitHub boundary of `new_repo` (the classic-PAT
session, `requests`, the configure and verify helpers) is replaced; `git init` really runs,
because the scaffold's own checks ask real git about the ignore rules.
"""

from __future__ import annotations

import contextlib
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import new_repo

SECRETS = ("REVIEWER_APP_ID", "REVIEWER_APP_PRIVATE_KEY")
# The only workflows allowed to read the per-repository secrets: the retired reusable
# workflow (`if: false`) and the caller template kept beside it.
RETIRED_READERS = {"auto-reviewer.yml", "auto-reviewer-caller.yml"}
SECRET_READ = re.compile(r"secrets\.(REVIEWER_APP_ID|REVIEWER_APP_PRIVATE_KEY)\b")


# ---------------------------------------------------------------------------
# #4724 R3: the finding that nothing reads the secrets, re-checked every run
# ---------------------------------------------------------------------------


def _workflow_texts():
    for wf in sorted((ROOT / ".github" / "workflows").glob("*.y*ml")):
        yield wf.name, wf.read_text(encoding="utf-8")


def test_only_the_retired_auto_review_files_read_the_per_repo_secrets():
    readers = {name for name, text in _workflow_texts() if SECRET_READ.search(text)}
    assert readers <= RETIRED_READERS, (
        f"{sorted(readers - RETIRED_READERS)} read a per-repository Cerberus secret. The "
        "secrets are required again: restore governance T08, the readiness audit's secrets "
        "dimension and new_repo.py's PEM gate, and name the reader in each docstring (#4724)."
    )


def test_the_retired_reusable_workflow_still_reads_them_only_in_a_job_that_never_runs():
    text = (ROOT / ".github" / "workflows" / "auto-reviewer.yml").read_text(encoding="utf-8")
    assert SECRET_READ.search(text)
    assert re.search(r"^\s+if:\s*false\s*$", text, re.MULTILINE), (
        "the reusable Auto Review job runs again, so its callers read the per-repository "
        "Cerberus secrets again; they are required again (#4724)"
    )


@pytest.mark.parametrize("enable_pypi", [True, False])
def test_no_workflow_the_scaffolder_writes_reads_the_secrets(tmp_path: Path, enable_pypi):
    new_repo.create_github_workflows(tmp_path, enable_pypi=enable_pypi)
    for wf in tmp_path.rglob("*.y*ml"):
        assert not SECRET_READ.search(wf.read_text(encoding="utf-8")), wf.name


def test_the_worker_approves_with_its_own_secrets_not_the_per_repo_ones():
    src = (ROOT / "sentinel" / "src" / "cerberus.js").read_text(encoding="utf-8")
    assert "env.CERBERUS_PRIVATE_KEY_B64" in src
    for name in SECRETS:
        assert name not in src


# ---------------------------------------------------------------------------
# #4724 T2: new_repo.py creates a GitHub repository without a Cerberus PEM
# ---------------------------------------------------------------------------


def _ok(cmd, cwd=None, check=True):
    if cmd[:2] == ["git", "init"]:
        subprocess.run(["git", "init", "-q"], cwd=cwd, check=True)
    return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")


def _must_not_run(what):
    def refuse(*args, **kwargs):
        raise AssertionError(f"a run without a PEM flag reached {what}")
    return refuse


@contextlib.contextmanager
def _fake_pat_session(*args, **kwargs):
    yield "fake-pat"


def _response(status):
    return SimpleNamespace(status_code=status, text="", json=dict)


def _run_main(tmp_path: Path, argv: list[str]):
    """Run new_repo.main() with every GitHub boundary replaced. Returns the exit code."""
    home = tmp_path / "home"
    (home / ".secrets").mkdir(parents=True)
    # The PEM the #1543 fallback used to pick up on its own. It must now be ignored.
    (home / ".secrets" / "cerberus-pem.gpg").write_bytes(b"not a real key")

    fake_requests = MagicMock()
    fake_requests.post.return_value = _response(201)
    fake_requests.put.return_value = _response(204)
    fake_requests.get.return_value = _response(200)

    patches = [
        patch("new_repo.config"),
        patch("new_repo.run_command", side_effect=_ok),
        patch("new_repo.Path.home", return_value=home),
        patch("new_repo.get_github_username", return_value="owner"),
        patch("new_repo.check_remote_repo_exists", return_value=None),
        patch("new_repo.classic_pat_session", _fake_pat_session),
        patch.object(new_repo, "requests", fake_requests),
        patch("new_repo._deploy_workflows_via_contents_api", return_value=(True, 0)),
        patch("new_repo.configure_repo_settings", return_value=True),
        patch("new_repo.configure_branch_protection", return_value=True),
        patch("new_repo.create_canonical_labels", return_value=(2, 2)),
        patch("new_repo.enable_dependabot_for_repo",
              return_value=SimpleNamespace(actions={}, ok=True)),
        patch("new_repo.read_post_create_hooks", return_value=[]),
        patch("new_repo.verify_branch_protection_on_origin", return_value=(True, "ok")),
        patch("new_repo.verify_repo_settings_on_origin", return_value=(True, "ok")),
        patch("new_repo.run_pr_sentinel_check", return_value=("skip", "not in a test")),
        patch("new_repo.cerberus_pem_session", _must_not_run("the Cerberus PEM decrypt")),
        patch("new_repo.deploy_to_repo", _must_not_run("the Cerberus secret deploy")),
        patch("new_repo.verify_secrets", _must_not_run("the Cerberus secret check")),
        patch("sys.argv", ["new_repo.py", *argv]),
    ]
    with contextlib.ExitStack() as stack:
        mocks = [stack.enter_context(p) for p in patches]
        cfg = mocks[0]
        cfg.projects_root.return_value = str(tmp_path)
        cfg.projects_root_unix.return_value = "/tmp/projects"
        cfg.assemblyzero_root.return_value = str(tmp_path / "AssemblyZero")
        try:
            new_repo.main()
        except SystemExit as e:
            return e.code or 0
        return 0


def test_a_github_repository_is_created_without_any_cerberus_pem(tmp_path: Path, capsys):
    code = _run_main(tmp_path, ["NoPem"])
    out = capsys.readouterr()

    assert code == 0, out.out[-2000:] + out.err[-2000:]
    assert (tmp_path / "NoPem").is_dir()
    assert "[SUCCESS] Repository 'NoPem' created!" in out.out
    assert "Using Cerberus PEM" not in out.out, "the #1543 fallback picked up a PEM by itself"
    assert "Cerberus encrypted PEM not found" not in out.out
    assert "Cerberus secrets" not in out.out, "a run without a PEM still reports Cerberus secrets"


def test_the_pem_flags_stay_refused_with_no_github(tmp_path: Path):
    """The optional flags still need a GitHub repo to deploy to."""
    argv = ["new_repo.py", "Conflict", "--no-github", "--cerberus-pem-gpg", str(tmp_path / "x.gpg")]
    with patch("new_repo.config"), patch("sys.argv", argv), pytest.raises(SystemExit) as exc:
        new_repo.main()
    assert exc.value.code == 1


def test_the_scaffolder_has_no_default_pem_and_no_pem_gate():
    assert not hasattr(new_repo, "DEFAULT_CERBERUS_PEM_GPG")
    src = (TOOLS / "new_repo.py").read_text(encoding="utf-8")
    assert "Cerberus encrypted PEM not found" not in src
    assert "Cerberus secrets (manual)" not in src


# ---------------------------------------------------------------------------
# #4723: the Cerberus health audit is retired
# ---------------------------------------------------------------------------

RETIRED_AUDIT = "audit_cerberus_health"
# Historical records keep their wording: the loud-failure sweep ledger and the reports of
# the issues that changed the audit.
HISTORICAL = ("docs/audits/", "docs/reports/")


def test_the_cerberus_health_audit_and_its_tests_are_gone():
    assert not (TOOLS / f"{RETIRED_AUDIT}.py").exists()
    assert not (ROOT / "tests" / "tools" / f"test_{RETIRED_AUDIT}.py").exists()


def test_nothing_live_names_the_retired_audit():
    here = Path(__file__).resolve()
    hits = []
    for root in (TOOLS, ROOT / "tests", ROOT / "assemblyzero", ROOT / "docs"):
        for path in root.rglob("*"):
            if path.suffix not in {".py", ".md"} or path.resolve() == here:
                continue
            rel = path.relative_to(ROOT).as_posix()
            if rel.startswith(HISTORICAL):
                continue
            if RETIRED_AUDIT in path.read_text(encoding="utf-8", errors="replace"):
                hits.append(rel)
    assert hits == [], f"live files still send someone to the retired audit: {hits}"
