"""No tracked file spells the operator's Projects root (#3609).

Code derives the root from where it sits (``assemblyzero.core.projects_root``);
anything an agent reads uses relative paths or placeholders. The ways that
root is written form a closed set, so this guard is a fixed-string check, not
a pattern: five spellings, compared case-insensitively.

Python sources are tokenized rather than read as text. A string token is
checked both as written and decoded, so ``"C:\\\\Users\\\\..."`` and
``r"C:\\Users\\..."`` are both caught; a comment token is checked as written,
which the AST alone cannot see. Every other text file is searched as text.
This file is the one exemption: it has to name what it forbids.
"""

from __future__ import annotations

import ast
import io
import subprocess
import tokenize
from pathlib import Path

import pytest

from assemblyzero.core.projects_root import REPO_ROOT

#: The closed set: the operator's Windows user directory as Windows, an
#: escaped Python or JSON string, a forward-slash Windows path, Git Bash and
#: WSL write it.
SPELLINGS = (
    "C:\\Users\\mcwiz",
    "C:\\\\Users\\\\mcwiz",
    "C:/Users/mcwiz",
    "/c/Users/mcwiz",
    "/mnt/c/Users/mcwiz",
)

#: Where the rule applies (#3609 requirement 1).
SCOPES = ("assemblyzero", "tools", "tests", ".claude")

#: Text formats an agent or a tool reads. A closed list of suffixes.
TEXT_SUFFIXES = {
    ".md", ".txt", ".json", ".jsonl", ".template", ".sh", ".bash", ".ps1",
    ".yml", ".yaml", ".toml", ".cfg", ".ini", ".js", ".ts", ".html", ".xml",
}

THIS_FILE = Path(__file__).resolve()


def _hits(text: str) -> list[str]:
    lowered = text.lower()
    return [s for s in SPELLINGS if s.lower() in lowered]


def python_findings(source: str) -> list[tuple[int, str]]:
    """(line, spelling) for every string or comment token that spells the root."""
    found: list[tuple[int, str]] = []
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type == tokenize.COMMENT:
            texts = [tok.string]
        elif tok.type == tokenize.STRING:
            texts = [tok.string]
            try:
                decoded = ast.literal_eval(tok.string)
            except (ValueError, SyntaxError):
                decoded = None  # an f-string part: its written form is checked
            if isinstance(decoded, (str, bytes)):
                texts.append(decoded if isinstance(decoded, str) else decoded.decode("latin-1"))
        elif tok.type in (getattr(tokenize, "FSTRING_MIDDLE", -1),):
            texts = [tok.string]
        else:
            continue
        for text in texts:
            for spelling in _hits(text):
                found.append((tok.start[0], spelling))
    return found


def text_findings(text: str) -> list[tuple[int, str]]:
    return [
        (number, spelling)
        for number, line in enumerate(text.splitlines(), start=1)
        for spelling in _hits(line)
    ]


def _tracked_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "--", *SCOPES],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    ).stdout
    return [REPO_ROOT / line for line in out.splitlines() if line]


def test_no_tracked_file_spells_the_projects_root():
    files = _tracked_files()
    assert files, "git ls-files returned nothing; the guard would pass vacuously"
    offenders: list[str] = []
    for path in files:
        if path.resolve() == THIS_FILE or not path.is_file():
            continue
        if path.suffix == ".py":
            findings = python_findings(path.read_text(encoding="utf-8"))
        elif path.suffix in TEXT_SUFFIXES:
            findings = text_findings(path.read_text(encoding="utf-8"))
        else:
            continue
        rel = path.relative_to(REPO_ROOT).as_posix()
        offenders += [f"{rel}:{line}: {spelling}" for line, spelling in findings]
    assert offenders == [], (
        "the Projects root is spelled; derive it from "
        "assemblyzero.core.projects_root or use a relative path:\n  "
        + "\n  ".join(offenders)
    )


@pytest.mark.parametrize("spelling", SPELLINGS)
def test_python_guard_catches_each_spelling_in_strings_and_comments(spelling):
    as_string = f"ROOT = {spelling!r}\n"
    as_comment = f"x = 1  # see {spelling}\\Projects\n"
    assert python_findings(as_string), as_string
    assert python_findings(as_comment), as_comment


def test_python_guard_catches_the_escaped_form_by_decoding():
    source = 'ROOT = "C:\\\\Users\\\\MCWIZ\\\\Projects"\n'
    assert python_findings(source)


def test_python_guard_ignores_code_that_derives_the_root():
    source = (
        "from assemblyzero.core.projects_root import PROJECTS\n"
        'ROOT = PROJECTS / "boostgauge"  # derived, never spelled\n'
    )
    assert python_findings(source) == []


@pytest.mark.parametrize("spelling", SPELLINGS)
def test_text_guard_catches_each_spelling(spelling):
    # "/mnt/c/..." also contains "/c/...", so a line may report both.
    assert (2, spelling) in text_findings(f"line one\nrun from {spelling}/Projects/AssemblyZero\n")
