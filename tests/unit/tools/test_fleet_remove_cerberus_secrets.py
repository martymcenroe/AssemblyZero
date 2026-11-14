"""Tests for tools/fleet_remove_cerberus_secrets.py (#4728).

GitHub is a fake that keeps each repository's Actions and Dependabot secrets and answers
the calls the program makes the way GitHub does: 200 or 404 for one secret, 204 for a
deletion, a page of `/user/repos` at a time. The program's `request` is pointed at it, and
the classic-PAT session is a stand-in that yields a dummy string: nothing is decrypted,
because per the _pat_session operational rule that decrypt belongs to the operator, never
to a test or an agent.
"""

from __future__ import annotations

import ast
import contextlib
import re
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent.parent.parent.parent / "tools"
sys.path.insert(0, str(TOOLS))

import fleet_remove_cerberus_secrets as frs

API = "https://api.github.com"
SECRET_PATH = re.compile(r"/repos/([^/]+)/([^/]+)/(actions|dependabot)/secrets/([^/]+)")
BOTH = set(frs.SECRETS)


class Resp:
    def __init__(self, status: int, body=None):
        self.status_code = status
        self._body = body

    def json(self):
        if self._body is None:
            raise ValueError("no body")
        return self._body


class FakeGitHub:
    """The parts of GitHub's REST API the program uses, holding real per-repository state."""

    def __init__(self, repos: dict[str, dict], login: str = "owner"):
        self.login = login
        self.repos = repos
        self.calls: list[tuple[str, str]] = []
        self.refuse: dict[tuple[str, str], int] = {}
        # (repo, scope, name) whose DELETE answers 204 and keeps the secret anyway.
        self.sticky: set[tuple[str, str, str]] = set()
        self.pages: list[int] = []

    def __call__(self, method: str, url: str, pat: str, params=None, **kwargs):
        assert url.startswith(API), url
        assert pat == "fake-pat"
        path = url[len(API):]
        self.calls.append((method, path))
        if (method, path) in self.refuse:
            return Resp(self.refuse[(method, path)], {"message": "refused by the fake"})
        if (method, path) == ("GET", "/user"):
            return Resp(200, {"login": self.login})
        if (method, path) == ("GET", "/user/repos"):
            assert params["affiliation"] == "owner"
            per, page = params["per_page"], params["page"]
            self.pages.append(page)
            names = list(self.repos)[(page - 1) * per: page * per]
            return Resp(200, [{"name": n, "owner": {"login": self.login},
                               "archived": self.repos[n].get("archived", False)} for n in names])
        m = SECRET_PATH.fullmatch(path)
        if not m or m.group(1) != self.login or m.group(2) not in self.repos:
            return Resp(404, {"message": "Not Found"})
        _, repo, scope, name = m.groups()
        store = self.repos[repo][scope]
        if method == "GET":
            return Resp(200, {"name": name}) if name in store else Resp(404, {"message": "Not Found"})
        if method == "DELETE":
            if name not in store:
                return Resp(404, {"message": "Not Found"})
            if (repo, scope, name) not in self.sticky:
                store.discard(name)
            return Resp(204)
        return Resp(405, {"message": "Method Not Allowed"})

    def deletes(self) -> list[str]:
        return sorted(p for m, p in self.calls if m == "DELETE")


def repo(actions=(), dependabot=(), archived=False) -> dict:
    return {"actions": set(actions), "dependabot": set(dependabot), "archived": archived}


def every(name: str) -> list[str]:
    """The four DELETE paths that clean one repository."""
    return sorted(f"/repos/owner/{name}/{s}/secrets/{n}" for s in frs.SCOPES for n in frs.SECRETS)


@contextlib.contextmanager
def fake_session(reason=None):
    print("<<decrypt>>", flush=True)
    yield "fake-pat"


def run(gh: FakeGitHub, apply: bool, only=None) -> int:
    return frs.run(apply, only, session=fake_session, request=gh)


# ---------------------------------------------------------------------------
# T1 (R2, R6): exactly four deletions; no other secret is touched
# ---------------------------------------------------------------------------


def test_t1_both_secrets_in_both_scopes_mean_exactly_four_deletions(capsys):
    gh = FakeGitHub({
        "alpha": repo(BOTH | {"OTHER_SECRET"}, BOTH | {"NPM_TOKEN"}),
        "beta": repo({"UNRELATED"}, {"UNRELATED"}),
    })
    assert run(gh, apply=True) == 0

    assert gh.deletes() == every("alpha")
    assert gh.repos["alpha"]["actions"] == {"OTHER_SECRET"}
    assert gh.repos["alpha"]["dependabot"] == {"NPM_TOKEN"}
    assert gh.repos["beta"]["actions"] == {"UNRELATED"}
    assert gh.repos["beta"]["dependabot"] == {"UNRELATED"}
    # It never even names an unrelated secret in a call.
    assert not any(other in p for _, p in gh.calls
                   for other in ("OTHER_SECRET", "NPM_TOKEN", "UNRELATED"))
    out = capsys.readouterr().out
    assert "Done: cleaned 1, already clean 1, of 2." in out


def test_t1_one_secret_in_one_scope_is_one_deletion():
    gh = FakeGitHub({"alpha": repo(dependabot={"REVIEWER_APP_PRIVATE_KEY", "KEEP"})})
    assert run(gh, apply=True) == 0
    assert gh.deletes() == ["/repos/owner/alpha/dependabot/secrets/REVIEWER_APP_PRIVATE_KEY"]
    assert gh.repos["alpha"]["dependabot"] == {"KEEP"}


def test_the_delete_refuses_any_other_secret_or_scope_before_any_call():
    gh = FakeGitHub({"alpha": repo({"OTHER_SECRET"})})
    with pytest.raises(ValueError):
        frs.delete(gh, "fake-pat", "owner", "alpha", "actions", "OTHER_SECRET")
    with pytest.raises(ValueError):
        frs.delete(gh, "fake-pat", "owner", "alpha", "codespaces", "REVIEWER_APP_ID")
    assert gh.calls == []
    assert gh.repos["alpha"]["actions"] == {"OTHER_SECRET"}


# ---------------------------------------------------------------------------
# T2 (R4, R5): a stop names the failure; a rerun skips what is already clean
# ---------------------------------------------------------------------------


def test_t2_a_rerun_after_a_stop_skips_the_clean_repositories(capsys):
    gh = FakeGitHub({"alpha": repo(BOTH, BOTH), "beta": repo(BOTH, BOTH),
                     "gamma": repo(BOTH, BOTH)})
    refused = ("DELETE", "/repos/owner/beta/dependabot/secrets/REVIEWER_APP_ID")
    gh.refuse[refused] = 403

    assert run(gh, apply=True) == 1
    err = capsys.readouterr().err
    assert "STOPPED at delete in beta" in err
    assert "beta dependabot/REVIEWER_APP_ID: DELETE answered HTTP 403" in err
    assert "cleaned 1, already clean 0, not finished 2 of 3" in err
    assert not any("/gamma/" in p for p in gh.deletes()), "the run went on past the stop"
    assert gh.repos["alpha"] == repo()
    assert gh.repos["beta"]["actions"] == set()
    assert gh.repos["beta"]["dependabot"] == BOTH

    del gh.refuse[refused]
    gh.calls.clear()
    assert run(gh, apply=True) == 0
    out = capsys.readouterr().out
    assert "[1/3] alpha: clean" in out
    assert not any("/alpha/" in p for p in gh.deletes())
    assert gh.deletes() == sorted(
        ["/repos/owner/beta/dependabot/secrets/REVIEWER_APP_ID",
         "/repos/owner/beta/dependabot/secrets/REVIEWER_APP_PRIVATE_KEY"] + every("gamma"))
    assert all(gh.repos[n] == repo() for n in gh.repos)
    assert "Done: cleaned 2, already clean 1, of 3." in out


def test_a_read_back_that_still_finds_the_secret_stops_the_run(capsys):
    gh = FakeGitHub({"alpha": repo(BOTH), "beta": repo(BOTH)})
    gh.sticky.add(("alpha", "actions", "REVIEWER_APP_PRIVATE_KEY"))
    assert run(gh, apply=True) == 1
    err = capsys.readouterr().err
    assert "read back: alpha actions/REVIEWER_APP_PRIVATE_KEY: still there" in err
    assert not any("/beta/" in p for p in gh.deletes())


def test_a_read_neither_200_nor_404_stops_even_the_dry_run(capsys):
    gh = FakeGitHub({"alpha": repo(), "beta": repo(BOTH), "gamma": repo(BOTH)})
    gh.refuse[("GET", "/repos/owner/beta/actions/secrets/REVIEWER_APP_ID")] = 403
    assert run(gh, apply=False) == 1
    err = capsys.readouterr().err
    assert "STOPPED at read beta" in err and "HTTP 403" in err
    assert "listed 1 of 3 before the stop" in err and "Nothing was deleted." in err
    assert not any("/gamma/" in p for _, p in gh.calls), "an unreadable repo was read as clean"
    assert gh.deletes() == []


def test_an_archived_repository_that_refuses_is_named_with_what_to_do(capsys):
    gh = FakeGitHub({"old": repo(BOTH, archived=True)})
    gh.refuse[("DELETE", "/repos/owner/old/actions/secrets/REVIEWER_APP_ID")] = 403
    assert run(gh, apply=True) == 1
    err = capsys.readouterr().err
    assert "old actions/REVIEWER_APP_ID" in err and "archived" in err and "unarchive" in err


def test_a_failed_decrypt_stops_before_any_call(capsys):
    @contextlib.contextmanager
    def refusing(reason=None):
        raise RuntimeError("gpg decrypt failed after 5 attempts.")
        yield  # pragma: no cover

    gh = FakeGitHub({"alpha": repo(BOTH)})
    assert frs.run(True, session=refusing, request=gh) == 1
    captured = capsys.readouterr()
    assert "Step 1: decrypting the classic PAT" in captured.out
    assert "STOPPED at decrypt: gpg decrypt failed" in captured.err
    assert "never listed, so nothing was deleted" in captured.err
    assert gh.calls == []


def test_a_failed_token_check_stops_before_the_listing(capsys):
    gh = FakeGitHub({"alpha": repo(BOTH)})
    gh.refuse[("GET", "/user")] = 401
    assert run(gh, apply=True) == 1
    assert "STOPPED at token check" in capsys.readouterr().err
    assert gh.calls == [("GET", "/user")]


# ---------------------------------------------------------------------------
# The dry run, the listing and what is printed
# ---------------------------------------------------------------------------


def test_the_dry_run_deletes_nothing_and_names_the_holders(capsys):
    gh = FakeGitHub({"alpha": repo(BOTH, {"REVIEWER_APP_ID"}), "beta": repo({"KEEP"})})
    assert run(gh, apply=False) == 0
    out = capsys.readouterr().out
    assert gh.deletes() == []
    assert gh.repos["alpha"] == repo(BOTH, {"REVIEWER_APP_ID"})
    assert ("alpha: holds actions/REVIEWER_APP_ID, actions/REVIEWER_APP_PRIVATE_KEY, "
            "dependabot/REVIEWER_APP_ID") in out
    assert "[2/2] beta: clean" in out
    assert "Done (dry run): 1 of 2 repositories hold a Cerberus secret: alpha." in out
    assert f"{frs.COMMAND} --apply" in out


def test_after_an_apply_the_dry_run_lists_no_holder(capsys):
    """T3's check, on the fake: what the operator's dry run says once --apply is done."""
    gh = FakeGitHub({"alpha": repo(BOTH, BOTH), "beta": repo({"KEEP"}, BOTH)})
    assert run(gh, apply=True) == 0
    capsys.readouterr()
    assert run(gh, apply=False) == 0
    out = capsys.readouterr().out
    assert out.rstrip().endswith("Done (dry run): no repository of the 2 holds either secret.")


def test_it_prints_before_and_after_the_decryption(capsys):
    gh = FakeGitHub({"alpha": repo(BOTH)})
    assert run(gh, apply=True) == 0
    before, after = capsys.readouterr().out.split("<<decrypt>>")
    assert "Step 1: decrypting the classic PAT. A box will ask for its passphrase." in before
    assert after.lstrip("\n").startswith("  decrypted; the PAT stays inside this process.")
    for line in ("Step 2: checking the token", "Step 3: listing the repositories",
                 "Step 4: reading each repository", "deleted   actions/REVIEWER_APP_ID",
                 "read back actions/REVIEWER_APP_ID: gone", "alpha: cleaned"):
        assert line in after


def test_the_listing_pages_and_puts_archived_repositories_last(monkeypatch, capsys):
    monkeypatch.setattr(frs, "PER_PAGE", 2)
    gh = FakeGitHub({"aaa-old": repo(archived=True), "delta": repo(), "Bravo": repo(),
                     "charlie": repo(), "echo": repo()})
    assert run(gh, apply=False) == 0
    assert gh.pages == [1, 2, 3]
    out = capsys.readouterr().out
    order = re.findall(r"\[\d/5\] ([\w-]+)", out)
    assert order == ["Bravo", "charlie", "delta", "echo", "aaa-old"]
    assert "[5/5] aaa-old (archived): clean" in out


def test_the_repo_flag_limits_the_run_and_an_unknown_name_stops_it(capsys):
    gh = FakeGitHub({"alpha": repo(BOTH), "beta": repo(BOTH)})
    assert run(gh, apply=True, only=["beta"]) == 0
    assert gh.deletes() == sorted(f"/repos/owner/beta/actions/secrets/{n}" for n in frs.SECRETS)
    assert gh.repos["alpha"]["actions"] == BOTH
    capsys.readouterr()

    gh.calls.clear()
    assert run(gh, apply=True, only=["nope"]) == 1
    assert "--repo names ['nope']" in capsys.readouterr().err
    assert gh.deletes() == []


def test_the_session_reason_names_no_repository():
    reasons = []

    @contextlib.contextmanager
    def recording(reason=None):
        reasons.append(reason)
        yield "fake-pat"

    gh = FakeGitHub({"secretproject": repo(BOTH)})
    assert frs.run(False, session=recording, request=gh) == 0
    assert reasons and "secretproject" not in reasons[0]


# ---------------------------------------------------------------------------
# Standard 0017 and ADR-0216
# ---------------------------------------------------------------------------


def test_every_flag_the_docstring_names_is_recognized():
    named = set(re.findall(r"(?<![\w-])--[a-z][a-z-]+", frs.__doc__))
    assert named == {"--apply", "--repo"}
    args = frs.parse_args(["--apply", "--repo", "a", "--repo", "b"])
    assert args.apply is True and args.repo == ["a", "b"]
    args = frs.parse_args([])
    assert args.apply is False and args.repo is None


def test_the_pat_never_reaches_argv_or_the_environment():
    tree = ast.parse((TOOLS / "fleet_remove_cerberus_secrets.py").read_text(encoding="utf-8"))
    imported = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    imported |= {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert not imported & {"os", "subprocess"}
    assert not any(isinstance(n, ast.Attribute) and n.attr == "environ" for n in ast.walk(tree))
    assert "classic_pat_session" in {a.name for n in ast.walk(tree)
                                     if isinstance(n, ast.ImportFrom) for a in n.names}
