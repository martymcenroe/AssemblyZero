"""A resume is declined on a missing ARTIFACT, never on a missing path (#2414).

`resume_plan` read one field and abandoned the resume when it held the empty
string, so the refusal fired on a missing PATH STRING rather than on a missing
artifact. The artifact is usually committed on the issue's lld branch and
perfectly restorable; nothing checked.

The acceptance the issue asks for is two-sided, and both sides are here: an
impl-stage halt with a passed spec RESUMES, and an impl-stage halt whose spec
artifact genuinely cannot be found still DECLINES.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import speedrun_roll as sr  # noqa: E402

SPEC_REL = "docs/lld/drafts/spec-0001-implementation-readiness.md"
LLD_REL = "docs/lld/active/LLD-001.md"


def _git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True,
    )


@pytest.fixture
def repo(tmp_path):
    """A real repo with an issue-1 lld branch carrying both artifacts.

    Real git rather than a mock: the lookup's whole job is to consult the
    branch, and a stubbed `ls-tree` would be testing the stub.
    """
    r = tmp_path / "boostgauge"
    r.mkdir()
    _git(r, "init", "-q")
    _git(r, "config", "user.email", "t@example.com")
    _git(r, "config", "user.name", "t")
    (r / "README.md").write_text("base\n", encoding="utf-8")
    _git(r, "add", ".")
    _git(r, "commit", "-qm", "base")
    # `git init` names the default branch from the machine's config, so it is
    # asked rather than assumed -- hardcoding "master" left this fixture on the
    # lld branch, where the artifacts it is meant to hide were still present.
    default = _git(r, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()

    _git(r, "checkout", "-q", "-b", "1-lld")
    for rel, body in ((LLD_REL, "# LLD one\n"), (SPEC_REL, "# Spec one\n")):
        target = r / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
    _git(r, "add", ".")
    _git(r, "commit", "-qm", "artifacts")
    _git(r, "checkout", "-q", default)

    # The exit janitor clears pipeline-authored untracked files, so the working
    # tree does NOT have them -- which is the state a resume actually meets.
    assert not (r / SPEC_REL).exists()
    return r


def _state(repo, **overrides):
    data = {
        "issue_number": 1,
        "current_stage": "impl",
        "target_repo": str(repo),
        "base_branch": "hardening-run-17",
        "lld_path": str(repo / LLD_REL),
        "spec_path": "",
        "stage_results": {
            "triage": {"status": "skipped", "error_message": ""},
            "lld": {"status": "passed", "error_message": "",
                    "artifact_path": str(repo / LLD_REL)},
            "spec": {"status": "passed", "error_message": "",
                     "artifact_path": ""},
            "impl": {"status": "failed", "error_message": "green phase"},
        },
        "started_at": "2026-08-15T16:42:31+00:00",
        "completed_at": "",
    }
    data.update(overrides)
    return data


# ---------------------------------------------------------------------------
# The lookup itself
# ---------------------------------------------------------------------------


class TestArtifactLookup:
    def test_a_recorded_path_is_used_directly(self, repo):
        data = _state(repo, spec_path="/somewhere/spec.md")
        assert sr._resolve_stage_artifact(repo, 1, data, "spec") == "/somewhere/spec.md"

    def test_an_empty_path_falls_back_to_the_stage_result(self, repo):
        """`finalize_spec` populates the top-level field only on a pass; the
        per-stage `artifact_path` is recorded either way."""
        data = _state(repo)
        data["stage_results"]["spec"]["artifact_path"] = str(repo / SPEC_REL)
        assert sr._resolve_stage_artifact(repo, 1, data, "spec") == str(repo / SPEC_REL)

    def test_an_empty_path_and_empty_result_falls_back_to_the_branch(self, repo):
        """The case the issue is about: nothing recorded anywhere, and the
        artifact sitting on the lld branch the whole time."""
        data = _state(repo)
        found = sr._resolve_stage_artifact(repo, 1, data, "spec")
        assert found == str(repo / SPEC_REL)

    def test_a_whitespace_only_path_counts_as_unset(self, repo):
        data = _state(repo, spec_path="   ")
        data["stage_results"]["spec"]["artifact_path"] = ""
        assert sr._resolve_stage_artifact(repo, 1, data, "spec") == str(repo / SPEC_REL)

    def test_a_genuinely_absent_artifact_resolves_to_nothing(self, tmp_path):
        """The other side of the acceptance. No branch, no record, no file."""
        bare = tmp_path / "empty"
        bare.mkdir()
        _git(bare, "init", "-q")
        data = _state(bare)
        data["stage_results"]["spec"]["artifact_path"] = ""
        assert sr._resolve_stage_artifact(bare, 1, data, "spec") == ""

    def test_the_newest_spec_wins_when_several_exist(self, repo):
        default = _git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        _git(repo, "checkout", "-q", "1-lld")
        (repo / "docs/lld/drafts/spec-0002-later.md").write_text("x", encoding="utf-8")
        _git(repo, "add", ".")
        _git(repo, "commit", "-qm", "second spec")
        _git(repo, "checkout", "-q", default)
        data = _state(repo)
        assert sr._resolve_stage_artifact(repo, 1, data, "spec").endswith(
            "spec-0002-later.md"
        )

    def test_the_lld_stage_resolves_the_same_way(self, repo):
        data = _state(repo, lld_path="")
        data["stage_results"]["lld"]["artifact_path"] = ""
        assert sr._resolve_stage_artifact(repo, 1, data, "lld") == str(repo / LLD_REL)


class TestBranchSearch:
    def test_a_missing_branch_is_not_an_error(self, tmp_path):
        bare = tmp_path / "empty"
        bare.mkdir()
        _git(bare, "init", "-q")
        assert sr._find_on_lld_branch(bare, 1, "docs/**") == ""

    def test_a_non_matching_glob_finds_nothing(self, repo):
        assert sr._find_on_lld_branch(repo, 1, "docs/nope/*.md") == ""


# ---------------------------------------------------------------------------
# resume_plan end to end -- the two-sided acceptance
# ---------------------------------------------------------------------------


class _Log:
    def __init__(self):
        self.lines = []

    def write(self, message):
        self.lines.append(message)


def _plan(repo, data, tmp_path):
    state_path = tmp_path / "1.json"
    state_path.write_text(json.dumps(data), encoding="utf-8")
    log = _Log()
    with patch.object(sr, "_orchestrator_state_path", return_value=state_path), \
         patch.object(sr, "resolve_attempt_branch", return_value="hardening-run-17"), \
         patch.object(sr, "_open_lld_pr_exists", return_value=True), \
         patch.object(sr, "draft_is_stale", return_value=False):
        return sr.resume_plan(Path("."), repo, 1, log), log


class TestSpecPassedImplHaltedResumes:
    """The fixture the issue names, and the exact state boostgauge #1 is in
    after the operator's kill: spec passed, impl halted, spec_path unset."""

    def test_it_resumes_from_impl(self, repo, tmp_path):
        stage, _log = _plan(repo, _state(repo), tmp_path)
        assert stage == "impl"

    def test_the_spec_artifact_is_restored_to_disk(self, repo, tmp_path):
        """Not merely 'resume was allowed' -- the input the impl stage needs
        is actually put back where it can be read."""
        assert not (repo / SPEC_REL).exists()
        stage, _log = _plan(repo, _state(repo), tmp_path)
        assert stage == "impl"
        assert (repo / SPEC_REL).is_file()
        assert (repo / SPEC_REL).read_text(encoding="utf-8") == "# Spec one\n"

    def test_the_old_behaviour_would_have_declined(self, repo, tmp_path):
        """Pins WHY this issue exists: the pre-#2414 expression is right here,
        and on this same state it yields the empty string."""
        data = _state(repo)
        assert data.get("spec_path", "") == ""  # what the old check read
        # ...while the artifact was on the branch the entire time.
        assert sr._resolve_stage_artifact(repo, 1, data, "spec")


class TestGenuinelyMissingArtifactStillDeclines:
    """The other half of the acceptance. A resume into a missing input is
    worse than a redraw, so this MUST still refuse."""

    def test_no_spec_anywhere_declines(self, repo, tmp_path):
        _git(repo, "branch", "-m", "1-lld", "1-lld-gone")  # hide the artifacts
        data = _state(repo)
        data["stage_results"]["spec"]["artifact_path"] = ""
        # The lld is still resolvable from its recorded path, so only the spec
        # is missing -- which isolates the branch under test.
        (repo / LLD_REL).parent.mkdir(parents=True, exist_ok=True)
        (repo / LLD_REL).write_text("# LLD one\n", encoding="utf-8")
        stage, log = _plan(repo, data, tmp_path)
        assert stage is None
        assert any("no spec artifact recorded" in line for line in log.lines)

    def test_a_recorded_path_that_cannot_be_restored_declines(self, repo, tmp_path):
        data = _state(repo, spec_path=str(repo / "docs/lld/drafts/ghost.md"))
        stage, log = _plan(repo, data, tmp_path)
        assert stage is None
        assert any("not restorable" in line for line in log.lines)

    def test_the_decline_names_which_stage_was_missing(self, repo, tmp_path):
        data = _state(repo, spec_path=str(repo / "docs/lld/drafts/ghost.md"))
        _stage, log = _plan(repo, data, tmp_path)
        assert any("spec artifact" in line for line in log.lines)

    def test_a_spec_stage_failure_does_not_need_the_spec_artifact(
        self, repo, tmp_path
    ):
        """Only the impl branch requires the spec. A spec-stage resume must
        not start demanding an artifact it is about to produce."""
        data = _state(repo)
        data["stage_results"]["spec"] = {"status": "failed", "error_message": "cap"}
        data["stage_results"].pop("impl")
        stage, _log = _plan(repo, data, tmp_path)
        assert stage == "spec"
