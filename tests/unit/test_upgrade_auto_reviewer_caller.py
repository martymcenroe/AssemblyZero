"""tools/upgrade_auto_reviewer_caller.py with the HTTP layer stubbed (#3641)."""

from __future__ import annotations

import base64
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "tools"))

import upgrade_auto_reviewer_caller as uarc  # noqa: E402

STALE = "name: auto-reviewer\n\non:\n  pull_request:\n\njobs:\n  review:\n    secrets: inherit\n"


class Resp:
    def __init__(self, status: int, body=None) -> None:
        self.status_code, self._body, self.text = status, body, ""

    def json(self):
        return self._body

    def raise_for_status(self) -> None:
        if self.status_code >= 300:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeHTTP:
    """Records every call; answers from a table keyed by (method, path suffix)."""

    def __init__(self, file_text: str | None, put_status: int = 200, rulesets=None, secrets=("REVIEWER_APP_ID",
                 "REVIEWER_APP_PRIVATE_KEY")) -> None:  # fmt: skip
        self.file_text, self.put_status = file_text, put_status
        self.rulesets = rulesets or []
        self.secrets = secrets
        self.calls: list[tuple[str, str, dict | None]] = []

    def _path(self, url: str) -> str:
        return url.split("/repos/martymcenroe/x", 1)[1]

    def get(self, url, **kw):
        p = self._path(url)
        self.calls.append(("GET", p, None))
        if p.endswith("auto-reviewer.yml"):
            if self.file_text is None:
                return Resp(404)
            enc = base64.b64encode(self.file_text.encode()).decode()
            return Resp(200, {"content": enc, "sha": "abc1234def"})
        if p == "/rulesets":
            return Resp(200, [{"id": r["id"], "enforcement": "active", "target": "branch"} for r in self.rulesets])
        if p.startswith("/rulesets/"):
            rid = int(p.rsplit("/", 1)[1])
            return Resp(200, next(r for r in self.rulesets if r["id"] == rid))
        if p.endswith("/protection"):
            return Resp(404)
        if p == "/actions/secrets":
            return Resp(200, {"secrets": [{"name": n} for n in self.secrets]})
        return Resp(404)

    def put(self, url, json=None, **kw):
        p = self._path(url)
        self.calls.append(("PUT", p, json))
        if p.endswith("auto-reviewer.yml"):
            return Resp(self.put_status)
        return Resp(200)

    def post(self, url, **kw):
        self.calls.append(("POST", self._path(url), None))
        return Resp(200)

    def delete(self, url, **kw):
        self.calls.append(("DELETE", self._path(url), None))
        return Resp(200)


def repo(http: FakeHTTP) -> uarc.Repo:
    return uarc.Repo("x", "main", "token-not-real", http=http)


def test_a_missing_file_is_refused() -> None:
    http = FakeHTTP(None)
    assert uarc.upgrade(repo(http), 11, apply=True) == 1
    assert not [c for c in http.calls if c[0] == "PUT"]


def test_a_canonical_file_is_left_alone() -> None:
    http = FakeHTTP(uarc.CALLER_WORKFLOW)
    assert uarc.upgrade(repo(http), 11, apply=True) == 0
    assert not [c for c in http.calls if c[0] == "PUT"]


def test_a_stale_file_is_replaced_with_the_canonical_caller_and_closes_the_issue() -> None:
    http = FakeHTTP(STALE)
    assert uarc.upgrade(repo(http), 11, apply=True) == 0
    puts = [c for c in http.calls if c[0] == "PUT" and c[1].endswith("auto-reviewer.yml")]
    assert len(puts) == 1
    body = puts[0][2]
    assert base64.b64decode(body["content"]).decode() == uarc.CALLER_WORKFLOW
    assert "Closes #11" in body["message"] and body["sha"] == "abc1234def"


def test_the_dry_run_writes_nothing() -> None:
    http = FakeHTTP(STALE)
    assert uarc.upgrade(repo(http), 11, apply=False) == 0
    assert not [c for c in http.calls if c[0] in ("PUT", "POST", "DELETE")]


def test_protection_is_restored_when_the_put_fails() -> None:
    ruleset = {"id": 7, "name": "main", "target": "branch", "enforcement": "active", "bypass_actors": [],
               "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"]}}, "rules": []}  # fmt: skip
    http = FakeHTTP(STALE, put_status=422, rulesets=[ruleset])
    with pytest.raises(RuntimeError):
        uarc.upgrade(repo(http), 11, apply=True)
    ruleset_puts = [c for c in http.calls if c[0] == "PUT" and c[1] == "/rulesets/7"]
    assert len(ruleset_puts) == 2, "one to add the bypass, one to restore it"
    assert ruleset_puts[-1][2]["bypass_actors"] == []


def test_the_caller_is_the_canonical_constant() -> None:
    import new_repo

    assert uarc.CALLER_WORKFLOW is new_repo._CANONICAL_AUTO_REVIEWER_CALLER
