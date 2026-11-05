"""Whether a spec's TypeScript test bodies read members their types have (#4519).

#4514 proves a spec's Python test bodies before a run. Nothing read the
TypeScript ones, so a wrong one was found only at the green phase, after every
file had been written: on a real run a body read `score.cost_usd`, which the
target's `Score` type does not have, the implementer copied it, and the run
spent all three iterations on it.

The bodies refer to code the run has yet to write, so a plain compile over them
fails for reasons that are not faults. Only one kind of error is a fault this
early: a body reads a property the compiler says a type lacks, and the type is
declared in the target, in a file the plan does not change. A type the plan
adds or modifies is left alone, because it does not yet exist in its final
form. A name the plan adds cannot be resolved, so the compiler reports it as a
different error, which this check does not read.

The compiler is the target's own TypeScript, run on each body under the
target's own `tsconfig.json`. Each body is written for the run beside the file
it names, so its relative imports resolve, and removed afterwards.

The same reading of Section 10 serves the criteria check (#4551): a TypeScript
`it` or `test` call the spec carries, in Section 10 or in a TypeScript test
file Section 6 plans, is a test for the criterion it cites, as a Python test
function is. `spec_typescript_tests` finds those calls with the same parser.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import tree_sitter_typescript
from tree_sitter import Language, Node, Parser

from assemblyzero.workflows.target_env import hook_environment

#: The compiler's diagnostics for reading a property a type lacks: TS2339, and
#: TS2551, the same with a suggestion. Its `--pretty false` form:
#: `tests/x.ts(12,22): error TS2339: Property 'cost_usd' does not exist on type 'Score'.`
_MISSING_MEMBER = re.compile(
    r"^(?P<file>.+?)\((?P<line>\d+),(?P<column>\d+)\): error TS(?:2339|2551): "
    r"Property '(?P<member>[^']+)' does not exist on type '(?P<type>[^']+)'"
)

#: A type the check can look up by name: a bare identifier, not a union, a
#: generic, an array or an object literal.
_BARE_NAME = re.compile(r"^[A-Za-z_$][\w$]*$")

#: The declarations a type name can come from.
_DECLARATIONS = frozenset({
    "interface_declaration", "type_alias_declaration", "class_declaration",
    "abstract_class_declaration", "enum_declaration",
})

#: Directories a project's own sources are never in.
_NOT_SOURCE = frozenset({"node_modules", ".git", "dist", "build", "coverage", ".turbo"})

#: How long one compile may take.
COMPILE_TIMEOUT_SECONDS = 300

#: The fence tags a TypeScript test body is written under.
_TS_TAGS = frozenset({"typescript", "ts", "tsx"})

#: The TypeScript file names Vitest and Jest collect as tests by default
#: (#4551). A closed set: a file planned under another name is not read as a
#: test file.
TEST_FILE_SUFFIXES: tuple[str, ...] = (".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx")

#: The callees that declare a test.
_TEST_CALLEES = frozenset({"it", "test"})

#: Modifiers that declare a test which does not run, as in `it.todo(...)` and
#: `test.skip(...)` (#4551). A closed set, read from the callee's member names:
#: a test that never runs covers nothing.
_NOT_RUN = frozenset({"todo", "skip"})


class TypeScriptCheckError(RuntimeError):
    """The compiler could not be run, or said something that cannot be read."""


@dataclass(frozen=True)
class SpecBody:
    """A TypeScript test body from the spec's Section 10, and the file its
    first-line comment says it belongs in."""

    path: str
    text: str


@dataclass(frozen=True)
class MissingMember:
    """A body reads `member` of `type_name`, which the compiler says it lacks."""

    path: str
    line: int
    member: str
    type_name: str
    test: str


@dataclass(frozen=True)
class SpecTest:
    """A TypeScript `it` or `test` call the spec carries (#4551).

    ``source`` is what a criterion tag is read from: the call's own text, and
    the titles of the `describe` calls that hold it.
    """

    title: str
    source: str


@dataclass(frozen=True)
class _Fence:
    """A non-empty fenced block of the spec and where it sits."""

    section: str  # the `## ` heading it is under, without the hashes
    heading: str  # the nearest heading of any level above it
    tag: str      # the fence's tag, lower case
    lines: list[str]


def _fences(spec: str) -> list[_Fence]:
    """Every non-empty fenced block of the spec, in order. The one reader of
    the spec's fences here: Section 10's bodies and Section 6's planned test
    files are both chosen from it."""
    found: list[_Fence] = []
    section = heading = tag = ""
    fence: list[str] | None = None
    for line in spec.splitlines():
        if line.strip().startswith("```"):
            if fence is None:
                tag = line.strip()[3:].strip().lower()
                fence = []
            else:
                if fence:
                    found.append(_Fence(section, heading, tag, fence))
                fence = None
            continue
        if fence is not None:
            fence.append(line)
            continue
        if line.startswith("#"):
            heading = line.lstrip("#").strip()
            if line.startswith("## "):
                section = heading
    return found


def _section_ten_typescript_fences(spec: str) -> list[tuple[str, list[str]]]:
    """(tag, lines) of every non-empty TypeScript fence in Section 10."""
    return [
        (fence.tag, fence.lines) for fence in _fences(spec)
        if fence.section.startswith("10.") and fence.tag in _TS_TAGS
    ]


def spec_typescript_bodies(spec: str) -> list[SpecBody]:
    """Every TypeScript fence in Section 10 that names its file.

    A body names its file on its first line, as `// web/tests/replay.test.ts
    (...)`. One that names none cannot be placed where its imports resolve and
    is not returned.
    """
    bodies: list[SpecBody] = []
    for _tag, fence in _section_ten_typescript_fences(spec):
        body = _placed(fence)
        if body:
            bodies.append(body)
    return bodies


def is_typescript_test_file(path: str) -> bool:
    """Whether `path` names a TypeScript test file by `TEST_FILE_SUFFIXES`."""
    return path.replace("\\", "/").rsplit("/", 1)[-1].endswith(TEST_FILE_SUFFIXES)


def _post_image(diff: list[str]) -> list[str]:
    """The lines a unified diff leaves in its file: context and added lines,
    each without its one-character marker. File headers, hunk headers and
    removed lines are dropped. A line with no marker is kept as written,
    because drafters often omit the space before a context line."""
    kept: list[str] = []
    for line in diff:
        if line.startswith(("---", "+++", "@@", "\\")):
            continue
        if line.startswith("-"):
            continue
        kept.append(line[1:] if line.startswith(("+", " ")) else line)
    return kept


def planned_test_files(spec: str) -> list[tuple[str, str]]:
    """(path, text) for every TypeScript test file Section 6 plans (#4551).

    A Section 6 subsection plans a file when its heading names it, as
    ``### 6.8 `web/tests/replay.test.ts` (Modify)``. Its TypeScript fences
    are read as written and its diff fences as the file reads after the diff,
    so a test the diff removes is not read. Other fences are not read.
    """
    planned: list[tuple[str, str]] = []
    for fence in _fences(spec):
        if not fence.section.startswith("6."):
            continue
        if fence.tag not in _TS_TAGS and fence.tag != "diff":
            continue
        path = next(
            (
                word for word in fence.heading.replace("`", " ").split()
                if is_typescript_test_file(word)
            ),
            "",
        )
        if path:
            lines = _post_image(fence.lines) if fence.tag == "diff" else fence.lines
            planned.append((path, "\n".join(lines) + "\n"))
    return planned


def _placed(fence: list[str]) -> SpecBody | None:
    first = next((line.strip() for line in fence if line.strip()), "")
    if not first.startswith("//"):
        return None
    words = first[2:].split()
    path = words[0] if words else ""
    if not path.endswith((".ts", ".tsx")):
        return None
    return SpecBody(path=path, text="\n".join(fence) + "\n")


def project_of(repo_root: Path, path: str) -> Path | None:
    """The nearest directory at or above `path`'s, inside the repository, that
    holds a `tsconfig.json`, or None."""
    root = repo_root.resolve()
    here = (root / path).parent.resolve()
    while here == root or root in here.parents:
        if (here / "tsconfig.json").is_file():
            return here
        if here == root:
            break
        here = here.parent
    return None


def typescript_compiler(project: Path, repo_root: Path) -> Path | None:
    """The target's own installed `tsc`, found the way Node resolves a package:
    `node_modules/typescript` in the project or a directory above it, up to the
    repository root. None when the target has not installed it."""
    root = repo_root.resolve()
    here = project.resolve()
    while True:
        compiler = here / "node_modules" / "typescript" / "bin" / "tsc"
        if compiler.is_file():
            return compiler
        if here == root or root not in here.parents:
            return None
        here = here.parent


def _parser(tsx: bool) -> Parser:
    language = (
        tree_sitter_typescript.language_tsx() if tsx
        else tree_sitter_typescript.language_typescript()
    )
    return Parser(Language(language))


def _walk(node: Node):
    yield node
    for child in node.children:
        yield from _walk(child)


def declared_in(repo_root: Path, type_name: str) -> list[str]:
    """The repository's TypeScript files that declare `type_name` as an
    interface, type alias, class or enum, repository-relative and sorted."""
    root = repo_root.resolve()
    found: list[str] = []
    for directory, subdirectories, files in os.walk(root):
        subdirectories[:] = [d for d in subdirectories if d not in _NOT_SOURCE]
        for name in files:
            if not name.endswith((".ts", ".tsx")):
                continue
            path = Path(directory) / name
            try:
                source = path.read_bytes()
            except OSError as exc:
                raise TypeScriptCheckError(
                    f"{path} cannot be read to find where {type_name} is declared: {exc}"
                ) from exc
            if type_name.encode() not in source:
                continue
            tree = _parser(name.endswith(".tsx")).parse(source)
            for node in _walk(tree.root_node):
                if node.type in _DECLARATIONS:
                    named = node.child_by_field_name("name")
                    if named is not None and named.text.decode() == type_name:
                        found.append(path.relative_to(root).as_posix())
                        break
    return sorted(found)


def title_of_test_at(body: str, line: int, tsx: bool = False) -> str:
    """The title of the `it` or `test` call that holds `line` (1-based), or a
    description of the line when no call holds it."""
    tree = _parser(tsx).parse(body.encode())
    best = ""
    for node in _walk(tree.root_node):
        if node.type != "call_expression":
            continue
        if _callee_names(node.child_by_field_name("function"))[:1] not in (["it"], ["test"]):
            continue
        if not node.start_point[0] + 1 <= line <= node.end_point[0] + 1:
            continue
        title = _title(node)
        if title is not None:
            best = title
    return best or f"the body's line {line}"


def _callee_names(function: Node | None) -> list[str]:
    """The names a callee is built from, outermost first: `it` is ["it"],
    `it.skip` is ["it", "skip"], and `it.each(table)` is ["it", "each"]."""
    if function is None:
        return []
    if function.type == "identifier":
        return [function.text.decode()]
    if function.type == "member_expression":
        named = function.child_by_field_name("property")
        tail = [named.text.decode()] if named is not None else []
        return _callee_names(function.child_by_field_name("object")) + tail
    if function.type == "call_expression":
        return _callee_names(function.child_by_field_name("function"))
    return []


def _title(call: Node) -> str | None:
    """The first string argument of a call, without its quotes, or None."""
    arguments = call.child_by_field_name("arguments")
    first = next(
        (
            a for a in (arguments.named_children if arguments else [])
            if a.type in ("string", "template_string")
        ),
        None,
    )
    return first.text.decode()[1:-1] if first is not None else None


def typescript_tests(text: str, tsx: bool = False) -> list[SpecTest]:
    """Every `it` or `test` call in `text` that declares a test which runs.

    A call is a test when its callee is built from `it` or `test`, no member
    of the callee is in `_NOT_RUN`, and it has a string title. tree-sitter
    reads through what it cannot parse, so a fence that is not a whole module,
    or a diff's post-image, still yields the calls it holds.
    """
    tree = _parser(tsx).parse(text.encode("utf-8"))
    tests: list[SpecTest] = []
    for node in _walk(tree.root_node):
        if node.type != "call_expression":
            continue
        names = _callee_names(node.child_by_field_name("function"))
        if not names or names[0] not in _TEST_CALLEES or _NOT_RUN & set(names[1:]):
            continue
        title = _title(node)
        if title is None:
            continue
        held_by: list[str] = []
        parent = node.parent
        while parent is not None:
            if parent.type == "call_expression" and _callee_names(
                parent.child_by_field_name("function")
            )[:1] == ["describe"]:
                held = _title(parent)
                if held is not None:
                    held_by.insert(0, held)
            parent = parent.parent
        tests.append(SpecTest(
            title=title, source="\n".join([*held_by, node.text.decode()]),
        ))
    return tests


def section_ten_typescript_tests(spec: str) -> list[SpecTest]:
    """The test calls in Section 10's TypeScript fences, in spec order (#4680).

    The testing workflow's contract reads these and not Section 6's planned
    files, which restate them: counting both counts each test twice.
    """
    tests: list[SpecTest] = []
    for tag, fence in _section_ten_typescript_fences(spec):
        tests.extend(typescript_tests("\n".join(fence) + "\n", tsx=tag == "tsx"))
    return tests


def spec_typescript_tests(spec: str) -> list[SpecTest]:
    """Every TypeScript test the spec carries (#4551): the test calls in
    Section 10's TypeScript fences, and in the TypeScript test files Section 6
    plans (`planned_test_files`)."""
    tests = section_ten_typescript_tests(spec)
    for path, text in planned_test_files(spec):
        tests.extend(typescript_tests(text, tsx=path.endswith(".tsx")))
    return tests


def missing_members(
    repo_root: Path, project: Path, compiler: Path, bodies: list[SpecBody],
) -> list[MissingMember]:
    """Compile each body under the project's own configuration and return every
    read of a property its type lacks.

    Each body is written beside the file it names, as a hidden file, with a
    configuration that extends the project's and compiles that body alone.
    Both are removed before this returns, and a file that cannot be removed
    raises OSError naming it.
    """
    written: list[tuple[Path, SpecBody]] = []
    config = project / f"tsconfig.az-spec-probe-{os.getpid()}.json"
    try:
        for index, body in enumerate(bodies):
            target = (repo_root / body.path).resolve()
            suffix = ".tsx" if body.path.endswith(".tsx") else ".ts"
            probe = target.parent / f".az-spec-probe-{os.getpid()}-{index}{suffix}"
            probe.parent.mkdir(parents=True, exist_ok=True)
            probe.write_text(body.text, encoding="utf-8")
            written.append((probe, body))
        config.write_text(json.dumps({
            "extends": "./tsconfig.json",
            "compilerOptions": {"noEmit": True, "incremental": False},
            "files": [os.path.relpath(p, project).replace(os.sep, "/") for p, _ in written],
            "include": [],
        }), encoding="utf-8")
        try:
            result = subprocess.run(
                ["node", str(compiler), "-p", config.name, "--pretty", "false"],
                cwd=str(project), env=hook_environment(), capture_output=True,
                text=True, timeout=COMPILE_TIMEOUT_SECONDS, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise TypeScriptCheckError(
                f"the target's TypeScript compiler ({compiler}) could not be run in "
                f"{project}: {type(exc).__name__}: {exc}"
            ) from exc
        if result.returncode not in (0, 1, 2):
            raise TypeScriptCheckError(
                f"the target's TypeScript compiler exited {result.returncode} in "
                f"{project}: {(result.stderr or result.stdout).strip()[:400]}"
            )
        by_file = {
            os.path.normcase(str(p)): (p, body) for p, body in written
        }
        found: list[MissingMember] = []
        for line in result.stdout.splitlines():
            match = _MISSING_MEMBER.match(line.strip())
            if not match:
                continue
            where = os.path.normcase(str((project / match.group("file")).resolve()))
            if where not in by_file:
                continue
            probe, body = by_file[where]
            number = int(match.group("line"))
            found.append(MissingMember(
                path=body.path, line=number, member=match.group("member"),
                type_name=match.group("type"),
                test=title_of_test_at(body.text, number, tsx=probe.suffix == ".tsx"),
            ))
        return found
    finally:
        # Each removal that fails raises OSError, naming the file left behind.
        for path in [config] + [p for p, _ in written]:
            path.unlink(missing_ok=True)


def is_bare_type_name(type_name: str) -> bool:
    """Whether the compiler named a type this check can look up by name."""
    return bool(_BARE_NAME.match(type_name))
