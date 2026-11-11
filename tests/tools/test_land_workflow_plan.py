"""Unit tests for tools/land_workflow_plan.py (#4713).

GitHub is replaced by a fake `requests` on the single-repository lander's module, through
which every call of the plan lander goes, and the token is a dummy string: nothing is
decrypted, because per the _pat_session operational rule that decrypt belongs to the
operator, never to a test or an agent.
"""

from __future__ import annotations

import base64
import copy
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "tools"))

import land_staged_workflow as lsw
import land_workflow_plan as lwp

API = "https://api.github.com/repos/o"
SOURCE = "SOURCEREPO"
LIVE = "name: Tests\non:\n  pull_request:\njobs:\n  test:\n    runs-on: ubuntu-latest\n"
COPY = "# off\n\nname: Tests\non:\n  pull_request:\njobs:\n  test:\n    if: false\n    runs-on: ubuntu-latest\n"
LIVE2 = "name: Lint\non:\n  pull_request:\njobs:\n  lint:\n    runs-on: ubuntu-latest\n"
COPY2 = "name: Lint\non:\n  pull_request:\njobs:\n  lint:\n    if: false\n    runs-on: ubuntu-latest\n"
BLOB = "a" * 40
BLOB2 = "b" * 40


def plan_for(*targets: dict) -> dict:
    return {
        "source": {"repo": SOURCE, "ref": "main"},
        "reason": "Turns the test jobs off, by the operator's order.",
        "targets": list(targets) or [target("alpha", 7)],
    }


def target(repo: str, issue: int, files: list[dict] | None = None) -> dict:
    return {"repo": repo, "issue": issue, "files": files or [
        {"staged": f"docs/ci/{repo}/tests.yml", "workflow": ".github/workflows/tests.yml",
         "base_blob": BLOB, "expect": "skipped"}]}


class Resp:
    def __init__(self, payload: object = None, status: int = 200):
        self.payload, self.status_code, self.text = payload, status, json.dumps(payload)

    def json(self) -> object:
        return self.payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class FakeGitHub:
    """Just enough of the REST API for one plan run, recording every write."""

    def __init__(self, conclusion: str = "skipped"):
        self.files: dict[tuple[str, str, str], tuple[str, str]] = {}  # (repo, ref, path) -> (text, sha)
        self.repos: dict[str, dict] = {}
        self.writes: list[tuple[str, str]] = []
        self.prs: dict[str, list[dict]] = {}
        self.conclusion = conclusion

    def put_file(self, repo: str, ref: str, path: str, text: str, sha: str) -> None:
        self.files[(repo, ref, path)] = (text, sha)
        self.repos.setdefault(repo, {"private": True, "default_branch": "main"})

    def _rec(self, text: str, sha: str) -> dict:
        return {"content": base64.b64encode(text.encode()).decode(), "sha": sha}

    def get(self, url, params=None, headers=None, timeout=None):
        params = params or {}
        if m := re.fullmatch(rf"{API}/([^/]+)", url):
            return Resp(self.repos[m.group(1)])
        if m := re.fullmatch(rf"{API}/([^/]+)/contents/(.+)", url):
            hit = self.files.get((m.group(1), params.get("ref"), m.group(2)))
            return Resp(self._rec(*hit)) if hit else Resp({}, 404)
        if m := re.fullmatch(rf"{API}/([^/]+)/git/ref/heads/main", url):
            return Resp({"object": {"sha": "m" * 40}})
        if m := re.fullmatch(rf"{API}/([^/]+)/pulls", url):
            return Resp([p for p in self.prs.get(m.group(1), []) if p["state"] == "open"])
        if m := re.fullmatch(rf"{API}/([^/]+)/pulls/(\d+)", url):
            return Resp({"head": {"sha": "h" * 40}, "mergeable_state": "clean"})
        if m := re.fullmatch(rf"{API}/([^/]+)/actions/runs", url):
            names = [lsw.workflow_name(t, None) for (r, ref, _), (t, _) in self.files.items()
                     if r == m.group(1) and ref.startswith("ci/")]
            return Resp({"workflow_runs": [
                {"name": n, "status": "completed", "conclusion": self.conclusion,
                 "created_at": "2026-11-11T00:00:00Z", "html_url": "https://x/run"} for n in names]})
        raise AssertionError(f"unexpected GET {url}")

    def post(self, url, headers=None, json=None, timeout=None):
        if m := re.fullmatch(rf"{API}/([^/]+)/git/refs", url):
            self.writes.append(("branch", f"{m.group(1)}:{json['ref']}"))
            return Resp({}, 201)
        if m := re.fullmatch(rf"{API}/([^/]+)/pulls", url):
            pr = {"number": 41, "state": "open", **json}
            self.prs.setdefault(m.group(1), []).append(pr)
            self.writes.append(("pr", f"{m.group(1)}:{json['title']}"))
            return Resp({"number": 41}, 201)
        raise AssertionError(f"unexpected POST {url}")

    def put(self, url, headers=None, json=None, timeout=None):
        if m := re.fullmatch(rf"{API}/([^/]+)/contents/(.+)", url):
            text = base64.b64decode(json["content"]).decode()
            self.files[(m.group(1), json["branch"], m.group(2))] = (text, "n" * 40)
            self.writes.append(("commit", f"{m.group(1)}:{m.group(2)}"))
            return Resp({}, 200)
        if m := re.fullmatch(rf"{API}/([^/]+)/pulls/(\d+)/merge", url):
            for p in self.prs[m.group(1)]:
                p["state"] = "merged"
            self.writes.append(("merge", m.group(1)))
            return Resp({}, 200)
        raise AssertionError(f"unexpected PUT {url}")

    def delete(self, url, headers=None, json=None, timeout=None):
        if m := re.fullmatch(rf"{API}/([^/]+)/git/refs/heads/(.+)", url):
            self.writes.append(("delete-branch", f"{m.group(1)}:{m.group(2)}"))
            return Resp({}, 204)
        raise AssertionError(f"unexpected DELETE {url}")


@pytest.fixture
def gh(monkeypatch):
    fake = FakeGitHub()
    monkeypatch.setattr(lsw, "requests", SimpleNamespace(
        get=fake.get, post=fake.post, put=fake.put, delete=fake.delete))
    monkeypatch.setattr(lsw.time, "sleep", lambda s: None)
    return fake


def stage(gh: FakeGitHub, repo: str, live: str = LIVE, copy_: str = COPY, blob: str = BLOB,
          workflow: str = ".github/workflows/tests.yml", staged: str | None = None) -> None:
    gh.put_file(repo, "main", workflow, live, blob)
    gh.put_file(SOURCE, "main", staged or f"docs/ci/{repo}/tests.yml", copy_, "s" * 40)


# --- T1: the plan's contract ---------------------------------------------------------


class TestValidatePlan:
    def test_a_well_formed_plan_passes(self):
        assert lwp.validate_plan(plan_for())["source"]["ref"] == "main"

    @pytest.mark.parametrize("path, value, needle", [
        (("source",), None, "source.repo"),
        (("reason",), "", "reason"),
        (("targets",), [], "targets"),
        (("targets", 0, "issue"), 0, "issue"),
        (("targets", 0, "repo"), "o/alpha", "a name"),
        (("targets", 0, "files", 0, "workflow"), "docs/tests.yml", ".github/workflows/"),
        (("targets", 0, "files", 0, "base_blob"), "abc", "base_blob"),
        (("targets", 0, "files", 0, "expect"), "failure", "expect"),
        (("targets", 0, "files", 0, "staged"), "", "staged"),
    ])
    def test_each_fault_is_refused_by_name(self, path, value, needle):
        plan = plan_for()
        node = plan
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value
        with pytest.raises(lwp.PlanError) as e:
            lwp.validate_plan(plan)
        assert needle in str(e.value)

    def test_a_duplicate_target_is_refused(self):
        with pytest.raises(lwp.PlanError, match="twice"):
            lwp.validate_plan(plan_for(target("alpha", 7), target("alpha", 8)))

    def test_a_reason_naming_the_source_is_refused(self):
        plan = plan_for()
        plan["reason"] = f"Staged in {SOURCE.lower()}."
        with pytest.raises(lwp.PlanError, match="source repository"):
            lwp.validate_plan(plan)

    def test_no_repository_is_baked_in(self):
        """This repo is public; every name arrives in the plan, at run time."""
        with pytest.raises(SystemExit):
            lwp.parse_args([])


class TestPrText:
    def test_title_and_body_close_the_issue_and_name_no_source(self):
        workflows = [".github/workflows/tests.yml", ".github/workflows/lint.yml"]
        title = lwp.pr_title(workflows, 7)
        body = lwp.pr_body("Turns the tests off.", workflows, 7)
        assert title == "ci: update tests.yml, lint.yml (Closes #7)"
        assert body.startswith("Closes #7\n")
        for text in (title, body):
            assert SOURCE not in text and "docs/ci" not in text

    def test_a_title_past_the_limit_counts_the_files(self):
        workflows = [f".github/workflows/{'w' * 40}{i}.yml" for i in range(8)]
        assert lwp.pr_title(workflows, 7) == "ci: update 8 workflows (Closes #7)"


class TestVerdict:
    @pytest.mark.parametrize("conclusion, expect, red, ok", [
        ("skipped", "skipped", False, True),
        ("success", "success", False, True),
        ("success", "skipped", False, False),
        ("failure", "success", False, False),
        ("failure", "success", True, True),
        ("in_progress", "skipped", True, False),
        ("no_run", "skipped", True, False),
    ])
    def test_verdict(self, conclusion, expect, red, ok):
        assert lwp.verdict(conclusion, expect, red) is ok


# --- T2 and T3: what one run does to a target ----------------------------------------


class TestLandTarget:
    def test_a_target_lands_as_one_branch_one_pr_then_merge_and_delete(self, gh):
        files = [
            {"staged": "docs/ci/alpha/tests.yml", "workflow": ".github/workflows/tests.yml",
             "base_blob": BLOB, "expect": "skipped"},
            {"staged": "docs/ci/alpha/lint.yml", "workflow": ".github/workflows/lint.yml",
             "base_blob": BLOB2, "expect": "skipped"},
        ]
        stage(gh, "alpha")
        stage(gh, "alpha", LIVE2, COPY2, BLOB2, ".github/workflows/lint.yml", "docs/ci/alpha/lint.yml")
        plan = lwp.validate_plan(plan_for(target("alpha", 7, files)))
        assert lwp.land_target("pat", plan, plan["targets"][0], "o", False) == "landed"
        assert [w[0] for w in gh.writes] == ["branch", "commit", "commit", "pr", "merge", "delete-branch"]
        assert gh.files[("alpha", "ci/staged-workflow-7", ".github/workflows/tests.yml")][0] == COPY
        pr = gh.prs["alpha"][0]
        assert pr["title"] == "ci: update tests.yml, lint.yml (Closes #7)"
        assert SOURCE not in pr["body"] and "docs/ci" not in pr["body"]

    def test_a_moved_base_blob_stops_before_any_write(self, gh):
        stage(gh, "alpha", blob="c" * 40)
        plan = lwp.validate_plan(plan_for())
        with pytest.raises(lwp.LandingStop) as e:
            lwp.land_target("pat", plan, plan["targets"][0], "o", False)
        assert e.value.step == "base" and gh.writes == []

    def test_a_target_already_landed_is_skipped_without_a_write(self, gh):
        stage(gh, "alpha", live=COPY)
        plan = lwp.validate_plan(plan_for())
        assert lwp.land_target("pat", plan, plan["targets"][0], "o", False) == "already"
        assert gh.writes == []

    def test_a_conclusion_other_than_the_plan_stops_and_leaves_the_pr_open(self, gh):
        gh.conclusion = "failure"
        stage(gh, "alpha")
        plan = lwp.validate_plan(plan_for())
        with pytest.raises(lwp.LandingStop) as e:
            lwp.land_target("pat", plan, plan["targets"][0], "o", False)
        assert e.value.step == "wait"
        assert ("merge", "alpha") not in gh.writes and gh.prs["alpha"][0]["state"] == "open"

    def test_a_copy_with_a_carriage_return_is_refused(self, gh):
        stage(gh, "alpha", copy_=COPY.replace("\n", "\r\n"))
        plan = lwp.validate_plan(plan_for())
        with pytest.raises(lwp.LandingStop, match="carriage return"):
            lwp.land_target("pat", plan, plan["targets"][0], "o", False)
        assert gh.writes == []


# --- T3, T4: the whole run -------------------------------------------------------------


class Session:
    def __init__(self):
        self.calls = 0

    def __call__(self, reason=None):
        self.calls += 1
        outer = self

        class Ctx:
            def __enter__(self):
                return "pat"

            def __exit__(self, *exc):
                return False

        outer.reason = reason
        return Ctx()


class TestRun:
    def test_one_session_covers_every_target(self, gh):
        for repo in ("alpha", "beta"):
            stage(gh, repo)
        plan = lwp.validate_plan(plan_for(target("alpha", 7), target("beta", 9)))
        session = Session()
        assert lwp.run(plan, plan["targets"], "o", False, session=session) == 0
        assert session.calls == 1
        assert [w[1] for w in gh.writes if w[0] == "merge"] == ["alpha", "beta"]

    def test_the_first_failure_stops_the_run_and_counts(self, gh, capsys):
        stage(gh, "alpha")
        stage(gh, "beta", blob="c" * 40)
        stage(gh, "gamma")
        plan = lwp.validate_plan(plan_for(target("alpha", 7), target("beta", 9), target("gamma", 11)))
        assert lwp.run(plan, plan["targets"], "o", False, session=Session()) == 1
        err = capsys.readouterr().err
        assert "STOPPED at beta" in err and "landed 1, already landed 0, not landed 2 of 3" in err
        assert not any(w[1].startswith("gamma") for w in gh.writes)

    def test_a_reason_naming_a_private_target_stops_when_any_target_is_public(self, gh, capsys):
        stage(gh, "alpha")
        stage(gh, "beta")
        gh.repos["beta"]["private"] = False
        plan = lwp.validate_plan(plan_for(target("alpha", 7), target("beta", 9)))
        plan["reason"] = "Same as alpha did."
        assert lwp.run(plan, plan["targets"], "o", False, session=Session()) == 1
        assert gh.writes == [] and "private target" in capsys.readouterr().err

    def test_a_default_branch_other_than_main_stops_before_any_write(self, gh):
        stage(gh, "alpha")
        gh.repos["alpha"]["default_branch"] = "master"
        plan = lwp.validate_plan(plan_for())
        assert lwp.run(plan, plan["targets"], "o", False, session=Session()) == 1
        assert gh.writes == []

    def test_the_dry_run_asks_for_no_credential(self, tmp_path, monkeypatch, capsys):
        path = tmp_path / "plan.json"
        path.write_text(json.dumps(plan_for()), encoding="utf-8")

        def refuse(*a, **k):
            raise AssertionError("the dry run asked for the PAT")

        monkeypatch.setattr(lwp, "classic_pat_session", refuse)
        monkeypatch.setattr(lwp, "run", refuse)
        assert lwp.main(["--plan", str(path)]) == 0
        out = capsys.readouterr().out
        assert "DRY-RUN" in out and "#7" in out

    def test_only_limits_the_run_and_refuses_a_name_not_in_the_plan(self):
        plan = lwp.validate_plan(plan_for(target("alpha", 7), target("beta", 9)))
        assert [t["repo"] for t in lwp.select(plan, ["beta"])] == ["beta"]
        with pytest.raises(lwp.PlanError):
            lwp.select(copy.deepcopy(plan), ["delta"])
