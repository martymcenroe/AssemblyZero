"""Tests for impl-stage import validator. Closes #1500.

The impl-stage validator at
assemblyzero/workflows/testing/nodes/implementation/import_validator.py
resolves internal imports against on-disk module paths. The earlier
version only checked repo_root/Path(*parts), missing src-layout repos
where chiron.provenance lives at src/chiron/provenance.py.
"""

from __future__ import annotations

from pathlib import Path


def test_resolves_flat_layout(tmp_path):
    from assemblyzero.workflows.testing.nodes.implementation.import_validator import (
        _resolve_internal_import,
    )
    (tmp_path / "chiron").mkdir()
    (tmp_path / "chiron" / "provenance.py").write_text("")
    assert _resolve_internal_import("chiron.provenance", tmp_path) is True


def test_resolves_src_layout(tmp_path):
    from assemblyzero.workflows.testing.nodes.implementation.import_validator import (
        _resolve_internal_import,
    )
    (tmp_path / "src" / "chiron").mkdir(parents=True)
    (tmp_path / "src" / "chiron" / "provenance.py").write_text("")
    assert _resolve_internal_import("chiron.provenance", tmp_path) is True


def test_resolves_lib_layout(tmp_path):
    from assemblyzero.workflows.testing.nodes.implementation.import_validator import (
        _resolve_internal_import,
    )
    (tmp_path / "lib" / "foo").mkdir(parents=True)
    (tmp_path / "lib" / "foo" / "bar.py").write_text("")
    assert _resolve_internal_import("foo.bar", tmp_path) is True


def test_resolves_source_layout(tmp_path):
    from assemblyzero.workflows.testing.nodes.implementation.import_validator import (
        _resolve_internal_import,
    )
    (tmp_path / "source" / "foo").mkdir(parents=True)
    (tmp_path / "source" / "foo" / "bar.py").write_text("")
    assert _resolve_internal_import("foo.bar", tmp_path) is True


def test_resolves_python_layout(tmp_path):
    from assemblyzero.workflows.testing.nodes.implementation.import_validator import (
        _resolve_internal_import,
    )
    (tmp_path / "python" / "foo").mkdir(parents=True)
    (tmp_path / "python" / "foo" / "bar.py").write_text("")
    assert _resolve_internal_import("foo.bar", tmp_path) is True


def test_resolves_apps_layout(tmp_path):
    from assemblyzero.workflows.testing.nodes.implementation.import_validator import (
        _resolve_internal_import,
    )
    (tmp_path / "apps" / "foo").mkdir(parents=True)
    (tmp_path / "apps" / "foo" / "bar.py").write_text("")
    assert _resolve_internal_import("foo.bar", tmp_path) is True


def test_resolves_src_layout_via_init(tmp_path):
    from assemblyzero.workflows.testing.nodes.implementation.import_validator import (
        _resolve_internal_import,
    )
    (tmp_path / "src" / "foo" / "bar").mkdir(parents=True)
    (tmp_path / "src" / "foo" / "bar" / "__init__.py").write_text("")
    assert _resolve_internal_import("foo.bar", tmp_path) is True


def test_resolves_parent_module_src_layout(tmp_path):
    """`from chiron.provenance import Citation` resolves when
    src/chiron/provenance.py exists (Citation lives inside).
    """
    from assemblyzero.workflows.testing.nodes.implementation.import_validator import (
        _resolve_internal_import,
    )
    (tmp_path / "src" / "chiron").mkdir(parents=True)
    (tmp_path / "src" / "chiron" / "provenance.py").write_text("class Citation: ...")
    assert _resolve_internal_import("chiron.provenance.Citation", tmp_path) is True


def test_unresolvable_returns_false(tmp_path):
    from assemblyzero.workflows.testing.nodes.implementation.import_validator import (
        _resolve_internal_import,
    )
    assert _resolve_internal_import("nonexistent.module", tmp_path) is False


def test_chiron_iter06_repro(tmp_path):
    """Verbatim shape from iter06 halt: src/chiron/provenance.py exists
    on disk, test file does `from chiron.provenance import Citation`,
    validator must accept.
    """
    from assemblyzero.workflows.testing.nodes.implementation.import_validator import (
        validate_imports,
    )
    (tmp_path / "src" / "chiron").mkdir(parents=True)
    (tmp_path / "src" / "chiron" / "provenance.py").write_text(
        '"""Citation provenance value object."""\nclass Citation: pass\n'
    )
    test_code = (
        '"""Tests for chiron.provenance."""\n'
        "import pytest\n"
        "\n"
        "from chiron.provenance import Citation\n"
        "\n"
        "def test_citation_is_immutable():\n"
        "    pass\n"
    )
    valid, bad = validate_imports(test_code, "tests/unit/test_provenance.py", tmp_path)
    assert valid is True, f"Expected valid, got bad={bad!r}"
    assert bad == []
