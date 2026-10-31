"""interface_surface.py under standard 0034, one test per sweep site (#3779).

An empty or partial interface map is the drafter working blind: it invents
the functions this module exists to stop it inventing. Each site used to
return less than the truth with only a warning. Line numbers in the names are
ledger 0908's, at its base ``79e18ad1``.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pytest

import assemblyzero.core.interface_surface as isurf


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "models.py").write_text("class Model:\n    def save(self) -> None: ...\n", encoding="utf-8")
    (pkg / "service.py").write_text(
        "from pkg.models import Model\n\ndef run(m: Model) -> int:\n    return 1\n",
        encoding="utf-8",
    )
    return tmp_path


def _unreadable(monkeypatch, target: Path) -> None:
    real = Path.read_text

    def read_text(self, *args, **kwargs):
        if self.resolve() == target.resolve():
            raise PermissionError("permission denied")
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_text)


class TestNoLessThanTheTruth:
    def test_107_a_file_that_does_not_parse_raises(self):
        with pytest.raises(SyntaxError):
            isurf.summarize_python_file("def broken(:\n")

    def test_267_a_walk_that_fails_raises(self, repo, monkeypatch):
        def rglob(self, pattern):
            raise PermissionError("cannot list")

        monkeypatch.setattr(Path, "rglob", rglob)
        with pytest.raises(PermissionError):
            isurf.list_repo_python_files(repo)

    def test_319_an_import_target_that_cannot_be_read_raises(self, repo, monkeypatch):
        service = repo / "pkg" / "service.py"
        _unreadable(monkeypatch, service)
        with pytest.raises(PermissionError):
            isurf.resolve_import_targets(service, repo.resolve())

    def test_394_an_unreadable_file_raises_instead_of_leaving_the_map(self, repo, monkeypatch):
        models = repo / "pkg" / "models.py"
        _unreadable(monkeypatch, models)
        with pytest.raises(PermissionError):
            isurf.extract_interface_map([models], repo.resolve())

    def test_402_files_left_out_for_budget_are_named(self, repo, caplog):
        paths = [repo / "pkg" / "models.py", repo / "pkg" / "service.py"]
        with caplog.at_level(logging.WARNING, logger="assemblyzero.core.interface_surface"):
            surface = isurf.extract_interface_map(paths, repo.resolve(), total_char_cap=60)
        assert len(surface) < 2
        assert any("pkg/service.py" in r.getMessage() or "pkg/models.py" in r.getMessage()
                   for r in caplog.records)

    def test_408_a_file_outside_the_root_raises(self, repo, tmp_path_factory):
        outside = tmp_path_factory.mktemp("elsewhere") / "models.py"
        outside.write_text("def f(): ...\n", encoding="utf-8")
        with pytest.raises(ValueError):
            isurf.extract_interface_map([outside], repo.resolve())

    def test_445_a_root_that_is_not_a_directory_raises(self, tmp_path):
        with pytest.raises(NotADirectoryError):
            isurf.build_interface_map(tmp_path / "gone")

    def test_449_a_repo_with_no_python_is_empty_and_said(self, tmp_path, caplog):
        (tmp_path / "index.js").write_text("export const x = 1;\n", encoding="utf-8")
        with caplog.at_level(logging.INFO, logger="assemblyzero.core.interface_surface"):
            assert isurf.build_interface_map(tmp_path) == {}
        assert any("no Python files" in r.getMessage() for r in caplog.records)

    def test_472_a_related_path_that_cannot_be_resolved_raises(self, repo, monkeypatch):
        """Mode 2 runs when the whole repo does not fit; force it."""
        monkeypatch.setattr(isurf, "WHOLE_SURFACE_MAX_FILES", 0)
        real_resolve = Path.resolve

        def resolve(self, *args, **kwargs):
            if self.name == "bad.py":
                raise OSError("too many levels of symbolic links")
            return real_resolve(self, *args, **kwargs)

        monkeypatch.setattr(Path, "resolve", resolve)
        with pytest.raises(OSError, match="symbolic links"):
            isurf.build_interface_map(repo, related_paths=[repo / "pkg" / "bad.py"])

    def test_492_an_extraction_failure_raises_instead_of_an_empty_map(self, repo, monkeypatch):
        _unreadable(monkeypatch, repo / "pkg" / "models.py")
        with pytest.raises(PermissionError):
            isurf.build_interface_map(repo)

    def test_518_a_revision_root_that_is_not_a_directory_raises(self, tmp_path):
        with pytest.raises(NotADirectoryError):
            isurf.build_interface_map_for_paths(["pkg/service.py"], tmp_path / "gone")

    def test_552_a_revision_extraction_failure_raises(self, repo, monkeypatch):
        _unreadable(monkeypatch, repo / "pkg" / "service.py")
        with pytest.raises(PermissionError):
            isurf.build_interface_map_for_paths(["pkg/service.py"], repo)

    def test_a_readable_repo_still_gives_its_whole_surface(self, repo):
        surface = isurf.build_interface_map(repo)
        assert {"pkg/models.py", "pkg/service.py"} <= set(surface)
