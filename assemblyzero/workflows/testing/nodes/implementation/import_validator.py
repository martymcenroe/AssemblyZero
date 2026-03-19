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

    Reads [tool.poetry.dependencies] and [tool.poetry.group.*.dependencies]
    to build a set of top-level import names.
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

    # Main dependencies
    poetry = data.get("tool", {}).get("poetry", {})
    for dep_name in poetry.get("dependencies", {}):
        packages.add(_normalize_package_name(dep_name))

    # Group dependencies (dev, test, etc.)
    for group in poetry.get("group", {}).values():
        for dep_name in group.get("dependencies", {}):
            packages.add(_normalize_package_name(dep_name))

    return packages


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


def _resolve_internal_import(module_path: str, repo_root: Path) -> bool:
    """Check if an internal import resolves to a file or package on disk.

    Handles both:
    - `import assemblyzero.utils.foo` -> assemblyzero/utils/foo.py or foo/__init__.py
    - `from assemblyzero.utils import foo` -> same resolution
    """
    parts = module_path.split(".")

    # Try as a module file: assemblyzero/utils/foo.py
    file_path = repo_root / Path(*parts).with_suffix(".py")
    if file_path.exists():
        return True

    # Try as a package: assemblyzero/utils/foo/__init__.py
    package_path = repo_root / Path(*parts) / "__init__.py"
    if package_path.exists():
        return True

    # Try parent module (for `from assemblyzero.utils import foo`):
    # The import might target a name inside a module, not a submodule file.
    # Check if the parent path resolves.
    if len(parts) > 1:
        parent_file = repo_root / Path(*parts[:-1]).with_suffix(".py")
        if parent_file.exists():
            return True
        parent_package = repo_root / Path(*parts[:-1]) / "__init__.py"
        if parent_package.exists():
            return True

    return False
