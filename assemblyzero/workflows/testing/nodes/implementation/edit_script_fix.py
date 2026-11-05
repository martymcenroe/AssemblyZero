"""A fix asks for edits, not a rebirth (#2407).

The spec stage learned this class in #1528: a "revision" that regenerates the
whole document drifts, because the model does not copy unflagged content
byte-identically however firmly it is asked to. The implementation stage never
inherited it. Its fix loop sends the whole current file, the test failures and
the spec, and asks for a complete regeneration.

## The measurement, from run-issue1-090001

Every per-file call in the run, paired with what it cost:

    src/boostgauge/skins/stingray.py   Add              sonnet    15.9s
    src/boostgauge/gauge.py            Add              sonnet     9.8s
    tests/conftest.py                  Modify(extend)   haiku      6.3s
    tests/unit/test_gauge.py           Add              sonnet    31.6s
    tests/visual/test_gauge.py         Add              sonnet     9.1s
    src/boostgauge/skins/stingray.py   Modify(extend)   sonnet   602.2s  TIMEOUT
    src/boostgauge/skins/stingray.py   Modify(extend)   sonnet   600.2s  TIMEOUT
    src/boostgauge/gauge.py            Modify(extend)   sonnet     8.5s
    tests/conftest.py                  Modify(extend)   haiku      7.8s
    tests/unit/test_gauge.py           Modify(extend)   sonnet    22.7s
    tests/visual/test_gauge.py         Modify(extend)   sonnet     9.6s
    src/boostgauge/skins/stingray.py   Modify(extend)   sonnet   602.2s  TIMEOUT
    src/boostgauge/skins/stingray.py   Modify(extend)   sonnet   480.9s
    ...

Two things in that table correct the issue that filed this.

**The draft was 15.9 seconds, not ~580.** The issue attributes ~580s to the
draft call; measured, every call in that class is a FIX call. So the asymmetry
is not 580 -> 602, it is **15.9 -> 602, a factor of thirty-eight** for the same
file. The case for edit scripts is stronger than it was written.

**Regeneration is not uniformly slow.** Four of five files regenerate in under
32 seconds on the same path in the same run. Only the file the failing tests
implicate blows up -- which is exactly the mechanism this module addresses:
that file gets the failure corpus appended AND is the one being reasoned about
hardest, so it re-derives the whole file while concentrating on one defect.
The fix is therefore scoped to where the pathology is, not applied as a blanket
change to every write.

The 480.9s call that COMPLETED matters too: the work fits under the wall when
the model gets there. A smaller ask is cheaper insurance than any ceiling.

## Same format, one parser

`parse_edit_blocks`, `apply_edit_blocks` and `unchanged_ratio` are imported
from the spec stage rather than reimplemented. The issue asks for "the same
script format the spec stage validates and applies", and a second copy of a
parser is a guarantee of drift rather than of sameness. Only the PROMPT differs
here, because the subject is code and failing tests rather than a document and
reviewer feedback.

## Never worse than regeneration

Every failure at every step -- no blocks, a SEARCH that does not match, a
SEARCH that matches twice, an empty result -- returns None, and the caller
falls back to the existing full-file path. That is the same contract #1528
wrote for the spec stage, and it is what makes this safe to switch on. The
caller, `orchestrator.try_edit_script_fix`, alerts the operator on every
fallback (#3585).
"""

from __future__ import annotations

import ast
import os
import re
import sys
from pathlib import Path

# One format, one parser (see the module docstring). These are pure text
# functions with their own unit tests; importing them is what makes "the same
# script format" true rather than merely claimed.
from assemblyzero.workflows.implementation_spec.nodes.edit_script import (
    apply_edit_blocks,
    parse_edit_blocks,
    unchanged_ratio,
)

__all__ = [
    "EDIT_SCRIPT_CODE_SYSTEM_PROMPT",
    "LARGE_FILE_CHARS",
    "EditScriptOutcome",
    "apply_edit_blocks",
    "build_code_edit_script_draft_prompt",
    "build_code_edit_script_prompt",
    "failures_for_file",
    "is_large_file",
    "parse_edit_blocks",
    "previous_attempt_section",
    "should_use_edit_script",
    "unchanged_ratio",
]

EDIT_SCRIPT_CODE_SYSTEM_PROMPT = (
    "You are a precision patch engine for source code. You NEVER rewrite "
    "files -- you emit minimal, exact edit blocks that a machine applies. "
    "Your entire response is edit blocks in the specified format; any prose "
    "outside edit blocks is discarded."
)

#: A file this small is cheaper to regenerate than to patch, and a SEARCH
#: anchor in it is more likely to be ambiguous. Measured against the run above:
#: every file that regenerated in under 32s is in this class or near it.
MIN_BYTES_FOR_EDIT_SCRIPT = 400

#: A Modify file at least this large is changed by edit script on every
#: iteration, its first draft included, and is never asked for whole (#4683).
#: Half of N4's prompt cap (#644, `orchestrator.CODE_GEN_PROMPT_CAP`): a
#: whole-file draft carries the file in and back out again, so a file over
#: half the cap cannot make the round trip inside it. Measured: a 3,666-line,
#: 171,540-byte module came back twice as its one new function, the size gate
#: refused both, and the run halted; a 30,172-byte module was next in line.
LARGE_FILE_CHARS = 30_000


def is_large_file(change_type: str, existing_content: str) -> bool:
    """Is this an existing file too large to ask for whole (#4683)?"""
    return (
        change_type.lower() == "modify"
        and len(existing_content) >= LARGE_FILE_CHARS
    )


class EditScriptOutcome:
    """What an edit-script fix attempt produced, and how well it held.

    `code` is None whenever the caller must fall back -- there is no partial
    success, for the same reason `apply_edit_blocks` returns failures rather
    than a half-patched document.
    """

    def __init__(
        self,
        code: str | None,
        blocks: int = 0,
        preserved: float = 0.0,
        failures: list[str] | None = None,
        no_edit: str | None = None,
    ) -> None:
        self.code = code
        self.blocks = blocks
        self.preserved = preserved
        self.failures = failures or []
        #: #2915: the model's stated reason that this file needs no change.
        self.no_edit = no_edit

    @property
    def ok(self) -> bool:
        return self.code is not None

    def describe(self) -> str:
        if self.no_edit is not None:
            return f"[EDIT-SCRIPT] no edits; the model says: {self.no_edit} (#2915)"
        if self.ok:
            return (
                f"[EDIT-SCRIPT] Applied {self.blocks} edit(s); "
                f"{self.preserved:.0%} of the prior file preserved "
                f"byte-identical (#2407)"
            )
        reason = self.failures[0] if self.failures else "no edit blocks in response"
        return f"[EDIT-SCRIPT] fell back to full regeneration: {reason}"


def should_use_edit_script(
    change_type: str, existing_content: str, failure_context: str
) -> bool:
    """Is this the fix-an-existing-file case the edit script is for?

    Three conditions, all measured rather than assumed:

    - there IS a prior failure to fix (an initial draft has nothing to patch);
    - the file already exists with content (you cannot SEARCH an empty file --
      this is the "file does not yet exist" fallback the issue names);
    - the file is big enough that patching beats regenerating.
    """
    if not failure_context.strip():
        return False
    if change_type.lower() not in ("modify", "add"):
        return False
    if len(existing_content) < MIN_BYTES_FOR_EDIT_SCRIPT:
        return False
    return True


def _file_tokens(filepath: str) -> set[str]:
    """The names a failure line would carry if this file were implicated.

    `src/boostgauge/skins/stingray.py` -> boostgauge.skins.stingray, the bare
    stem, the path itself, and `test_stingray` -- the runner names the test,
    and the fix lands in the module under it.
    """
    path = Path(filepath)
    stem = path.stem
    if not stem:
        return set()
    parts = [p for p in path.with_suffix("").parts if p not in ("src", "lib")]
    return {
        stem.lower(),
        ".".join(parts).lower(),
        str(path).replace("\\", "/").lower(),
        f"test_{stem}".lower(),
    }


def _attributed_blocks(
    failure_summary: str, filepath: str, repo_root: Path | None = None,
) -> list[str]:
    """The blocks of the corpus that name this file.

    #2851: attribution is per BLOCK, not per line. A traceback block is a test
    name, a frame, a source line and its `E` lines; the frame is the line that
    names the owning file (`src/boostgauge/collector.py:116: in
    _is_unleashed_session`), and keeping only that line would hand the model a
    filename with no error under it. Lines are slash-normalised before the
    match because pytest prints Windows frames with backslashes and the tokens
    are built with forward slashes.

    #2861: a block the frame rule leaves unattributed, whose innermost frame
    is a TEST function, is attributed by what that test's body names. An
    assertion that raises in the test itself (`assert len(calls) == 1`) has
    no frame under src/, but the test constructed `WindowsCollector({})` and
    called `.collect()`, and the planned file that defines those names is the
    file the failure is about. Needs `repo_root` to read the test; without it
    the frame rule stands alone, as before.
    """
    tokens = _file_tokens(filepath)
    if not tokens:
        return []
    defined: tuple[set[str], dict[str, set[str]]] | None = None  # parsed once per file
    kept: list[str] = []
    for block in _blocks(failure_summary):
        haystack = block.replace("\\", "/").lower()
        if any(token in haystack for token in tokens):
            kept.append(block)
            continue
        if repo_root is None:
            continue
        test_ref = _test_frame_of(block)
        if test_ref is None:
            continue
        if defined is None:
            defined = _names_defined_in(repo_root / filepath)
        top, methods = defined
        if not top and not methods:
            continue
        used = _names_used_by_test(repo_root / test_ref[0], test_ref[1])
        # #2865: a top-level name the test uses is enough. A method name
        # counts only when the test also uses a class that defines it -- so
        # `collect` attributes the file whose WindowsCollector defines it,
        # and not a file whose `collect` hangs off a DummyCollector double.
        if used & top or any(
            methods[m] & used for m in used if m in methods
        ):
            kept.append(block)
    return kept


def _test_frame_of(block: str) -> tuple[str, str] | None:
    """(test file path, test function name) from a block's innermost frame,
    or None when the innermost frame is not a test function."""
    frame = None
    for line in block.splitlines():
        match = _FRAME.match(line.strip().replace("\\", "/"))
        if match:
            frame = match
    if frame is None:
        return None
    path, func = frame.group(1), frame.group(2)
    if not (Path(path).name.startswith("test_") or func.startswith("test_")):
        return None
    return path, func


#: `path/to/file.py:116: in some_function`, forward slashes, stripped.
_FRAME = re.compile(r"^(\S+?\.py):\d+: in (\S+)")

#: Names too generic to attribute on: a test that calls `run()` or reads
#: `.name` says nothing about which planned file it exercises.
_MIN_NAME_LEN = 4


def _python_tree(path: Path, what: str) -> ast.Module | None:
    """The parsed file the #2861 rule reads, or None when it has nothing to read.

    None is an answer: a file that is not on disk, or not Python, defines and
    uses no names this rule can see, and the frame rule and the whole-corpus
    fallback decide. A Python file that cannot be read or does not parse is
    a failure (standard 0034): attributing around it would be a guess, so an
    ERROR line names the file and the exception propagates (#3585).
    """
    if path.suffix != ".py" or not path.is_file():
        return None
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(
            f"ERROR [N4] could not read {path} ({what}) to attribute failures "
            f"(#2861): {type(exc).__name__}: {exc}",
            file=sys.stderr, flush=True,
        )
        raise
    try:
        return ast.parse(source)
    except (SyntaxError, ValueError) as exc:
        print(
            f"ERROR [N4] {path} ({what}) does not parse, so failures cannot be "
            f"attributed by its names (#2861): {type(exc).__name__}: {exc}",
            file=sys.stderr, flush=True,
        )
        raise


def _names_defined_in(path: Path) -> tuple[set[str], dict[str, set[str]]]:
    """(top-level classes and functions, {method name: classes defining it}).

    #2865: the two are kept apart because they are different strengths of
    evidence. A top-level name the test uses says which file it exercises.
    A method name says so only together with its class: on run-issue4-151141
    the failing tests' `collector.collect()` matched the `collect` method of a
    `DummyCollector` test double in two planned test files, and both were
    sent for a fix that was not theirs.

    A planned file not on disk, or not Python, defines nothing; one that
    cannot be read or parsed raises (see `_python_tree`).
    """
    tree = _python_tree(path, "a planned file")
    if tree is None:
        return set(), {}

    def _ok(name: str) -> bool:
        return len(name) >= _MIN_NAME_LEN and not (
            name.startswith("__") and name.endswith("__")
        )

    top: set[str] = set()
    methods: dict[str, set[str]] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if _ok(node.name):
                top.add(node.name)
        elif isinstance(node, ast.ClassDef):
            if _ok(node.name):
                top.add(node.name)
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and _ok(item.name):
                    methods.setdefault(item.name, set()).add(node.name)
    return top, methods


def _names_used_by_test(path: Path, func: str) -> set[str]:
    """Every Name and Attribute the named test function's body refers to.

    A test file not on disk (a frame path that is not under the repository
    root) uses nothing; one that cannot be read or parsed raises (see
    `_python_tree`).
    """
    tree = _python_tree(path, "the failing test's file")
    if tree is None:
        return set()
    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == func
        ):
            # Names the test BINDS itself -- locals, its own helpers, its
            # parameters -- are not references to anything a planned file
            # defines. `start = time.process_time()` in test_req_8 must not
            # attribute a planned file that happens to define `start()`.
            bound: set[str] = {a.arg for a in ast.walk(node.args) if isinstance(a, ast.arg)}
            used: set[str] = set()
            for sub in ast.walk(node):
                if isinstance(sub, ast.Name):
                    if isinstance(sub.ctx, ast.Load):
                        used.add(sub.id)
                    else:
                        bound.add(sub.id)
                elif isinstance(sub, ast.Attribute):
                    used.add(sub.attr)
                elif isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    if sub is not node:
                        bound.add(sub.name)
            return {n for n in used - bound if len(n) >= _MIN_NAME_LEN}
    return set()


def _blocks(failure_summary: str) -> list[str]:
    """Split the summary into its units, by the one rule all three shapes obey.

    A line at column 0 opens a unit; indented lines continue it; a blank line
    ends it. That reads a bare `FAILED path::test - reason` line as a unit of
    its own, a grouped entry (`N test(s): reason` over an indented `e.g.`) as
    one unit, and a traceback block (test name over an indented frame, source
    line and `E` lines) as one unit -- so the frame that names the file and
    the error it explains are never separated.
    """
    blocks: list[str] = []
    current: list[str] = []
    for line in failure_summary.splitlines():
        if not line.strip():
            if current:
                blocks.append("\n".join(current))
                current = []
            continue
        if not line[0].isspace() and current:
            blocks.append("\n".join(current))
            current = []
        current.append(line.rstrip())
    if current:
        blocks.append("\n".join(current))
    return blocks


def is_attributed(
    failure_summary: str, filepath: str, repo_root: Path | None = None,
) -> bool:
    """Does at least one failure in the corpus name this file?

    The caller's decision (#2851): when the corpus attributes to SOME file,
    a file it does not attribute to has nothing to fix this iteration and is
    left alone -- not sent the whole corpus with an order to fix all of it.
    With `repo_root`, a failure raised inside a test body is attributed by
    the names that test uses (#2861).
    """
    return bool(_attributed_blocks(failure_summary, filepath, repo_root))


def failures_for_file(
    failure_summary: str, filepath: str, repo_root: Path | None = None,
) -> str:
    """The failures this file is implicated in, or everything if unattributable.

    The issue asks to "scope the prompt to the failing tests rather than the
    full failure corpus WHERE THE RUNNER CAN ATTRIBUTE failures to files". The
    conditional is load-bearing and is honoured literally: when nothing
    matches the caller gets the whole corpus back. Silently narrowing to
    nothing would starve the fix of the information it needs, which is a worse
    failure than a prompt that is larger than necessary.

    #2851: what "matches" means changed. It used to be a line-by-line filter
    over a summary whose traceback section had no frame lines and whose
    "source line" was a caret underline, so on run-issue4-120049 nothing ever
    matched and all six files were told to fix all four failures. Blocks are
    kept whole now, and the frame `_extract_traceback_blocks` emits is what
    they match on.
    """
    if not failure_summary.strip():
        return failure_summary
    kept = _attributed_blocks(failure_summary, filepath, repo_root)
    if not kept:
        return failure_summary
    return "\n\n".join(kept)


#: TypeScript's own names, which no file declares (#4512).
_TS_BUILTIN_TYPES = frozenset({
    "any", "bigint", "boolean", "never", "null", "number", "object", "string",
    "symbol", "undefined", "unknown", "void",
})
_TS_ERROR_LINE_RE = re.compile(r"error TS\d+:.*$", re.MULTILINE)
_TS_NAMED_TYPE_RE = re.compile(r"\b[Tt]ype '([A-Za-z_$][\w$]*)")
_TS_RELATIVE_IMPORT_RE = re.compile(r"""\bfrom\s+["'](\.{1,2}/[^"']+)["']""")
#: How far the search walks, and how much of a declaration a prompt carries.
_TS_IMPORT_DEPTH = 2
_TS_DECLARATION_CAP = 3000


def type_names_in_failure(failure_context: str) -> list[str]:
    """The types a TypeScript compiler error names, first seen first (#4512)."""
    names: list[str] = []
    for line in _TS_ERROR_LINE_RE.findall(failure_context):
        for name in _TS_NAMED_TYPE_RE.findall(line):
            if name not in _TS_BUILTIN_TYPES and name not in names:
                names.append(name)
    return names


def _imported_ts_files(path: Path, source: str) -> list[Path]:
    """The files `source` imports by relative path that exist on disk."""
    found: list[Path] = []
    for target in _TS_RELATIVE_IMPORT_RE.findall(source):
        stem = (path.parent / target).resolve()
        for candidate in (
            stem, stem.with_suffix(".ts"), Path(f"{stem}.ts"), Path(f"{stem}.tsx"),
            Path(f"{stem}.d.ts"), stem / "index.ts",
        ):
            if candidate.is_file():
                found.append(candidate)
                break
    return found


def _ts_declaration(name: str, source: str) -> str | None:
    """The text of `name`'s interface, type, class or enum in `source`, or None."""
    opening = re.search(
        r"^[ \t]*(?:export\s+)?(?:declare\s+)?(?:abstract\s+)?"
        rf"(interface|type|class|enum)\s+{re.escape(name)}\b",
        source, re.MULTILINE,
    )
    if opening is None:
        return None
    depth = 0
    opened = False
    for index in range(opening.start(), len(source)):
        char = source[index]
        if char == "{":
            depth, opened = depth + 1, True
        elif char == "}":
            depth -= 1
            if opened and depth == 0:
                return source[opening.start():index + 1].strip()
        elif char == ";" and depth == 0 and opening.group(1) == "type":
            return source[opening.start():index + 1].strip()
    return source[opening.start():].strip()


def type_declarations_for(
    filepath: str, failure_context: str, repo_root: Path | None,
) -> str:
    """The prompt section showing the types a compiler error names (#4512).

    A real run answered `NO-EDIT` until its budget was gone because the error
    named a type declared in a file the prompt never showed, and the fix was
    one line in the file it did show. Only the failing file's first-party
    imports are searched, so a name is never matched against an unrelated
    file. A type declared in the file itself is in the prompt already, and a
    type nothing here declares is said to be missing rather than left out.
    """
    names = type_names_in_failure(failure_context)
    if not names or repo_root is None:
        return ""
    path = repo_root / filepath
    if not path.is_file():
        return ""
    own_source = path.read_text(encoding="utf-8")
    sources: dict[Path, str] = {}
    frontier = [(path, own_source)]
    for _depth in range(_TS_IMPORT_DEPTH):
        reached: list[tuple[Path, str]] = []
        for parent, source in frontier:
            for imported in _imported_ts_files(parent, source):
                if imported not in sources and imported != path.resolve():
                    sources[imported] = imported.read_text(encoding="utf-8")
                    reached.append((imported, sources[imported]))
        frontier = reached

    shown: list[str] = []
    for name in names:
        if _ts_declaration(name, own_source) is not None:
            continue
        for source_path, source in sources.items():
            declaration = _ts_declaration(name, source)
            if declaration is not None:
                where = Path(os.path.relpath(source_path, repo_root)).as_posix()
                shown.append(
                    f"`{name}`, declared in {where}:\n\n"
                    f"```\n{declaration[:_TS_DECLARATION_CAP]}\n```"
                )
                break
        else:
            shown.append(
                f"`{name}`: no declaration was found in this file or in the "
                f"first-party files it imports."
            )
    if not shown:
        return ""
    return "## TYPES THE COMPILER ERROR NAMES (reference, read-only)\n\n" + "\n\n".join(shown)


def build_code_edit_script_prompt(
    filepath: str,
    existing_content: str,
    failure_context: str,
    spec_excerpt: str = "",
    run_files: list[str] | None = None,
    type_declarations: str = "",
) -> str:
    """Ask for edits against the current file, not a regeneration of it.

    #4512: `run_files` are the files this run may change. Without them a model
    can name any file as the one at fault, and a file outside the run cannot
    change, so its `NO-EDIT` leaves the failure standing for good.
    """
    sections: list[str] = [
        f"# Fix Request: {filepath}\n\n"
        "The file below already exists and MOSTLY WORKS. Some tests fail. "
        "Change only what is needed to make them pass.\n\n"
        "Do NOT rewrite the file. Output ONLY edit blocks in EXACTLY this "
        "format:\n\n"
        "<<<<<<< SEARCH\n"
        "(exact lines copied verbatim from the CURRENT FILE below)\n"
        "=======\n"
        "(replacement lines)\n"
        ">>>>>>> REPLACE\n\n"
        "Rules:\n"
        "1. Each SEARCH text must be copied EXACTLY from the current file "
        "(character-for-character, including indentation) and must occur "
        "exactly ONCE in it. Keep SEARCH as small as practical (typically "
        "1-15 lines).\n"
        "2. To INSERT new code, SEARCH for the nearest existing anchor "
        "line(s) and REPLACE with those same anchor lines plus the new code.\n"
        "3. Emit one edit block per fix. Fix the failures listed below that "
        "this file is responsible for. Touch NOTHING else -- code you do not "
        "name in a SEARCH block cannot and must not change, and the passing "
        "tests depend on that.\n"
        "4. No preamble, no explanation, no markdown fences around the "
        "blocks -- edit blocks only.\n"
        "5. If nothing in THIS file needs to change for the failures listed "
        "-- the fix belongs in another file -- output exactly one line and "
        "nothing else: NO-EDIT: <why>. Never rewrite a file to have "
        "something to say."
    ]

    if run_files:
        listed = "\n".join(f"- {path}" for path in run_files)
        sections.append(
            "## FILES THIS RUN MAY CHANGE\n\n"
            f"{listed}\n\n"
            "A file not on this list cannot change in this run. If the failure "
            "can be repaired in the current file, repair it there, even when "
            "code in a file not listed looks like a natural place for the "
            "change. NO-EDIT is only for a fix that belongs in another file "
            "on this list."
        )

    if failure_context:
        sections.append(
            "## FAILING TESTS TO FIX\n\n"
            "```\n" + failure_context.strip() + "\n```\n\n"
            "Read the assertions for the expected behavior. Concentrate on "
            "these; everything else in the file already passes."
        )

    if type_declarations:
        sections.append(type_declarations)

    if spec_excerpt:
        sections.append(f"## SPEC (for reference)\n\n{spec_excerpt}")

    sections.append(
        f"## CURRENT FILE (the file you are patching)\n\n"
        f"```\n{existing_content}\n```"
    )

    return "\n\n".join(sections)


def build_code_edit_script_draft_prompt(
    filepath: str,
    existing_content: str,
    description: str = "",
    spec_section: str = "",
    run_files: list[str] | None = None,
    previous_failure: str = "",
) -> str:
    """Ask for the spec's change to a large file as edits, on its first draft (#4683).

    The fix prompt above says tests fail; on a first draft none has run, and
    the change to make is the spec's. So this prompt carries the file's
    Section 6 subsection where the fix prompt carries failures, and the same
    edit-block format, which `apply_code_edit_script` applies either way.
    """
    lines = existing_content.count("\n") + 1
    sections: list[str] = [(
        f"# Implementation Request (edit script): {filepath}\n\n"
        f"The file below already exists and is too large to rewrite "
        f"({lines:,} lines). Make the change the specification describes for "
        "this file, and nothing else.\n\n"
        "Do NOT rewrite the file. Output ONLY edit blocks in EXACTLY this "
        "format:\n\n"
        "<<<<<<< SEARCH\n"
        "(exact lines copied verbatim from the CURRENT FILE below)\n"
        "=======\n"
        "(replacement lines)\n"
        ">>>>>>> REPLACE\n\n"
        "Rules:\n"
        "1. Each SEARCH text must be copied EXACTLY from the current file "
        "(character-for-character, including indentation) and must occur "
        "exactly ONCE in it. Keep SEARCH as small as practical (typically "
        "1-15 lines), and long enough to be unique.\n"
        "2. To INSERT new code, SEARCH for the nearest existing anchor "
        "line(s) and REPLACE with those same anchor lines plus the new code.\n"
        "3. Emit one edit block per change. Touch NOTHING the specification "
        "does not ask for -- code you do not name in a SEARCH block cannot "
        "and must not change.\n"
        "4. No preamble, no explanation, no markdown fences around the "
        "blocks -- edit blocks only.\n"
        "5. If the specification asks no change of THIS file, output exactly "
        "one line and nothing else: NO-EDIT: <why>."
    )]

    if description:
        sections.append(f"## WHAT THE CHANGE IS FOR\n\n{description}")

    if spec_section:
        sections.append(
            "## THE SPECIFICATION FOR THIS FILE\n\n"
            f"{spec_section}\n\n"
            "A diff's line numbers are the spec writer's and may be out of "
            "date. Place each change by its context lines in the CURRENT FILE."
        )

    if run_files:
        listed = "\n".join(f"- {path}" for path in run_files)
        sections.append(
            "## FILES THIS RUN MAY CHANGE\n\n"
            f"{listed}\n\n"
            "The other files on this list are written by their own requests. "
            "Change only this one here."
        )

    if previous_failure:
        sections.append(previous_attempt_section(previous_failure))

    sections.append(
        f"## CURRENT FILE (the file you are patching)\n\n"
        f"```\n{existing_content}\n```"
    )

    return "\n\n".join(sections)


def previous_attempt_section(reason: str) -> str:
    """What a retried edit script is told about the one before it (#4683)."""
    return (
        "## YOUR PREVIOUS EDIT SCRIPT COULD NOT BE USED\n\n"
        f"```\n{reason.strip()}\n```\n\n"
        "Copy every SEARCH text verbatim from the CURRENT FILE below, make "
        "each one occur exactly once, and send edit blocks only."
    )


_NO_EDIT_RE =re.compile(r"^\s*NO-EDIT\s*:?\s*(?P<reason>.*)$", re.IGNORECASE)


def _no_edit_reason(response: str) -> str | None:
    """The reason given on a `NO-EDIT: <why>` answer, or None (#2915).

    Only a response that IS the declaration counts -- one line, optionally
    fenced -- so a stray mention inside an edit block never silences a patch.
    """
    lines = [line for line in response.strip().splitlines() if line.strip()]
    lines = [line for line in lines if not line.strip().startswith("```")]
    if len(lines) != 1:
        return None
    match = _NO_EDIT_RE.match(lines[0])
    if match is None:
        return None
    return match.group("reason").strip() or "no reason given"


def apply_code_edit_script(
    response: str, existing_content: str
) -> EditScriptOutcome:
    """Parse and apply a fix response, or report why the caller must fall back.

    Drift is impossible BY CONSTRUCTION rather than by instruction: content the
    model does not name in a SEARCH block is never sent to the model's output
    at all, so it cannot be quietly rewritten. That is the property #1528 was
    built for and the one this issue asks the implementation stage to inherit.
    """
    declined = _no_edit_reason(response or "")
    if declined is not None:
        # #2915: a file the failures name but that has nothing to fix -- on
        # run-issue4-135112 windows.py was named by a circular import whose
        # fix was in collector.py -- answered with no blocks, and the caller
        # regenerated it whole. "Nothing to change here" is an answer, and
        # the file it is about stays exactly as it is.
        return EditScriptOutcome(existing_content, preserved=1.0, no_edit=declined)

    blocks = parse_edit_blocks(response or "")
    if not blocks:
        return EditScriptOutcome(None, failures=["no edit blocks in response"])

    patched, failures = apply_edit_blocks(existing_content, blocks)
    if failures:
        # Partial application is never returned as success -- the same contract
        # the spec stage holds.
        return EditScriptOutcome(None, blocks=len(blocks), failures=failures)

    if not patched.strip():
        return EditScriptOutcome(
            None, blocks=len(blocks), failures=["edits emptied the file"]
        )

    return EditScriptOutcome(
        patched, blocks=len(blocks),
        preserved=unchanged_ratio(existing_content, patched),
    )


#: A response that is plainly a whole file rather than edit blocks. Cheap
#: pre-check so an obvious regeneration is not run through the parser.
_LOOKS_LIKE_WHOLE_FILE = re.compile(r"^\s*(?:```|from |import |#!|\"\"\")")


def response_is_a_regeneration(response: str) -> bool:
    """Did the model ignore the format and send the file back anyway?"""
    if not response:
        return False
    if "<<<<<<< SEARCH" in response:
        return False
    return bool(_LOOKS_LIKE_WHOLE_FILE.match(response))
