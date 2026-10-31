"""No paid API-key path exists: not Gemini's (ADR 0237, #3583), not Anthropic's (#2864).

AssemblyZero reaches Gemini only through agy and Claude only through the
subscription CLI. This guard fails, from the AST and never a pattern, when any
module under ``assemblyzero/`` or ``tools/``:

* imports ``google.genai``, ``google.generativeai``, ``google.api_core``,
  ``langchain_google_genai``, ``anthropic`` or ``langchain_anthropic`` (or
  anything beneath them);
* reads ``GEMINI_API_KEY``, ``GOOGLE_API_KEY`` or ``ANTHROPIC_API_KEY`` from
  the environment, through ``os.environ[...]``, ``os.environ.get``,
  ``os.getenv`` or ``environ.get``;
* reads ``ANTHROPIC_API_KEY`` out of a ``.env`` file, which no environment call
  shows: a loader compares each line's key against the name, so any code string
  that is the name, or starts with it as a ``NAME=`` line would, is a finding.
  Docstrings and bare strings are not code strings.

and when ``pyproject.toml`` or ``poetry.lock`` names a key-SDK package. The
property protected is the absence of a spend path: a quota that runs out is
waited out, never paid around.
"""

from __future__ import annotations

import ast
import subprocess
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

FORBIDDEN_MODULES = (
    "google.genai",
    "google.generativeai",
    "google.api_core",
    "langchain_google_genai",
    "anthropic",
    "langchain_anthropic",
)
FORBIDDEN_KEYS = ("GEMINI_API_KEY", "GOOGLE_API_KEY", "ANTHROPIC_API_KEY")
#: The key a ``.env`` loader would hunt for by comparing line keys (#2864).
LOADER_KEYS = ("ANTHROPIC_API_KEY",)
FORBIDDEN_PACKAGES = (
    "anthropic",
    "langchain-anthropic",
    "google-genai",
    "google-generativeai",
    "langchain-google-genai",
    "google-auth",
    "google-api-core",
)


def _forbidden_module(name: str) -> bool:
    return any(name == m or name.startswith(m + ".") for m in FORBIDDEN_MODULES)


def _is_environ(node: ast.AST) -> bool:
    """``os.environ`` or a bare ``environ``."""
    if isinstance(node, ast.Attribute):
        return node.attr == "environ"
    return isinstance(node, ast.Name) and node.id == "environ"


def _first_arg_is_key(call: ast.Call) -> bool:
    return bool(call.args) and isinstance(call.args[0], ast.Constant) and call.args[0].value in FORBIDDEN_KEYS


def violations(source: str) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    tree = ast.parse(source)
    # A string that stands alone as a statement is a docstring or a note, never
    # a value the program compares against.
    prose = {id(n.value) for n in ast.walk(tree) if isinstance(n, ast.Expr)}
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in prose
            and node.value.startswith(LOADER_KEYS)
        ):
            found.append((node.lineno, f"string {node.value!r} (a .env loader's key)"))
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _forbidden_module(alias.name):
                    found.append((node.lineno, f"import {alias.name}"))
        elif isinstance(node, ast.ImportFrom) and node.module:
            full = [node.module] + [f"{node.module}.{a.name}" for a in node.names]
            if node.module == "google":
                full += [f"google.{a.name}" for a in node.names]
            if any(_forbidden_module(name) for name in full):
                found.append((node.lineno, f"from {node.module} import ..."))
        elif isinstance(node, ast.Subscript) and _is_environ(node.value):
            key = node.slice
            if isinstance(key, ast.Constant) and key.value in FORBIDDEN_KEYS:
                found.append((node.lineno, f"environ[{key.value!r}]"))
        elif isinstance(node, ast.Call) and _first_arg_is_key(node):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr in ("get", "pop", "setdefault") and _is_environ(func.value):
                found.append((node.lineno, f"environ.{func.attr}({node.args[0].value!r})"))
            elif isinstance(func, ast.Attribute) and func.attr == "getenv":
                found.append((node.lineno, f"getenv({node.args[0].value!r})"))
            elif isinstance(func, ast.Name) and func.id == "getenv":
                found.append((node.lineno, f"getenv({node.args[0].value!r})"))
    return found


def _tracked_python() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "--", "assemblyzero/*.py", "tools/*.py"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    ).stdout
    return [REPO_ROOT / line for line in out.splitlines() if line]


def test_no_module_imports_a_key_sdk_or_reads_a_key():
    files = _tracked_python()
    assert len(files) > 100, "git ls-files found too few modules; the guard would pass vacuously"
    offenders = [
        f"{path.relative_to(REPO_ROOT).as_posix()}:{line}: {what}"
        for path in files
        for line, what in violations(path.read_text(encoding="utf-8-sig"))
    ]
    assert offenders == [], (
        "ADR 0237 and #2864: agy is the only Gemini transport and the "
        "subscription CLI the only Claude transport.\n  " + "\n  ".join(offenders)
    )


def test_no_key_sdk_is_a_dependency():
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    declared: list[str] = list(project.get("project", {}).get("dependencies", []))
    for group in project.get("tool", {}).get("poetry", {}).get("group", {}).values():
        declared += list(group.get("dependencies", {}))
    names = {d.split()[0].split("(")[0].split(">")[0].split("=")[0].split(";")[0].strip().lower() for d in declared}
    assert sorted(names & set(FORBIDDEN_PACKAGES)) == []


def test_no_key_sdk_is_locked():
    """The lock file resolves every package that is installed, so a key SDK
    pulled in by some other dependency still shows here (#2864)."""
    lock = tomllib.loads((REPO_ROOT / "poetry.lock").read_text(encoding="utf-8"))
    locked = {pkg["name"].lower() for pkg in lock["package"]}
    assert len(locked) > 50, "poetry.lock parsed to too few packages; the guard would pass vacuously"
    assert sorted(locked & set(FORBIDDEN_PACKAGES)) == []


@pytest.mark.parametrize(
    "source",
    [
        "import google.genai\n",
        "import google.generativeai as genai\n",
        "from google import genai\n",
        "from google.api_core import exceptions\n",
        "from langchain_google_genai import ChatGoogleGenerativeAI\n",
        "import os\nk = os.environ['GEMINI_API_KEY']\n",
        "import os\nk = os.environ.get('GOOGLE_API_KEY')\n",
        "import os\nk = os.getenv('GEMINI_API_KEY')\n",
        "from os import environ\nk = environ.get('GOOGLE_API_KEY', '')\n",
        "import anthropic\n",
        "import anthropic.types\n",
        "from anthropic import Anthropic\n",
        "from langchain_anthropic import ChatAnthropic\n",
        "import os\nk = os.environ['ANTHROPIC_API_KEY']\n",
        "import os\nk = os.environ.get('ANTHROPIC_API_KEY')\n",
        "import os\nk = os.getenv('ANTHROPIC_API_KEY')\n",
        "def load(line):\n    key, _, value = line.partition('=')\n    if key == 'ANTHROPIC_API_KEY':\n        return value\n",
        "def load(line):\n    return line.startswith('ANTHROPIC_API_KEY=')\n",
    ],
)
def test_the_guard_catches_each_shape(source):
    assert violations(source), source


def test_the_guard_passes_clean_code():
    source = (
        "import os\n"
        "from google.protobuf import message\n"
        "x = os.environ.get('AZ_OPERATOR_EMAIL_FROM')\n"
        "# GEMINI_API_KEY is named in a comment only\n"
        "# so is ANTHROPIC_API_KEY\n"
        "def f():\n"
        "    \"\"\"ANTHROPIC_API_KEY is named in a docstring only.\"\"\"\n"
        "    return 'the anthropic package is gone'\n"
        "import anthropic_unrelated_but_not_the_sdk_prefix\n"
    )
    assert violations(source) == []
