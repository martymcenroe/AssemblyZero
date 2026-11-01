"""#4501: mechanical validation refuses an Add on a path that already exists.

The Add branch asked only whether the parent existed, so an approved LLD could
list a target's core module, and the directories above it, as new. The spec and
implementation stages turn such an Add into a Modify, so nothing is overwritten;
the wrong document had landed by then.
"""

from __future__ import annotations

import importlib

import pytest

vm = importlib.import_module("assemblyzero.workflows.requirements.nodes.validate_mechanical")


def _add(path: str, *, directory: bool = False) -> dict:
    return {"path": path, "change_type": "Add", "is_directory": directory}


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "web" / "shared").mkdir(parents=True)
    (tmp_path / "web" / "shared" / "engine.ts").write_text("x\n", encoding="utf-8")
    return tmp_path


class TestAnAddOnSomethingThatExists:
    def test_t1_a_file_is_refused_and_told_to_modify(self, repo):
        errors = vm.validate_file_paths([_add("web/shared/engine.ts")], repo)

        assert len(errors) == 1
        assert errors[0].severity == vm.ValidationSeverity.ERROR
        assert "web/shared/engine.ts" in errors[0].message
        assert "Modify" in errors[0].message

    def test_t2_a_directory_is_refused(self, repo):
        errors = vm.validate_file_paths([_add("web/shared", directory=True)], repo)

        assert len(errors) == 1
        assert "web/shared" in errors[0].message

    def test_t3_a_file_only_on_the_base_is_refused(self, repo, monkeypatch):
        monkeypatch.setattr(vm, "_exists_on_base", lambda root, base, path: True)

        errors = vm.validate_file_paths(
            [_add("web/shared/landed_earlier.ts")], repo, base_branch="attempt",
        )

        assert len(errors) == 1
        assert "landed_earlier.ts" in errors[0].message

    def test_the_table_the_real_run_approved_is_refused_row_by_row(self, repo):
        (repo / "web" / "tests").mkdir()
        files = [
            _add("web", directory=True),
            _add("web/shared", directory=True),
            _add("web/tests", directory=True),
            _add("web/shared/engine.ts"),
            _add("web/tests/stocks.test.ts"),
        ]

        errors = vm.validate_file_paths(files, repo)

        assert [e.file_path for e in errors] == [
            "web", "web/shared", "web/tests", "web/shared/engine.ts",
        ]


class TestARealAdd:
    def test_t4_a_new_file_in_an_existing_directory_passes(self, repo):
        assert vm.validate_file_paths([_add("web/shared/stocks.ts")], repo) == []

    def test_t4_a_new_file_in_a_new_directory_passes(self, repo):
        files = [_add("web/new", directory=True), _add("web/new/file.ts")]

        assert vm.validate_file_paths(files, repo) == []

    def test_t4_a_new_path_with_no_base_declared_asks_nothing_of_git(self, repo, monkeypatch):
        def refuse(root, base, path):
            assert base == "", "with no base there is nothing to ask"
            return False

        monkeypatch.setattr(vm, "_exists_on_base", refuse)

        assert vm.validate_file_paths([_add("web/shared/stocks.ts")], repo) == []
