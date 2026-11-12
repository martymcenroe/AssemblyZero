"""The per-repository Cerberus secret deploy path is retired (#4728).

Nothing reads `REVIEWER_APP_ID` or `REVIEWER_APP_PRIVATE_KEY` since Auto Review's retirement
(#4724). `tools/fleet_remove_cerberus_secrets.py` takes them out of every repository, so
nothing here may put them back:

- the deploy tool and its tests are removed, the way #4719 removed the Auto Review deploy tool;
- no tool, test or package module imports it;
- `new_repo.py` refuses the `--cerberus-pem` and `--cerberus-pem-gpg` flags that called it,
  and keeps no deploy step;
- no live file sends anyone to it. Historical audit ledgers and reports keep their wording, and
  so do the dated rows of a document's history table.
"""

from __future__ import annotations

import ast
import inspect
import re
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import new_repo

RETIRED = "deploy_cerberus_secrets"
SEARCHED = ("tools", "tests", "assemblyzero", "docs")
HISTORICAL = ("docs/audits/", "docs/reports/")
# A row of a document's history table: its first cell is a date.
HISTORY_ROW = re.compile(r"^\|\s*\d{4}-\d{2}-\d{2}\s*\|")
HERE = Path(__file__).resolve().relative_to(ROOT).as_posix()


def _lines_naming(text: str, suffixes: tuple[str, ...]) -> list[tuple[str, int, str]]:
    """(path, line number, line) for every line of a SEARCHED file with `suffixes` naming `text`.

    `git grep` over the tracked and untracked files, because walking these trees file by
    file takes minutes on a Windows-mounted checkout. Exit 1 means no match; any other
    non-zero exit fails the test.
    """
    run = subprocess.run(
        ["git", "-C", str(ROOT), "grep", "--untracked", "-n", "-F", "-e", text, "--", *SEARCHED],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    assert run.returncode in (0, 1), run.stderr
    hits = []
    for row in run.stdout.splitlines():
        path, number, line = row.split(":", 2)
        if path.endswith(suffixes):
            hits.append((path, int(number), line))
    return hits


def test_t4_the_deploy_tool_and_its_tests_are_gone():
    assert not (TOOLS / f"{RETIRED}.py").exists()
    assert not (ROOT / "tests" / "unit" / f"test_{RETIRED}.py").exists()


def _imported_modules(source: str) -> set[str]:
    tree = ast.parse(source)
    names = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    names |= {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    return names


def test_t4_no_tool_test_or_package_module_imports_it():
    """A file can import the tool only if it names it, so only those files are parsed."""
    naming = sorted({path for path, _, _ in _lines_naming(RETIRED, (".py",))} - {HERE})
    hits = [path for path in naming
            if RETIRED in _imported_modules((ROOT / path).read_text(encoding="utf-8-sig"))]
    assert hits == [], f"these still import the retired deploy tool: {hits}"


def test_the_import_check_sees_both_import_forms():
    assert RETIRED in _imported_modules(f"import {RETIRED}\n")
    assert RETIRED in _imported_modules(f"from {RETIRED} import deploy_to_repo\n")
    assert RETIRED not in _imported_modules(f"x = '{RETIRED}'\n")


@pytest.mark.parametrize("flag", ["--cerberus-pem", "--cerberus-pem-gpg"])
def test_t4_new_repo_refuses_the_pem_flags(flag, tmp_path: Path, capsys):
    argv = ["new_repo.py", "NoPem", flag, str(tmp_path / "key")]
    with patch("new_repo.config"), patch("sys.argv", argv), pytest.raises(SystemExit) as exc:
        new_repo.main()
    assert exc.value.code == 2
    assert f"unrecognized arguments: {flag}" in capsys.readouterr().err


def test_t4_new_repo_keeps_no_cerberus_deploy_step():
    for name in ("_deploy_cerberus", "deploy_to_repo", "verify_secrets", "cerberus_pem_session"):
        assert not hasattr(new_repo, name), name
    assert "cerberus_status" not in inspect.signature(new_repo.failed_steps).parameters


def test_nothing_live_names_the_retired_tool():
    hits = [f"{path}:{n}" for path, n, line in _lines_naming(RETIRED, (".py", ".md"))
            if path != HERE and not path.startswith(HISTORICAL) and not HISTORY_ROW.match(line)]
    assert hits == [], f"live lines still send someone to the retired deploy tool: {hits}"


def test_the_search_finds_what_it_is_looking_for():
    """The two searches above pass on an empty result, so prove they can find a hit."""
    found = _lines_naming("def test_nothing_live_names_the_retired_tool", (".py",))
    assert found and {path for path, _, _ in found} == {HERE}
    assert HISTORY_ROW.match("| 2026-04-22 | v5.1: the old tool |")
    assert not HISTORY_ROW.match("| `tools/x.py` | Stable | the old tool |")
