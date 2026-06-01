"""AST-based import validation for generated code.

Issue #842: Validates that all imports in generated Python code resolve
to real modules — stdlib, installed third-party packages, or internal
project modules that exist on disk. Catches hallucinated imports like
`assemblyzero.core.metrics` before they reach the test phase.
"""

import ast
import sys
from pathlib import Path

# Python stdlib module names (Python 3.10+)
_STDLIB_MODULES: frozenset[str] = frozenset(sys.stdlib_module_names)

# Well-known third-party top-level packages that may not appear in
# pyproject.toml under their import name (e.g., "google-cloud-foo"
# installs as "google").  Keep this small — it's a fallback.
_KNOWN_THIRD_PARTY: frozenset[str] = frozenset({
    "pytest", "pytest_cov", "_pytest",
})


def _read_third_party_packages(repo_root: Path) -> set[str]:
    """Extract third-party package names from pyproject.toml.

    Reads three pyproject layouts:
    - `[tool.poetry.dependencies]` + `[tool.poetry.group.*.dependencies]`
      (Poetry, legacy).
    - `[project] dependencies = [...]` + `[project.optional-dependencies]`
      (PEP 621, canonical).
    - `[dependency-groups]` (PEP 735, used by uv / hatch / modern tooling).

    Closes #1515: previously only the Poetry tables were read, so every
    external repo using PEP 621 lost its declared dependencies and every
    third-party import got misclassified as "unresolvable internal."
    """
    pyproject = repo_root / "pyproject.toml"
    if not pyproject.exists():
        return set()

    try:
        # Use tomllib (Python 3.11+) or tomli
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib  # type: ignore[no-redef]

        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except Exception:
        return set()

    packages: set[str] = set()

    # Poetry: [tool.poetry.dependencies] and [tool.poetry.group.*.dependencies]
    poetry = data.get("tool", {}).get("poetry", {})
    for dep_name in poetry.get("dependencies", {}):
        packages.add(_normalize_package_name(dep_name))
    for group in poetry.get("group", {}).values():
        for dep_name in group.get("dependencies", {}):
            packages.add(_normalize_package_name(dep_name))

    # PEP 621: [project] dependencies = ["pypdf>=5.0.0", ...]
    project = data.get("project", {})
    for spec in project.get("dependencies", []):
        name = _extract_package_name_from_pep508(spec)
        if name:
            packages.add(_normalize_package_name(name))
    # PEP 621: [project.optional-dependencies]
    for group_specs in project.get("optional-dependencies", {}).values():
        for spec in group_specs:
            name = _extract_package_name_from_pep508(spec)
            if name:
                packages.add(_normalize_package_name(name))

    # PEP 735: [dependency-groups] dev = ["pytest>=9.0.3", ...]
    for group_specs in data.get("dependency-groups", {}).values():
        if not isinstance(group_specs, list):
            continue
        for spec in group_specs:
            if not isinstance(spec, str):
                continue
            name = _extract_package_name_from_pep508(spec)
            if name:
                packages.add(_normalize_package_name(name))

    return packages


def _extract_package_name_from_pep508(spec: str) -> str:
    """Extract the package name from a PEP 508 dependency spec.

    Handles common forms:
    - `"pypdf"` -> `"pypdf"`
    - `"pypdf>=5.0.0"` -> `"pypdf"`
    - `"pytest (>=9.0.3,<10.0.0)"` -> `"pytest"`  (Poetry whitespace form)
    - `"pytest-cov[extra]>=7"` -> `"pytest-cov"`

    Returns empty string on malformed input rather than raising.
    """
    if not spec or not isinstance(spec, str):
        return ""
    # Strip whitespace, then take the part before any version/extras marker.
    s = spec.strip()
    # Cut on the first occurrence of any spec-terminator char.
    for ch in (" ", "[", "(", ">", "<", "=", "!", "~", ";"):
        idx = s.find(ch)
        if idx > 0:
            s = s[:idx]
    return s.strip()


def _normalize_package_name(name: str) -> str:
    """Convert a PyPI package name to its likely top-level import name.

    e.g., "google-cloud-storage" -> "google", "pytest-cov" -> "pytest_cov"
    """
    # Replace hyphens with underscores (PEP 503 normalization)
    return name.lower().replace("-", "_").split(".")[0]


def _is_stdlib_module(module_top: str) -> bool:
    """Check if a top-level module name is part of the Python stdlib."""
    return module_top in _STDLIB_MODULES or module_top.startswith("_")


def validate_imports(
    code: str,
    filepath: str,
    repo_root: Path,
) -> tuple[bool, list[str]]:
    """Validate that all imports in generated code resolve to real modules.

    Args:
        code: Python source code to validate.
        filepath: Relative path of the file being generated (for context).
        repo_root: Repository root for resolving internal imports.

    Returns:
        Tuple of (valid, list_of_unresolvable_imports).
        valid is True when there are no unresolvable imports.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        # Syntax errors are caught by the earlier ast.parse() check
        return True, []

    # Collect all imported module top-level names
    imports: list[tuple[str, int]] = []  # (full_module_path, line_number)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((alias.name, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            # Closes #1516: relative imports (level > 0, e.g. `from .chunker
            # import X`) are intra-package by definition. Without knowing
            # the importing file's package the validator can't resolve them
            # against repo_root paths; Python's import machinery will catch
            # genuine misses at test/runtime, so skip rather than flag.
            if node.level and node.level > 0:
                continue
            if node.module:
                imports.append((node.module, node.lineno))

    if not imports:
        return True, []

    # Load third-party package names
    third_party = _read_third_party_packages(repo_root) | _KNOWN_THIRD_PARTY

    bad_imports: list[str] = []
    checked: set[str] = set()

    for module_path, lineno in imports:
        top_level = module_path.split(".")[0]

        # Skip duplicates
        if module_path in checked:
            continue
        checked.add(module_path)

        # 1. Stdlib
        if _is_stdlib_module(top_level):
            continue

        # 2. Third-party (from pyproject.toml or known list)
        if top_level in third_party:
            continue

        # 3. Relative imports within the same package are fine
        # (ast.ImportFrom with level > 0 has module=None or partial)
        # We already skip those since node.module would be partial

        # 4. Internal imports — verify the target exists on disk
        if not _resolve_internal_import(module_path, repo_root):
            bad_imports.append(f"{module_path} (line {lineno})")

    return len(bad_imports) == 0, bad_imports


# Closes #1500: src-layout repos place importable modules under a
# source-root prefix (src/ is canonical; lib/, source/, python/, apps/ are
# common alternatives — same list as the spec-stage validator extended in
# #1477). The earlier resolver only checked repo_root/Path(*parts), which
# missed every external target that uses src-layout.
_SOURCE_ROOT_PREFIXES: tuple[str, ...] = (
    "", "src", "lib", "source", "python", "apps",
)


def _resolve_internal_import(module_path: str, repo_root: Path) -> bool:
    """Check if an internal import resolves to a file or package on disk.

    Handles both flat-layout and src-layout (and lib/source/python/apps
    variants). Mirrors the spec-stage validator at
    assemblyzero/workflows/implementation_spec/nodes/validate_completeness.py
    (PR #1462 + #1477). Closes #1500.
    """
    parts = module_path.split(".")
    candidates: list[Path] = [
        Path(*parts).with_suffix(".py"),
        Path(*parts) / "__init__.py",
    ]
    if len(parts) > 1:
        candidates.extend([
            Path(*parts[:-1]).with_suffix(".py"),
            Path(*parts[:-1]) / "__init__.py",
        ])

    for candidate in candidates:
        for prefix in _SOURCE_ROOT_PREFIXES:
            probe = (
                repo_root / prefix / candidate if prefix
                else repo_root / candidate
            )
            if probe.exists():
                return True

    return False
