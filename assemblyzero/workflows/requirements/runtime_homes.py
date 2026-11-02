"""Where the issue's runtime concepts are built, and whether the plan goes there (#4537).

An LLD run approved a plan whose requirements said "the observation generator
MUST set `stale: true`" while its Files Changed table added a new module beside
an offline compiler and changed nothing the target runs. The target built each
turn's observation in one function of one TypeScript file, and the plan never
listed that file. The drafter had not been told where the observation was
built, mechanical validation had nothing to compare the requirements with, and
the reviewer approved it in three lines.

One finder serves three readers:

- N0b (`analyze_codebase`) runs `find_runtime_homes` on the issue, and the
  drafter is shown each home as the place the change must land (R1).
- Mechanical validation refuses an LLD whose requirement names a concept while
  Section 2.1 changes no file that builds or declares it (R2), through
  `unlanded_requirements`.
- The reviewer is asked, for each requirement, which listed file implements
  it (R3), through `requirement_trace_brief`.

What counts is decided by parsers, never by a pattern over prose. A concept is
a name the issue writes as an identifier, and that the target declares as a
type: a Python class, read with `ast`, or a TypeScript interface, type alias,
class or enum, read with tree-sitter. Its builders are the functions whose
declared return type names it. The regular expression here is a tokenizer: it
splits text into identifier-shaped words, and decides nothing about them.
"""

from __future__ import annotations

import ast
import functools
import re
from pathlib import Path

import tree_sitter_typescript
from tree_sitter import Language, Node, Parser

from assemblyzero.core.interface_surface import list_repo_source_files

#: A word that can be a name in code. The tokenizer, and nothing more.
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

#: The marks that end a sentence, and the bar that opens a table cell. A
#: capitalized word after one of them is capitalized by position, so its
#: capital does not make it a name.
_SENTENCE_ENDS = frozenset(".!?:|")

#: How a fenced block opens and closes in markdown.
_FENCES = ("```", "~~~")

#: The markdown that can open a line before its first word: whitespace, list
#: bullets and numbers, quote and table bars, emphasis.
_LINE_OPENERS = " \t-*+>|_0123456789.)"

#: How a test file is named in the languages the finder reads. A test helper
#: that returns the concept is not where the target builds it at runtime.
#: (`list_repo_source_files` already leaves out `tests/` and `test/`.)
_TEST_NAMES = frozenset({"conftest.py"})
_TEST_PREFIXES = ("test_",)
_TEST_SUFFIXES = ("_test.py", ".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx")

#: The TypeScript declarations a concept's type can come from.
_TS_TYPES = frozenset({
    "interface_declaration", "type_alias_declaration", "class_declaration",
    "abstract_class_declaration", "enum_declaration",
})

#: The TypeScript nodes that are functions, and so can declare a return type.
_TS_FUNCTIONS = frozenset({
    "function_declaration", "generator_function_declaration",
    "method_definition", "arrow_function", "function_expression",
})

#: Return annotations that say what a function checks, not what it returns:
#: `x is T` and `asserts x is T`. A type guard does not build its type.
_TS_NOT_A_RESULT = frozenset({"type_predicate_annotation", "asserts_annotation"})

#: The node holding an unnamed function's name, by the parent's node type.
_TS_NAME_HOLDER = {
    "variable_declarator": "name",
    "pair": "key",
    "public_field_definition": "name",
    "assignment_expression": "left",
}

#: The endings an English plural adds to a noun. A requirement that speaks of
#: "observations" names the `Observation` concept.
_PLURAL_ENDINGS = ("", "s", "es")

#: How many builders the drafter is shown for one concept.
_BUILDERS_SHOWN = 6

#: How much of a requirement a refusal quotes.
_QUOTE_CAP = 220

#: The drafter's and the reviewer's heading for the homes.
RUNTIME_HOMES_TITLE = "## Where the Issue's Runtime Concepts Are Built"

#: The reviewer's heading for the per-requirement question.
REQUIREMENT_TRACE_TITLE = "## Which Listed File Implements Each Requirement (BLOCKING)"

#: The question asked of every requirement.
TRACE_QUESTION = "Which file listed in Section 2.1 implements this requirement?"


# ---------------------------------------------------------------------------
# The names the issue writes
# ---------------------------------------------------------------------------


def _opens_sentence(before: str) -> bool:
    """Does a word written after ``before``, on the same line, open a sentence?"""
    text = before.rstrip()
    if not text.strip(_LINE_OPENERS):
        return True
    return text[-1] in _SENTENCE_ENDS


def _labels_a_number(after: str) -> bool:
    """Is the word a label for the number after it: `Section 6`, `Tier 1`?
    A label names a part of a document, never a concept in the code."""
    return after.startswith(" ") and after.lstrip(" ")[:1].isdigit()


def _capitalized_word(token: str) -> bool:
    """Capital first letter and a lowercase letter somewhere: `Observation`,
    not `MUST` or `HTTP`."""
    return token[0].isupper() and any(c.islower() for c in token)


def _camel_case(token: str) -> bool:
    """A capital after the first letter, with lowercase too: `EngineState`.
    English never writes a word this way, so its position does not matter."""
    return any(c.isupper() for c in token[1:]) and any(c.islower() for c in token)


def issue_concept_names(issue_text: str) -> list[str]:
    """The words the issue writes as names, in the order it first writes them.

    A word is written as a name when it sits in backticks, when it is camel
    case, or when it is capitalized somewhere a sentence does not begin and is
    not the label of a number (`Section 6`). A heading's words are capitalized
    by position, and a fenced block holds logs and code quoted as evidence,
    whose names are incidental: both are passed over. None of this decides
    that a name is a concept: only a declaration in the target does, in
    `find_runtime_homes`.
    """
    names: list[str] = []
    seen: set[str] = set()
    fenced = False
    for line in (issue_text or "").splitlines():
        if line.lstrip().startswith(_FENCES):
            fenced = not fenced
            continue
        if fenced or line.lstrip().startswith("#"):
            continue
        offset = 0
        for index, segment in enumerate(line.split("`")):
            in_code = index % 2 == 1
            for match in _IDENTIFIER.finditer(segment):
                token = match.group()
                named = in_code or _camel_case(token) or (
                    _capitalized_word(token)
                    and not _opens_sentence(line[: offset + match.start()])
                    and not _labels_a_number(segment[match.end():])
                )
                if named and token not in seen:
                    seen.add(token)
                    names.append(token)
            offset += len(segment) + 1
    return names


# ---------------------------------------------------------------------------
# Declarations and builders, read by parsers
# ---------------------------------------------------------------------------


def _is_test_file(path: Path) -> bool:
    name = path.name
    return (
        name in _TEST_NAMES
        or name.startswith(_TEST_PREFIXES)
        or name.endswith(_TEST_SUFFIXES)
    )


def _annotation_names(annotation: ast.expr) -> set[str]:
    """Every name a Python annotation mentions, string forward references too."""
    found: set[str] = set()
    for node in ast.walk(annotation):
        if isinstance(node, ast.Name):
            found.add(node.id)
        elif isinstance(node, ast.Attribute):
            found.add(node.attr)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            found.update(_IDENTIFIER.findall(node.value))
    return found


def _python_facts(
    text: str, filename: str, names: set[str]
) -> tuple[set[str], list[tuple[str, str, int]]]:
    """The concept types a Python file declares, and its builders of them.

    Raises:
        SyntaxError: the file does not parse. It is not skipped: a file the
            finder cannot read could be the one that builds the concept.
    """
    tree = ast.parse(text, filename=filename)
    declared: set[str] = set()
    builders: list[tuple[str, str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name in names:
            declared.add(node.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.returns:
            for concept in sorted(_annotation_names(node.returns) & names):
                builders.append((concept, node.name, node.lineno))
    return declared, builders


@functools.cache
def _ts_parser(tsx: bool) -> Parser:
    language = (
        tree_sitter_typescript.language_tsx()
        if tsx else tree_sitter_typescript.language_typescript()
    )
    return Parser(Language(language))


def _ts_text(source: bytes, node: Node) -> str:
    return source[node.start_byte:node.end_byte].decode("utf-8")


def _ts_function_name(node: Node, source: bytes) -> str:
    name = node.child_by_field_name("name")
    if name is None and node.parent is not None:
        field = _TS_NAME_HOLDER.get(node.parent.type)
        if field is not None:
            name = node.parent.child_by_field_name(field)
    return _ts_text(source, name) if name is not None else "an anonymous function"


def _ts_type_names(node: Node, source: bytes) -> set[str]:
    """Every type identifier written under ``node``."""
    found: set[str] = set()
    stack = [node]
    while stack:
        current = stack.pop()
        if current.type == "type_identifier":
            found.add(_ts_text(source, current))
        stack.extend(current.children)
    return found


def _typescript_facts(
    text: str, names: set[str], *, tsx: bool
) -> tuple[set[str], list[tuple[str, str, int]]]:
    """The concept types a TypeScript file declares, and its builders of them.

    tree-sitter reads through what it cannot parse, so a gap in its grammar
    costs a node, not the file (the interface surface relies on the same).
    """
    source = text.encode("utf-8")
    root = _ts_parser(tsx).parse(source).root_node
    declared: set[str] = set()
    builders: list[tuple[str, str, int]] = []
    stack = [root]
    while stack:
        node = stack.pop()
        if node.type in _TS_TYPES:
            name = node.child_by_field_name("name")
            if name is not None and _ts_text(source, name) in names:
                declared.add(_ts_text(source, name))
        elif node.type in _TS_FUNCTIONS:
            returns = node.child_by_field_name("return_type")
            if returns is not None and returns.type not in _TS_NOT_A_RESULT:
                function = _ts_function_name(node, source)
                for concept in sorted(_ts_type_names(returns, source) & names):
                    builders.append((concept, function, node.start_point[0] + 1))
        stack.extend(node.children)
    return declared, builders


def _facts(
    path: Path, text: str, names: set[str]
) -> tuple[set[str], list[tuple[str, str, int]]]:
    if path.suffix == ".py":
        return _python_facts(text, str(path), names)
    return _typescript_facts(text, names, tsx=path.suffix == ".tsx")


def find_runtime_homes(repo_root: Path, issue_text: str) -> dict[str, dict]:
    """Where the target builds each concept the issue names (R1).

    A concept is a name from `issue_concept_names` that the target declares as
    a type. Its builders are the functions whose return type names it, outside
    test files. A concept the target declares and never returns from a
    function has no home here: nothing says where its behaviour runs.

    Args:
        repo_root: The tree the LLD is designed against.
        issue_text: The issue body.

    Returns:
        ``{concept: {"declared_in": [path], "builders": [{"function", "file",
        "line"}]}}``, paths relative to ``repo_root`` in posix form, concepts
        in the order the issue names them. Empty when the issue names no
        concept the target builds.

    Raises:
        OSError: the tree cannot be walked or a file cannot be read.
        UnicodeDecodeError: a source file is not UTF-8.
        SyntaxError: a Python file that mentions a name does not parse.
    """
    names = issue_concept_names(issue_text)
    if not names:
        return {}
    root = Path(repo_root).resolve()
    wanted = set(names)
    declared: dict[str, set[str]] = {}
    builders: dict[str, list[dict]] = {}
    for path in list_repo_source_files(root):
        if _is_test_file(path):
            continue
        # utf-8-sig: a leading byte-order mark is not code. Python's import
        # system skips one, and `ast.parse` refuses it.
        text = path.read_text(encoding="utf-8-sig")
        present = {name for name in wanted if name in text}
        if not present:
            continue
        rel = path.relative_to(root).as_posix()
        types, functions = _facts(path, text, present)
        for concept in types:
            declared.setdefault(concept, set()).add(rel)
        for concept, function, line in functions:
            builders.setdefault(concept, []).append(
                {"function": function, "file": rel, "line": line}
            )
    homes: dict[str, dict] = {}
    for concept in names:
        if concept in declared and builders.get(concept):
            homes[concept] = {
                "declared_in": sorted(declared[concept]),
                "builders": sorted(
                    builders[concept], key=lambda b: (b["file"], b["line"])
                ),
            }
    return homes


def builder_files(home: dict) -> list[str]:
    """The files that build one concept, each once, in order."""
    files: list[str] = []
    for builder in home.get("builders") or []:
        if builder["file"] not in files:
            files.append(builder["file"])
    return files


def runtime_home_files(homes: dict[str, dict]) -> list[str]:
    """Every file that builds a concept, each once, in concept order."""
    files: list[str] = []
    for home in (homes or {}).values():
        for path in builder_files(home):
            if path not in files:
                files.append(path)
    return files


def format_runtime_homes_section(homes: dict[str, dict]) -> str:
    """The homes as the drafter and the reviewer read them; empty for none."""
    if not homes:
        return ""
    lines = [
        RUNTIME_HOMES_TITLE,
        "",
        (
            "The issue names these concepts, and the target builds each one at "
            "runtime in the functions listed. A requirement that changes what "
            "one of them carries, or how it is built, lands in a file that "
            "builds it: list that file in Section 2.1 as Modify and put the "
            "change there. A new module the target never calls changes nothing "
            "at runtime. Mechanical validation refuses a plan with a "
            "requirement that names one of these concepts while Section 2.1 "
            "changes no file that builds or declares it."
        ),
        "",
    ]
    for concept, home in homes.items():
        declared = ", ".join(f"`{p}`" for p in home.get("declared_in") or [])
        built = home.get("builders") or []
        shown = "; ".join(
            f"`{b['function']}` in `{b['file']}`, line {b['line']}"
            for b in built[:_BUILDERS_SHOWN]
        )
        more = len(built) - _BUILDERS_SHOWN
        tail = f"; and {more} more" if more > 0 else ""
        lines.append(f"- `{concept}` (declared in {declared}): built by {shown}{tail}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# R2: a requirement about a concept lands in a file that builds it
# ---------------------------------------------------------------------------


def requirement_names_concept(text: str, concept: str) -> bool:
    """Is one of the requirement's words the concept's name, in any case,
    singular or plural? `grid.observation_outage` is two words, neither of
    them `observation`."""
    stem = concept.lower()
    forms = {stem + ending for ending in _PLURAL_ENDINGS}
    return any(word.lower() in forms for word in _IDENTIFIER.findall(text))


def _quote(text: str) -> str:
    if len(text) <= _QUOTE_CAP:
        return text
    return text[:_QUOTE_CAP].rsplit(" ", 1)[0] + " ..."


def _norm(path: str) -> str:
    path = path.strip().replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    return path


def unlanded_requirements(
    requirements: list[dict],
    files: list[dict],
    homes: dict[str, dict],
) -> list[str]:
    """One refusal for each requirement that names a concept while the file
    list changes none of the files that build or declare it (R2).

    A file that declares the concept's type counts as well as one that builds
    it: a requirement about a concept the program consumes, rather than
    builds, can land in the type and its consumers. The refusal is for a plan
    that touches neither, which is the plan that cannot change the runtime.

    Args:
        requirements: ``extract_requirements`` output, ``{"id", "text"}``.
        files: ``parse_files_changed_table`` output. A Delete changes no
            behaviour into a file, so it does not count.
        homes: ``find_runtime_homes`` output.

    Returns:
        Messages, each naming the requirement, quoting it, and naming the
        file that builds the concept, which the plan must change.
    """
    changed = {
        _norm(f.get("path", ""))
        for f in files
        if str(f.get("change_type", "")).lower() not in ("delete", "remove")
    }
    messages: list[str] = []
    for requirement in requirements:
        missing: list[str] = []
        needed: list[str] = []
        for concept, home in homes.items():
            if not requirement_names_concept(requirement["text"], concept):
                continue
            built_in = builder_files(home)
            landing = set(built_in) | set(home.get("declared_in") or [])
            if built_in and not changed.intersection(landing):
                builders = ", ".join(
                    f"`{b['function']}` in `{b['file']}`" for b in home["builders"]
                )
                missing.append(f"`{concept}`, which the target builds at runtime by {builders}")
                needed.extend(p for p in built_in if p not in needed)
        if missing:
            number = requirement["id"].removeprefix("REQ-")
            messages.append(
                f"Requirement {number} (\"{_quote(requirement['text'])}\") names "
                f"{'; and '.join(missing)}. Section 2.1 changes no file that "
                f"builds or declares it, so no listed file can implement it: add "
                f"{', '.join(f'`{p}`' for p in needed)} to Section 2.1 as Modify "
                f"and put the change there, or take the requirement out of scope "
                f"(#4537)."
            )
    return messages


# ---------------------------------------------------------------------------
# R3: the reviewer is asked, for each requirement, which listed file does it
# ---------------------------------------------------------------------------


def requirement_trace_brief(draft: str) -> str:
    """The per-requirement question for the adversarial review (R3).

    Empty when the draft has no Section 3, which test-plan validation has
    already refused before any review.
    """
    from assemblyzero.core.section_utils import drafter_authored, section_body
    from assemblyzero.core.validation.test_plan_validator import (
        _SECTION_3_TITLE_RE,
        extract_requirements,
    )
    from assemblyzero.workflows.requirements.nodes.validate_mechanical import (
        parse_files_changed_table,
    )

    if section_body(drafter_authored(draft), _SECTION_3_TITLE_RE) is None:
        return ""
    requirements = extract_requirements(draft)
    if not requirements:
        return ""
    files, _errors = parse_files_changed_table(draft)
    listed = (
        "\n".join(f"- `{f['path']}` ({f['change_type']})" for f in files)
        if files else "- (Section 2.1 lists no file)"
    )
    asked = "\n".join(
        f"{r['id'].removeprefix('REQ-')}. {r['text']}\n   {TRACE_QUESTION}"
        for r in requirements
    )
    return (
        f"{REQUIREMENT_TRACE_TITLE}\n\n"
        "Answer this for every requirement below before you give a verdict: "
        "name the file listed in Section 2.1 that implements it. A requirement "
        "that no listed file can implement is a Tier 1 BLOCKING finding: the "
        "verdict is REVISE, with a feedback item that names the requirement "
        "and the file in the target where its behaviour runs. A requirement "
        "about runtime behaviour (what the running program computes, shows or "
        "stores) is implemented only by a file the running program executes; "
        "a new module that nothing in the target calls implements nothing.\n\n"
        f"Files listed in Section 2.1:\n{listed}\n\n"
        f"Requirements:\n{asked}"
    )
