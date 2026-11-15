"""tools/store_pr_sentinel_app_key.py and tools/_github_app_jwt.py (#4784).

No real gpg, no network, no real key, no real home folder: gpg and
gpg-connect-agent are faked by replacing subprocess.run, GitHub by replacing
urllib's urlopen, the key is generated here, and every path is under tmp_path.

poetry run pytest tests/unit/test_store_pr_sentinel_app_key.py -q
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import stat
import subprocess
import sys
import urllib.error
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import _github_app_jwt
import _pat_session
import fleet_ids
import store_pr_sentinel_app_key as store

APP_ID = "987654321"
PASSPHRASE = b"a passphrase"


@pytest.fixture(scope="module")
def key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="module")
def pem_text(key) -> str:
    return key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ).decode("ascii")


@pytest.fixture
def pem_file(tmp_path, pem_text) -> Path:
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    path = downloads / "pr-sentinel.private-key.pem"
    path.write_text(pem_text, encoding="ascii", newline="\n")
    return path


@pytest.fixture
def out(tmp_path) -> Path:
    return tmp_path / "home" / ".secrets" / "pr-sentinel-app.gpg"


@pytest.fixture(autouse=True)
def app_id(monkeypatch):
    monkeypatch.setattr(store.fleet_ids, "get", lambda key: APP_ID)


class _Response:
    def __init__(self, status, body):
        self.status, self._body = status, body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeGitHub:
    def __init__(self, status=200, app_id=int(APP_ID)):
        self.status, self.app_id, self.requests = status, app_id, []

    def urlopen(self, request, timeout=None):
        self.requests.append(request)
        if self.status != 200:
            body = json.dumps({"message": "A JSON web token could not be decoded"}).encode()
            raise urllib.error.HTTPError(request.full_url, self.status, "no", {}, io.BytesIO(body))
        return _Response(200, json.dumps({"id": self.app_id, "slug": "pr-sentinel-test"}).encode())


class FakeGpg:
    """gpg and gpg-connect-agent. Plaintext stays in memory; every call snapshots tmp_path."""

    def __init__(self, root, decrypt_changes=False, encrypt_fails=None):
        self.root, self.decrypt_changes, self.encrypt_fails = root, decrypt_changes, encrypt_fails
        self.calls, self.snapshots, self.plain = [], [], {}

    def __call__(self, args, **kwargs):
        argv = list(args)
        self.calls.append({"argv": argv, "env": kwargs.get("env") or dict(os.environ), "input": kwargs.get("input")})
        self.snapshots.append({p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()})
        if argv[0] == "gpg-connect-agent":
            return subprocess.CompletedProcess(argv, 0, stdout=f"OK {PASSPHRASE.hex()}\n", stderr="")
        if "--symmetric" in argv:
            target = Path(argv[argv.index("--output") + 1])
            target.write_bytes(b"FAKE CIPHERTEXT " + hashlib.sha256(kwargs["input"]).hexdigest().encode())
            if self.encrypt_fails == "interrupt":
                raise KeyboardInterrupt
            if self.encrypt_fails == "cancel":
                return subprocess.CompletedProcess(argv, 2, stdout=b"", stderr=b"gpg: cancelled by user")
            self.plain[argv[argv.index("--output") + 1]] = kwargs["input"]
            return subprocess.CompletedProcess(argv, 0, stdout=b"", stderr=b"")
        plaintext = self.plain[argv[-1]].decode("ascii")
        if self.decrypt_changes:
            plaintext = "1" + plaintext
        return subprocess.CompletedProcess(argv, 0, stdout=plaintext, stderr="")


@pytest.fixture
def github(monkeypatch):
    fake = FakeGitHub()
    monkeypatch.setattr(store.urllib.request, "urlopen", fake.urlopen)
    return fake


@pytest.fixture
def gpg(monkeypatch, tmp_path):
    fake = FakeGpg(tmp_path)
    monkeypatch.setattr(store.subprocess, "run", fake)
    monkeypatch.setenv("GPG_TTY", "/dev/pts/9")
    return fake


def _run(capsys, *argv):
    code = store.main([str(a) for a in argv])
    lines = capsys.readouterr().out.strip().splitlines()
    return code, lines


def _decode(part: str) -> dict:
    return json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))


def test_mint_app_jwt_is_rs256_signed_by_the_key_with_iss_the_app_id(key, pem_text):
    token = _github_app_jwt.mint_app_jwt(APP_ID, pem_text)
    header, payload, signature = token.split(".")
    assert _decode(header) == {"alg": "RS256", "typ": "JWT"}
    claims = _decode(payload)
    assert claims["iss"] == APP_ID and claims["exp"] - claims["iat"] == 600
    key.public_key().verify(
        base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4)),
        f"{header}.{payload}".encode(), padding.PKCS1v15(), hashes.SHA256(),
    )


def test_the_app_id_comes_from_config_fleet_ids(monkeypatch):
    monkeypatch.undo()
    assert store._app_id() == fleet_ids.get("pr_sentinel_app_id")
    assert store._app_id().isdigit()


def test_dry_run_asks_github_as_the_app_and_changes_nothing(capsys, pem_file, pem_text, out, github, gpg, key):
    code, lines = _run(capsys, "--pem", pem_file, "--out", out)
    assert code == 0 and lines[-1] == "OK: dry run, nothing changed"
    assert gpg.calls == [] and not out.parent.exists()
    assert pem_file.read_text(encoding="ascii") == pem_text
    (request,) = github.requests
    assert request.full_url == "https://api.github.com/app"
    token = request.get_header("Authorization").removeprefix("Bearer ")
    assert _decode(token.split(".")[1])["iss"] == APP_ID
    assert f"--pem {pem_file}" in lines[-2] and lines[-2].endswith("--apply")


@pytest.mark.parametrize("apply", [False, True])
@pytest.mark.parametrize(("status", "answered_id"), [(401, int(APP_ID)), (200, 123)])
def test_github_refusing_the_key_stops_and_keeps_it(
    capsys, monkeypatch, pem_file, pem_text, out, gpg, apply, status, answered_id,
):
    monkeypatch.setattr(store.urllib.request, "urlopen", FakeGitHub(status, answered_id).urlopen)
    code, lines = _run(capsys, "--pem", pem_file, "--out", out, *(["--apply"] if apply else []))
    assert code == 1 and lines[-1].startswith("FAILED: prove the key with GitHub")
    if status == 401:
        assert "Private keys" in lines[-1]
    assert pem_file.read_text(encoding="ascii") == pem_text
    assert not out.exists() and gpg.calls == []


@pytest.mark.parametrize("case", ["missing", "relative", "not a pem", "ec key", "symlink"])
def test_a_bad_key_file_stops_before_gpg_and_github(capsys, tmp_path, pem_file, out, github, gpg, case):
    given = {"missing": tmp_path / "absent.pem", "relative": Path("key.pem")}.get(case, pem_file)
    if case == "not a pem":
        pem_file.write_text("not a key\n", encoding="ascii")
    if case == "ec key":
        pem_file.write_bytes(ec.generate_private_key(ec.SECP256R1()).private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    if case == "symlink":
        if sys.platform == "win32":
            pytest.skip("symbolic links need privilege on Windows")
        given = tmp_path / "link.pem"
        given.symlink_to(pem_file)
    code, lines = _run(capsys, "--pem", given, "--out", out, "--apply")
    assert code == 1 and lines[-1].startswith("FAILED: check --pem")
    assert gpg.calls == [] and github.requests == []


@pytest.mark.parametrize("which", ["out", "tmp"])
def test_an_existing_out_is_refused_and_untouched(capsys, pem_file, out, github, gpg, which):
    out.parent.mkdir(parents=True)
    there = out if which == "out" else out.with_name(out.name + ".tmp")
    there.write_bytes(b"already here")
    code, lines = _run(capsys, "--pem", pem_file, "--out", out, "--apply")
    assert code == 1 and lines[-1].startswith("FAILED: check --out")
    assert there.read_bytes() == b"already here" and pem_file.exists() and gpg.calls == []


def _no_plaintext_anywhere(gpg, pem_file, pem_text):
    body = pem_text.splitlines()[1]
    for snapshot in gpg.snapshots + [{p: p.read_bytes() for p in gpg.root.rglob("*") if p.is_file()}]:
        for path, content in snapshot.items():
            if path != pem_file:
                assert body.encode() not in content, path


def test_apply_pipes_the_bundle_to_gpg_stores_it_and_removes_the_key(capsys, pem_file, pem_text, out, github, gpg):
    code, lines = _run(capsys, "--pem", pem_file, "--out", out, "--apply")
    assert code == 0, lines
    assert lines[-1].startswith("OK: the pr-sentinel App key is stored encrypted at")
    (encrypt,) = [c for c in gpg.calls if "--symmetric" in c["argv"]]
    assert encrypt["input"] == f"{APP_ID}\n{pem_text}".encode()
    assert encrypt["env"]["GPG_TTY"] == "/dev/pts/9"
    body = pem_text.splitlines()[1]
    for call in gpg.calls:
        for text in [*call["argv"], *call["env"].values()]:
            assert body not in text and APP_ID not in text and "PRIVATE KEY" not in text
    _no_plaintext_anywhere(gpg, pem_file, pem_text)
    assert out.is_file() and not out.with_name(out.name + ".tmp").exists()
    assert not pem_file.exists()
    if sys.platform != "win32":
        assert stat.S_IMODE(out.stat().st_mode) == 0o600
        assert stat.S_IMODE(out.parent.stat().st_mode) == 0o700
    printed = "\n".join(lines)
    assert "-----BEGIN RSA PRIVATE KEY-----" in printed and body not in printed
    assert "download history" in printed and "Recycle Bin" in printed


@pytest.mark.parametrize("failure", ["decrypt changes", "cancel"])
def test_a_failed_store_keeps_the_key_and_removes_the_tmp(capsys, pem_file, pem_text, out, github, gpg, failure):
    gpg.decrypt_changes = failure == "decrypt changes"
    gpg.encrypt_fails = "cancel" if failure == "cancel" else None
    code, lines = _run(capsys, "--pem", pem_file, "--out", out, "--apply")
    assert code == 1
    assert lines[-1].startswith("FAILED: check the file" if failure == "decrypt changes" else "FAILED: encrypt")
    assert pem_file.read_text(encoding="ascii") == pem_text
    assert not out.exists() and not out.with_name(out.name + ".tmp").exists()


def test_an_interrupted_encrypt_removes_the_tmp_and_keeps_the_key(pem_file, out, github, gpg):
    gpg.encrypt_fails = "interrupt"
    with pytest.raises(KeyboardInterrupt):
        store.main(["--pem", str(pem_file), "--out", str(out), "--apply"])
    assert pem_file.exists() and not out.with_name(out.name + ".tmp").exists() and not out.exists()


@pytest.mark.skipif(not hasattr(os, "geteuid"), reason="no user id on this OS")
def test_root_is_refused(capsys, monkeypatch, pem_file, out, github, gpg):
    monkeypatch.setattr(store.os, "geteuid", lambda: 0)
    code, lines = _run(capsys, "--pem", pem_file, "--out", out)
    assert code == 1 and lines[-1].startswith("FAILED: refuse root") and github.requests == []


def test_the_old_echo_recipe_is_gone_and_the_docs_name_the_program(tmp_path):
    doc = _pat_session.pr_sentinel_app_session.__doc__
    assert "echo" not in doc and "store_pr_sentinel_app_key.py" in doc
    with pytest.raises(FileNotFoundError) as err, _pat_session.pr_sentinel_app_session(tmp_path / "absent.gpg"):
        pass
    assert "echo <" not in str(err.value) and "store_pr_sentinel_app_key.py" in str(err.value)
    row = [line for line in (ROOT / "sentinel" / "README.md").read_text(encoding="utf-8").splitlines()
           if line.startswith("| Private key |")]
    assert len(row) == 1 and "~/.secrets/pr-sentinel-app.gpg" in row[0]
    assert "store_pr_sentinel_app_key.py" in row[0] and ".pem" not in row[0]
    runbook = (ROOT / "docs" / "runbooks" / "0927-new-repo-human-checklist.md").read_text(encoding="utf-8")
    assert "tools/store_pr_sentinel_app_key.py" in runbook
