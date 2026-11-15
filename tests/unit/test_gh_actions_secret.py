"""set_secret in tools/gh_actions_secret.py, and the post-create hook import contract (#4783).

An operator-configured post-create hook, which lives outside this repository, sets a
repository secret with `set_secret(repo, name, value, pat, scope)`. When the module that
held it was removed, nothing here failed and the hook died on import in the operator's
run. These tests pin both halves:

- `set_secret` against a fake GitHub: no network, a real PyNaCl key pair, so the sealed
  value is proven to open to what was sent;
- every module and name `new_repo.HOOK_IMPORTABLE` lists imports from `tools/`, directly
  and through a hook file run by `run_post_create_hooks`, so removing one fails the suite.
"""

from __future__ import annotations

import base64
import importlib
import inspect
import sys
from pathlib import Path

import pytest
import requests
from nacl import encoding, public
from nacl.exceptions import CryptoError

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import _gh_retry
import gh_actions_secret
import new_repo
from gh_actions_secret import SCOPES, set_secret

API = "https://api.github.com"
OWNER = "martymcenroe"
REPO = "ThrowAway"
FAKE_PAT = "ghp_fake_classic_pat_for_testing_only"
SECRET_NAME = "SOME_READ_TOKEN"
SECRET_VALUE = "github_pat_fake_read_only_token_for_testing"


class FakeResponse:
    def __init__(self, status_code: int, body: dict | None = None):
        self.status_code = status_code
        self._body = body or {}
        self.headers: dict[str, str] = {}

    def json(self) -> dict:
        return self._body

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class FakeGitHub:
    """Answers the two calls set_secret makes; records every request it sees.

    Each (owner, repo, scope) gets its own key pair, as GitHub keeps a separate
    store per scope. `key_status` and `put_status` set the answers; a value of
    None for either raises ConnectionError instead.
    """

    def __init__(self, key_status: int | None = 200, put_status: int | None = 201):
        self.key_status = key_status
        self.put_status = put_status
        self.keys: dict[tuple[str, str, str], tuple[str, public.PrivateKey]] = {}
        self.calls: list[tuple[str, str, dict, dict | None]] = []

    def key_for(self, owner: str, repo: str, scope: str) -> tuple[str, public.PrivateKey]:
        slot = (owner, repo, scope)
        if slot not in self.keys:
            self.keys[slot] = (f"key-id-{owner}-{repo}-{scope}", public.PrivateKey.generate())
        return self.keys[slot]

    def request(self, method, url, headers=None, timeout=None, json=None, **kwargs):
        self.calls.append((method, url, headers or {}, json))
        _, _, path = url.partition(API)
        parts = path.strip("/").split("/")
        # repos/<owner>/<repo>/<scope>/secrets/<public-key | name>
        assert parts[0] == "repos" and parts[4] == "secrets", url
        owner, repo, scope, last = parts[1], parts[2], parts[3], parts[5]
        if method == "GET" and last == "public-key":
            if self.key_status is None:
                raise requests.ConnectionError("no route to the fake GitHub")
            key_id, private = self.key_for(owner, repo, scope)
            b64 = private.public_key.encode(encoding.Base64Encoder()).decode("utf-8")
            return FakeResponse(self.key_status, {"key_id": key_id, "key": b64})
        if method == "PUT":
            if self.put_status is None:
                raise requests.ConnectionError("no route to the fake GitHub")
            return FakeResponse(self.put_status)
        raise AssertionError(f"unexpected call {method} {url}")

    def puts(self) -> list[tuple[str, str, dict, dict | None]]:
        return [c for c in self.calls if c[0] == "PUT"]


@pytest.fixture
def github(monkeypatch):
    """A FakeGitHub behind the retry helper's HTTP call, with its sleeps made instant."""
    fake = FakeGitHub()
    monkeypatch.setattr(_gh_retry.requests, "request", fake.request)
    monkeypatch.setattr(_gh_retry.time, "sleep", lambda _s: None)
    return fake


def _opened(private: public.PrivateKey, encrypted_value: str) -> str:
    sealed = base64.b64decode(encrypted_value)
    return public.SealedBox(private).decrypt(sealed).decode("utf-8")


class TestSetSecret:
    @pytest.mark.parametrize("scope", ["actions", "dependabot"])
    @pytest.mark.parametrize("put_status", [201, 204])
    def test_a_2xx_put_of_the_sealed_value_returns_true(self, github, scope, put_status):
        github.put_status = put_status
        assert set_secret(REPO, SECRET_NAME, SECRET_VALUE, FAKE_PAT, scope) is True

        (get, put) = github.calls
        assert get[0] == "GET"
        assert get[1] == f"{API}/repos/{OWNER}/{REPO}/{scope}/secrets/public-key"
        assert put[0] == "PUT"
        assert put[1] == f"{API}/repos/{OWNER}/{REPO}/{scope}/secrets/{SECRET_NAME}"
        key_id, private = github.keys[(OWNER, REPO, scope)]
        assert put[3]["key_id"] == key_id
        assert _opened(private, put[3]["encrypted_value"]) == SECRET_VALUE

    def test_the_sealed_value_never_carries_the_plaintext(self, github):
        assert set_secret(REPO, SECRET_NAME, SECRET_VALUE, FAKE_PAT) is True
        (put,) = github.puts()
        assert SECRET_VALUE not in str(put[3])
        assert set(put[3]) == {"encrypted_value", "key_id"}

    def test_each_scope_seals_with_its_own_key(self, github):
        for scope in SCOPES:
            assert set_secret(REPO, SECRET_NAME, SECRET_VALUE, FAKE_PAT, scope=scope)
        actions_put, dependabot_put = github.puts()
        _, actions_key = github.keys[(OWNER, REPO, "actions")]
        _, dependabot_key = github.keys[(OWNER, REPO, "dependabot")]
        assert _opened(actions_key, actions_put[3]["encrypted_value"]) == SECRET_VALUE
        assert _opened(dependabot_key, dependabot_put[3]["encrypted_value"]) == SECRET_VALUE
        with pytest.raises(CryptoError):
            _opened(actions_key, dependabot_put[3]["encrypted_value"])

    def test_both_calls_carry_the_pat_as_a_bearer_token(self, github):
        set_secret(REPO, SECRET_NAME, SECRET_VALUE, FAKE_PAT)
        assert [c[2]["Authorization"] for c in github.calls] == [f"Bearer {FAKE_PAT}"] * 2

    def test_the_scope_defaults_to_actions(self, github):
        assert set_secret(REPO, SECRET_NAME, SECRET_VALUE, FAKE_PAT) is True
        assert all("/actions/secrets/" in c[1] for c in github.calls)

    def test_owner_defaults_to_the_fleet_user_and_can_be_named(self, github):
        assert gh_actions_secret.GITHUB_USER == OWNER
        assert set_secret(REPO, SECRET_NAME, SECRET_VALUE, FAKE_PAT, owner="someone") is True
        assert all(c[1].startswith(f"{API}/repos/someone/{REPO}/") for c in github.calls)

    @pytest.mark.parametrize("put_status", [400, 403, 404, 422])
    def test_a_4xx_put_returns_false(self, github, put_status):
        github.put_status = put_status
        assert set_secret(REPO, SECRET_NAME, SECRET_VALUE, FAKE_PAT) is False
        assert len(github.puts()) == 1

    def test_a_put_that_never_connects_returns_false(self, github):
        github.put_status = None
        assert set_secret(REPO, SECRET_NAME, SECRET_VALUE, FAKE_PAT) is False

    @pytest.mark.parametrize("key_status", [301, 403, 404])
    def test_a_failed_key_fetch_returns_false_and_puts_nothing(self, github, key_status):
        github.key_status = key_status
        assert set_secret(REPO, SECRET_NAME, SECRET_VALUE, FAKE_PAT) is False
        assert github.puts() == []

    def test_a_key_fetch_that_never_connects_returns_false_and_puts_nothing(self, github):
        github.key_status = None
        assert set_secret(REPO, SECRET_NAME, SECRET_VALUE, FAKE_PAT) is False
        assert github.puts() == []
        assert len(github.calls) > 1, "the retry helper retries a connection error"

    def test_the_signature_is_the_one_the_hook_calls(self):
        params = list(inspect.signature(set_secret).parameters.values())
        assert [p.name for p in params[:5]] == ["repo", "name", "value", "pat", "scope"]
        assert params[4].default == "actions"
        assert all(p.kind is p.KEYWORD_ONLY for p in params[5:])

    def test_the_scopes_are_actions_and_dependabot(self):
        assert SCOPES == ("actions", "dependabot")


class TestHookImportContract:
    """Requirement 3 of #4783: what a hook may import from tools/ is importable."""

    def test_the_contract_names_both_modules(self):
        assert new_repo.HOOK_IMPORTABLE == {
            "_pat_session": ("gpg_secret_session",),
            "gh_actions_secret": ("set_secret",),
        }

    @pytest.mark.parametrize("module_name", sorted(new_repo.HOOK_IMPORTABLE))
    def test_every_named_module_is_in_tools_and_has_its_names(self, module_name):
        assert (TOOLS / f"{module_name}.py").is_file()
        module = importlib.import_module(module_name)
        assert Path(module.__file__).resolve() == (TOOLS / f"{module_name}.py").resolve()
        for name in new_repo.HOOK_IMPORTABLE[module_name]:
            assert callable(getattr(module, name, None)), f"{module_name}.{name}"

    def test_a_hook_importing_the_whole_contract_runs(self, tmp_path):
        """The runner loads a hook from outside tools/, as the operator's hooks are loaded."""
        lines = [
            f"from {module} import {', '.join(names)}  # noqa: F401"
            for module, names in sorted(new_repo.HOOK_IMPORTABLE.items())
        ]
        lines += [
            "",
            "def post_create(owner, repo, pat):",
            "    return 'imported'",
            "",
        ]
        hook = tmp_path / "contract_hook.py"
        hook.write_text("\n".join(lines), encoding="utf-8")
        results = new_repo.run_post_create_hooks([hook], OWNER, REPO, FAKE_PAT)
        assert results == [(hook, "imported")]

    def test_the_runner_documents_the_contract(self):
        doc = new_repo.run_post_create_hooks.__doc__
        assert "HOOK_IMPORTABLE" in doc
        for module, names in new_repo.HOOK_IMPORTABLE.items():
            for name in names:
                assert f"{module}.{name}" in doc
