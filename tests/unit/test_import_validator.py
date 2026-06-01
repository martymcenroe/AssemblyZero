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


def test_pep621_dependencies_recognized(tmp_path):
    """Closes #1515. PEP 621 [project] dependencies must be recognized
    as third-party. Without this, every PEP 621 repo's deps get flagged
    as 'unresolvable internal' imports."""
    from assemblyzero.workflows.testing.nodes.implementation.import_validator import (
        _read_third_party_packages,
    )
    (tmp_path / "pyproject.toml").write_text(
        '[project]\n'
        'name = "chiron"\n'
        'dependencies = [\n'
        '    "pypdf>=5.0.0",\n'
        '    "pyyaml>=6.0",\n'
        ']\n'
    )
    pkgs = _read_third_party_packages(tmp_path)
    assert "pypdf" in pkgs
    assert "pyyaml" in pkgs


def test_pep621_optional_dependencies_recognized(tmp_path):
    """Closes #1515. [project.optional-dependencies] also recognized."""
    from assemblyzero.workflows.testing.nodes.implementation.import_validator import (
        _read_third_party_packages,
    )
    (tmp_path / "pyproject.toml").write_text(
        '[project]\n'
        'name = "chiron"\n'
        'dependencies = []\n'
        '[project.optional-dependencies]\n'
        'extras = ["rich>=13"]\n'
    )
    pkgs = _read_third_party_packages(tmp_path)
    assert "rich" in pkgs


def test_pep735_dependency_groups_recognized(tmp_path):
    """Closes #1515. [dependency-groups] (PEP 735, uv/hatch) recognized."""
    from assemblyzero.workflows.testing.nodes.implementation.import_validator import (
        _read_third_party_packages,
    )
    (tmp_path / "pyproject.toml").write_text(
        '[project]\n'
        'name = "chiron"\n'
        'dependencies = []\n'
        '[dependency-groups]\n'
        'dev = ["pytest (>=9.0.3,<10.0.0)"]\n'
    )
    pkgs = _read_third_party_packages(tmp_path)
    assert "pytest" in pkgs


def test_chiron_iter07_pyproject_repro(tmp_path):
    """Closes #1515. Verbatim Chiron #37 iter07 pyproject shape:
    PEP 621 [project] with pypdf + pyyaml. Validator must pick them up."""
    from assemblyzero.workflows.testing.nodes.implementation.import_validator import (
        validate_imports,
    )
    (tmp_path / "pyproject.toml").write_text(
        '[project]\n'
        'name = "chiron"\n'
        'version = "0.1.0"\n'
        'dependencies = [\n'
        '    "pypdf>=5.0.0",\n'
        '    "pyyaml>=6.0",\n'
        ']\n'
    )
    (tmp_path / "src" / "chiron" / "corpus").mkdir(parents=True)
    (tmp_path / "src" / "chiron" / "corpus" / "__init__.py").write_text("")

    code = (
        '"""Extract MPEP PDFs."""\n'
        'from pathlib import Path\n'
        'from typing import Iterator\n'
        '\n'
        'import pypdf\n'
        'import yaml\n'
        '\n'
        'def extract(path: Path) -> Iterator[str]:\n'
        '    return iter([])\n'
    )
    valid, bad = validate_imports(code, "src/chiron/corpus/extractor.py", tmp_path)
    # pypdf is in deps; yaml is not (the package is "pyyaml" but imports as "yaml")
    # so yaml would still be flagged — that's a separate concern about
    # import-name-vs-package-name (not part of #1515).
    assert "pypdf" not in [b.split()[0] for b in bad], (
        f"pypdf should be recognized via PEP 621 deps; got bad={bad!r}"
    )


def test_relative_imports_skipped_single_dot(tmp_path):
    """Closes #1516. `from .chunker import X` must not be flagged."""
    from assemblyzero.workflows.testing.nodes.implementation.import_validator import (
        validate_imports,
    )
    code = (
        '"""Module using relative imports."""\n'
        'from .chunker import chunk_by_section\n'
        '\n'
        'def go():\n'
        '    return chunk_by_section\n'
    )
    valid, bad = validate_imports(code, "src/chiron/corpus/extractor.py", tmp_path)
    assert valid is True, f"relative import should be skipped, got bad={bad!r}"
    assert bad == []


def test_relative_imports_skipped_double_dot(tmp_path):
    """Closes #1516. `from ..foo import Y` must not be flagged."""
    from assemblyzero.workflows.testing.nodes.implementation.import_validator import (
        validate_imports,
    )
    code = (
        '"""Module using double-dot relative imports."""\n'
        'from ..provenance import Citation\n'
        '\n'
        'def go():\n'
        '    return Citation\n'
    )
    valid, bad = validate_imports(code, "src/chiron/corpus/extractor.py", tmp_path)
    assert valid is True, f"double-dot relative should be skipped, got bad={bad!r}"
    assert bad == []


def test_relative_dot_only_skipped(tmp_path):
    """Closes #1516. `from . import bar` must not be flagged."""
    from assemblyzero.workflows.testing.nodes.implementation.import_validator import (
        validate_imports,
    )
    code = "from . import chunker\n\ndef go():\n    return chunker\n"
    valid, bad = validate_imports(code, "src/chiron/corpus/extractor.py", tmp_path)
    assert valid is True, f"dot-only relative should be skipped, got bad={bad!r}"
    assert bad == []


def test_absolute_imports_still_validated(tmp_path):
    """Closes #1516. Regression guard: absolute imports of nonexistent
    modules must still be flagged (the fix only skips relative imports)."""
    from assemblyzero.workflows.testing.nodes.implementation.import_validator import (
        validate_imports,
    )
    code = "from nonexistent.module import X\n\ndef go(): pass\n"
    valid, bad = validate_imports(code, "src/chiron/corpus/extractor.py", tmp_path)
    assert valid is False, "absolute nonexistent import must be flagged"
    assert any("nonexistent" in b for b in bad)


def test_pyyaml_dep_recognizes_yaml_import(tmp_path):
    """Closes #1518. PyYAML installs the `yaml` top-level module; declaring
    pyyaml in deps must register `yaml` so `import yaml` is recognized."""
    from assemblyzero.workflows.testing.nodes.implementation.import_validator import (
        _read_third_party_packages,
    )
    (tmp_path / "pyproject.toml").write_text(
        '[project]\n'
        'name = "chiron"\n'
        'dependencies = ["pyyaml>=6.0"]\n'
    )
    pkgs = _read_third_party_packages(tmp_path)
    assert "yaml" in pkgs, f"Expected yaml import name from pyyaml dep, got {pkgs}"


def test_pillow_dep_recognizes_pil_import(tmp_path):
    """Closes #1518. Pillow → PIL (case-insensitive normalize)."""
    from assemblyzero.workflows.testing.nodes.implementation.import_validator import (
        _read_third_party_packages,
    )
    (tmp_path / "pyproject.toml").write_text(
        '[project]\n'
        'name = "chiron"\n'
        'dependencies = ["Pillow>=10"]\n'
    )
    pkgs = _read_third_party_packages(tmp_path)
    assert "PIL" in pkgs, f"Expected PIL import name from Pillow dep, got {pkgs}"


def test_beautifulsoup4_dep_recognizes_bs4_import(tmp_path):
    """Closes #1518. beautifulsoup4 → bs4."""
    from assemblyzero.workflows.testing.nodes.implementation.import_validator import (
        _read_third_party_packages,
    )
    (tmp_path / "pyproject.toml").write_text(
        '[project]\n'
        'name = "chiron"\n'
        'dependencies = ["beautifulsoup4>=4.12"]\n'
    )
    pkgs = _read_third_party_packages(tmp_path)
    assert "bs4" in pkgs


def test_unmapped_pypi_name_still_normalizes(tmp_path):
    """Closes #1518 regression: package names not in the mapping table
    still go through the normal hyphen→underscore normalize path."""
    from assemblyzero.workflows.testing.nodes.implementation.import_validator import (
        _read_third_party_packages,
    )
    (tmp_path / "pyproject.toml").write_text(
        '[project]\n'
        'name = "chiron"\n'
        'dependencies = ["pytest-cov>=7"]\n'
    )
    pkgs = _read_third_party_packages(tmp_path)
    assert "pytest_cov" in pkgs


def test_chiron_iter10_full_import_validation(tmp_path):
    """Closes #1518. Verbatim iter10 shape: pyproject with pypdf + pyyaml,
    code does `import yaml` — must pass validation, not flag yaml as
    unresolvable."""
    from assemblyzero.workflows.testing.nodes.implementation.import_validator import (
        validate_imports,
    )
    (tmp_path / "pyproject.toml").write_text(
        '[project]\n'
        'name = "chiron"\n'
        'dependencies = [\n'
        '    "pypdf>=5.0.0",\n'
        '    "pyyaml>=6.0",\n'
        ']\n'
    )
    code = (
        '"""CLI entry."""\n'
        'import argparse\n'
        'import logging\n'
        'from pathlib import Path\n'
        '\n'
        'import yaml\n'
        '\n'
        'def main(): pass\n'
    )
    valid, bad = validate_imports(code, "src/chiron/corpus/cli.py", tmp_path)
    assert valid is True, f"Expected valid, got bad={bad!r}"


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
