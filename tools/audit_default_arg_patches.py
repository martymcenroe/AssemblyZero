"""Find tests made vacuous by default-argument binding (#2264).

The trap: a parameter written `def f(..., runner=_default_runner)` captures the
VALUE of `_default_runner` at definition time. A test that later patches
`module._default_runner` rebinds the module attribute, not the captured default,
so a call to `f()` that omits the argument uses the ORIGINAL collaborator. The
patch has no effect and the test passes while asserting nothing -- green while
testing nothing, which is the worst failure mode a test has.

Surfaced 2026-08-12 while shipping #2192: the first cut of those tests silently
tested nothing while appearing to pass.

## Why this reports so little

A patch is only vacuous when ALL THREE hold, and the check demands all three:

  1. the patched module itself captures that name as a function default;
  2. some call site invokes the capturing function WITHOUT passing it, so the
     frozen default is what actually gets used;
  3. a test patches the name at module level.

Dropping condition 2 is what makes this class of audit useless. A first cut of
this script matched on the bare attribute name and reported seven suspects, of
which zero were defects -- `sentinel_migrate.AUDIT_CSV` is captured as a default
AND patched by tests, but every caller passes it explicitly, so the patch is
live. A check that cries wolf seven times trains its reader to skip it.

An audit is a program, not an inspection: this is runnable, exits non-zero on a
finding, and is pinned by fixtures including a positive one, so it is known to
be capable of failing.

Usage:
    poetry run python tools/audit_default_arg_patches.py
    poetry run python tools/audit_default_arg_patches.py --json
    poetry run python tools/audit_default_arg_patches.py --suspects
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRS = ("assemblyzero", "tools")
TEST_DIRS = ("tests",)


def module_dotted_name(path: Path) -> str:
    return ".".join(path.relative_to(ROOT).with_suffix("").parts)


def captured_defaults(tree: ast.AST) -> dict[str, list[str]]:
    """{captured_name: [functions capturing it]} for one parsed module.

    Only bare Name defaults count. A literal, a call or an attribute cannot be
    rebound by a module-level patch, so it is not part of this trap.
    """
    captured: dict[str, list[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for default in list(node.args.defaults) + [
            d for d in node.args.kw_defaults if d is not None
        ]:
            if isinstance(default, ast.Name):
                captured.setdefault(default.id, []).append(node.name)
    return captured


#: A keyword-only parameter can never be reached positionally.
_UNREACHABLE_POSITIONALLY = 1 << 30


def parameter_for_default(
    tree: ast.AST, function: str, captured_name: str
) -> tuple[str, int] | None:
    """(parameter, positional index) of `function` holding `captured_name`.

    The INDEX is what makes this audit correct rather than merely cautious. A
    first cut treated any positional argument at a call site as possibly
    reaching the parameter and cleared the call; that silently cleared the
    canonical #2192 shape, `repo_slug(repo_root, runner=_default_runner)` called
    as `repo_slug(root)` -- one positional argument, and `runner` sitting at
    index 1 where it cannot possibly land. Caught by this audit's own positive
    fixture, which is the reason to have one.
    """
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name != function:
            continue
        positional = node.args.posonlyargs + node.args.args
        offset = len(positional) - len(node.args.defaults)
        for index, (arg, default) in enumerate(
            zip(positional[offset:], node.args.defaults), start=offset
        ):
            if isinstance(default, ast.Name) and default.id == captured_name:
                return arg.arg, index
        for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults):
            if (
                default is not None
                and isinstance(default, ast.Name)
                and default.id == captured_name
            ):
                return arg.arg, _UNREACHABLE_POSITIONALLY
    return None


def calls_omitting(
    tree: ast.AST, function: str, parameter: str, index: int
) -> list[int]:
    """Lines calling `function` WITHOUT supplying `parameter`.

    A call supplies it by keyword, by `**kwargs` (which might carry it), or by
    having enough positional arguments to reach `index`. Anything else omits it,
    and therefore uses the frozen default.
    """
    omitting: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        target = node.func
        name = (
            target.id if isinstance(target, ast.Name)
            else target.attr if isinstance(target, ast.Attribute)
            else None
        )
        if name != function:
            continue
        if any(kw.arg == parameter for kw in node.keywords):
            continue
        if any(kw.arg is None for kw in node.keywords):
            continue  # **kwargs could carry it
        if any(isinstance(a, ast.Starred) for a in node.args):
            continue  # *args could reach it
        if len(node.args) > index:
            continue  # a positional argument lands on it
        omitting.append(node.lineno)
    return omitting


_PATCH_STR = re.compile(r"""patch\(\s*["']([\w.]+)["']""")
_PATCH_OBJECT = re.compile(r"""patch\.object\(\s*([\w.]+)\s*,\s*["'](\w+)["']""")
_SETATTR = re.compile(r"""setattr\(\s*([\w.]+)\s*,\s*["'](\w+)["']""")


def patched_names(path: Path) -> list[tuple[int, str, str]]:
    """(line, target_expression, attribute) for every patch in a test file."""
    found: list[tuple[int, str, str]] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return found
    for number, line in enumerate(lines, start=1):
        for match in _PATCH_STR.finditer(line):
            module, _, attribute = match.group(1).rpartition(".")
            if module:
                found.append((number, module, attribute))
        for pattern in (_PATCH_OBJECT, _SETATTR):
            for match in pattern.finditer(line):
                found.append((number, match.group(1), match.group(2)))
    return found


def _module_matches(patch_target: str, dotted: str) -> bool:
    """Does a test's patch target name this module?

    Tests import tools as bare modules (`import sentinel_migrate`) and packages
    dotted, so the tail segment is compared as well as the full path.
    """
    if patch_target == dotted:
        return True
    return patch_target == dotted.rsplit(".", 1)[-1]


def scan_sources(source_dirs: tuple[str, ...] | None = None) -> dict[str, dict]:
    """{dotted_module: {captured_name: {"functions": [...], "frozen": [...]}}}.

    "frozen" lists (function, parameter, lines) where a call omits the argument
    and therefore uses the captured default.
    """
    # Resolved at CALL time, never captured as a default -- this script hunts
    # exactly that trap, and its own first cut fell into it: `SOURCE_DIRS` as a
    # default argument meant a test patching the module constant was testing
    # nothing, and the positive fixture failed for that reason rather than for
    # the reason it was written. The tool must not contain the defect it names.
    source_dirs = SOURCE_DIRS if source_dirs is None else source_dirs
    index: dict[str, dict] = {}
    for directory in source_dirs:
        base = ROOT / directory
        if not base.is_dir():
            continue
        for path in base.rglob("*.py"):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
            except (SyntaxError, OSError):
                continue
            captured = captured_defaults(tree)
            if not captured:
                continue
            dotted = module_dotted_name(path)
            for name, functions in captured.items():
                frozen = []
                for function in sorted(set(functions)):
                    resolved = parameter_for_default(tree, function, name)
                    if resolved is None:
                        continue
                    parameter, position = resolved
                    lines = calls_omitting(tree, function, parameter, position)
                    if lines:
                        frozen.append(
                            {"function": function, "parameter": parameter,
                             "lines": lines}
                        )
                index.setdefault(dotted, {})[name] = {
                    "functions": sorted(set(functions)),
                    "frozen": frozen,
                }
    return index


def audit(
    source_dirs: tuple[str, ...] | None = None,
    test_dirs: tuple[str, ...] | None = None,
) -> tuple[list[dict], list[dict]]:
    """(findings, suspects).

    A FINDING is a patch that cannot work: the module captures the name AND a
    call omits it. A SUSPECT captures the name but every call passes it, so the
    patch is live today and one refactor away from not being.

    Both directory tuples resolve at CALL time. See `scan_sources`.
    """
    test_dirs = TEST_DIRS if test_dirs is None else test_dirs
    index = scan_sources(source_dirs)
    findings: list[dict] = []
    suspects: list[dict] = []

    for directory in test_dirs:
        base = ROOT / directory
        if not base.is_dir():
            continue
        for path in base.rglob("*.py"):
            for line, target, attribute in patched_names(path):
                for dotted, names in index.items():
                    if not _module_matches(target, dotted):
                        continue
                    entry = names.get(attribute)
                    if entry is None:
                        continue
                    record = {
                        "test_file": str(path.relative_to(ROOT)).replace("\\", "/"),
                        "line": line,
                        "patch_target": f"{target}.{attribute}",
                        "module": dotted,
                        "captured_by": entry["functions"],
                        "frozen_call_sites": entry["frozen"],
                    }
                    (findings if entry["frozen"] else suspects).append(record)
    return findings, suspects


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="machine-readable")
    parser.add_argument(
        "--suspects", action="store_true",
        help="also list live patches whose target is captured as a default",
    )
    args = parser.parse_args(argv)

    findings, suspects = audit()

    if args.json:
        print(json.dumps({"findings": findings, "suspects": suspects}, indent=2))
        return 1 if findings else 0

    if findings:
        print(
            f"{len(findings)} VACUOUS PATCH(ES): the target is captured as a "
            f"function default and\na call site omits it, so the patch cannot "
            f"take effect and the test asserts nothing.\n"
        )
        for finding in findings:
            print(f"  {finding['test_file']}:{finding['line']}")
            print(f"    patches : {finding['patch_target']}")
            for frozen in finding["frozen_call_sites"]:
                print(
                    f"    frozen  : {frozen['function']}("
                    f"{frozen['parameter']}=...) called without it at line(s) "
                    f"{', '.join(str(n) for n in frozen['lines'])}"
                )
            print(
                "    fix     : inject the collaborator explicitly, or patch at "
                "the call boundary\n"
            )
    else:
        print("No vacuous default-argument patches found.")

    if args.suspects:
        print(
            f"\n{len(suspects)} live patch(es) whose target is ALSO captured as "
            f"a default.\nThese work today because every call passes the "
            f"argument explicitly."
        )
        for suspect in suspects:
            print(
                f"  {suspect['test_file']}:{suspect['line']} -> "
                f"{suspect['patch_target']} "
                f"(captured by {', '.join(suspect['captured_by'])})"
            )

    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
