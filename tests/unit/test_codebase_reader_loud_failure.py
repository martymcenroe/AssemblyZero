"""The codebase reader raises when a file it was asked to read cannot be read (ADR 0236, #3585).

The reader builds the codebase context a requirements run drafts from. A file
that exists but could not be stat'd, resolved, decoded or read used to come back
as empty content, and the batch reader dropped it, so the draft was built on a
partial context with nothing said. A symlink that escapes the repo was dropped
with a WARNING. A ``pyproject.toml`` or ``package.json`` that does not parse
became ``{}``. Each now raises ``CodebaseReadError`` naming the file and the
cause.

What stays quiet, by contract: a file that does not exist, is not a regular
file, has a binary extension, or matches a sensitive pattern. Those are answers
("there is no text here to read"), not failures.

One test per ledger site, named for the line the ledger gives at ``79e18ad1``.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import pytest

from assemblyzero.utils.codebase_reader import (
    parse_project_metadata,
    read_file_with_budget,
    read_files_within_budget,
)


class _Raised:
    value: BaseException


@contextmanager
def _raises_read_error():
    """Expect ``CodebaseReadError``. Matched by name, so that against a module
    which predates the class each site test fails on "did not raise", which is
    the behaviour being fixed, rather than on a missing attribute."""
    caught = _Raised()
    try:
        yield caught
    except Exception as exc:  # noqa: BLE001 - the type is asserted below
        assert type(exc).__name__ == "CodebaseReadError", repr(exc)
        caught.value = exc
        return
    pytest.fail("did not raise CodebaseReadError")


def _patch(monkeypatch, name: str, target: Path, exc: Exception) -> None:
    """Make ``Path.<name>`` raise ``exc`` for ``target`` only."""
    real = getattr(Path, name)

    def fake(self, *args, **kwargs):
        if str(self) == str(target):
            raise exc
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, name, fake)


def test_152_a_file_that_cannot_be_stat_ed_raises(tmp_path, monkeypatch, operator_alerts):
    target = tmp_path / "CLAUDE.md"
    target.write_text("rules", encoding="utf-8")
    _patch(monkeypatch, "is_file", target, PermissionError(13, "Permission denied"))

    with _raises_read_error() as raised:
        read_file_with_budget(target)

    assert str(target) in str(raised.value)
    assert "PermissionError" in str(raised.value)


def test_164_a_symlink_that_escapes_the_repo_raises_naming_both_paths(tmp_path, operator_alerts):
    outside = tmp_path / "outside" / "secret.txt"
    outside.parent.mkdir()
    outside.write_text("TOP SECRET DATA", encoding="utf-8")
    repo = tmp_path / "repo"
    repo.mkdir()
    link = repo / "linked.txt"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("cannot create symlinks here")

    with _raises_read_error() as raised:
        read_file_with_budget(link, repo_root=repo)

    message = str(raised.value)
    assert str(link) in message
    assert str(outside.resolve()) in message
    assert "TOP SECRET DATA" not in message


def test_171_a_path_that_cannot_be_resolved_raises(tmp_path, monkeypatch, operator_alerts):
    target = tmp_path / "README.md"
    target.write_text("readme", encoding="utf-8")
    _patch(monkeypatch, "resolve", target, OSError(40, "Too many levels of symbolic links"))

    with _raises_read_error() as raised:
        read_file_with_budget(target)

    assert str(target) in str(raised.value)


def test_198_a_text_file_that_is_not_utf8_raises(tmp_path, operator_alerts):
    target = tmp_path / "notes.txt"
    target.write_bytes(b"caf\xe9\n")

    with _raises_read_error() as raised:
        read_file_with_budget(target)

    assert str(target) in str(raised.value)
    assert "UnicodeDecodeError" in str(raised.value)


def test_201_a_file_that_cannot_be_read_raises(tmp_path, monkeypatch, operator_alerts):
    target = tmp_path / "README.md"
    target.write_text("readme", encoding="utf-8")
    _patch(monkeypatch, "read_text", target, PermissionError(13, "Permission denied"))

    with _raises_read_error() as raised:
        read_file_with_budget(target)

    assert str(target) in str(raised.value)


def test_201_the_batch_reader_does_not_drop_an_unreadable_file(tmp_path, monkeypatch, operator_alerts):
    good = tmp_path / "CLAUDE.md"
    good.write_text("rules", encoding="utf-8")
    bad = tmp_path / "README.md"
    bad.write_text("readme", encoding="utf-8")
    _patch(monkeypatch, "read_text", bad, PermissionError(13, "Permission denied"))

    with _raises_read_error():
        read_files_within_budget([good, bad])


def test_340_a_pyproject_that_does_not_parse_raises(tmp_path, operator_alerts):
    (tmp_path / "pyproject.toml").write_text("not valid TOML {{[[[", encoding="utf-8")
    (tmp_path / "package.json").write_text('{"name": "fallback"}', encoding="utf-8")

    with _raises_read_error() as raised:
        parse_project_metadata(tmp_path)

    assert "pyproject.toml" in str(raised.value)


def test_369_a_package_json_that_does_not_parse_raises(tmp_path, operator_alerts):
    (tmp_path / "package.json").write_text("{not valid json!!!}", encoding="utf-8")

    with _raises_read_error() as raised:
        parse_project_metadata(tmp_path)

    assert "package.json" in str(raised.value)


def test_a_missing_file_is_a_quiet_empty_answer(tmp_path, operator_alerts):
    result = read_file_with_budget(tmp_path / "absent.md")

    assert result["content"] == ""
    assert operator_alerts == []


def test_a_binary_or_sensitive_file_is_a_quiet_empty_answer(tmp_path, operator_alerts):
    image = tmp_path / "logo.png"
    image.write_bytes(b"\x89PNG\r\n")
    secret = tmp_path / ".env"
    secret.write_text("TOKEN=x", encoding="utf-8")

    assert read_file_with_budget(image)["content"] == ""
    assert read_file_with_budget(secret)["content"] == ""
    assert read_files_within_budget([image, secret]) == []


def test_no_config_file_is_a_quiet_empty_dict(tmp_path, operator_alerts):
    assert parse_project_metadata(tmp_path) == {}
