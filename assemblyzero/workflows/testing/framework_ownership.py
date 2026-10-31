"""Which framework of the run runs a test file (#4236, #4243, #4245).

One rule, one home. The red and green phases split the run's test files
among its frameworks by it (#4236); N2 places each framework's scaffold where
that framework owns it (#4243); N4 registers the test files it writes by it
(#4245). Three copies of the rule would be three answers to one question.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from assemblyzero.workflows.testing.framework_detector import (
    JS_TEST_SUFFIXES,
    TestFramework,
    choose_by_test_name,
    source_extensions,
)
from assemblyzero.workflows.testing.runner_registry import (
    UnknownFrameworkError,
    resolve_framework,
)


class TestFileOwnershipError(ValueError):
    """No framework of the run would run a test file, or more than one would,
    or the state names a framework that is not one (#4236). Never a skip: a
    file nothing runs would read as passed."""

    __test__ = False  # a class named Test*, not a test


@dataclass(frozen=True)
class RunFramework:
    """One framework of the run: its config, and the directory it runs in,
    relative to the repository root ("." for the root)."""

    config: dict
    framework: TestFramework
    directory: str

    @property
    def label(self) -> str:
        return framework_label(self.framework, self.directory)


def framework_label(framework: TestFramework, directory: str | None) -> str:
    """`pytest` at the root; `vitest (web)` in a subdirectory."""
    if not directory or directory == ".":
        return framework.value
    return f"{framework.value} ({directory})"


def run_frameworks(state: dict) -> list[RunFramework]:
    """Every framework of the run, in the order N0 wrote them (#4236).

    `framework_configs` is what N0 wrote. A state without it (a checkpoint
    from before #4236) has `framework_config` alone, and that one framework
    is the run's; with neither, the run is pytest's. With more than one
    framework, an entry that names no test framework raises; with one, it is
    pytest, the single-framework default it always was.
    """
    configs = state.get("framework_configs")
    if not configs:
        framework_config = state.get("framework_config")
        configs = [framework_config] if framework_config else [{"framework": TestFramework.PYTEST}]
    configs = [config for config in configs if config]
    multi = len(configs) > 1
    out: list[RunFramework] = []
    for config in configs:
        # #3585: the registry raises for a framework it does not know, where
        # it used to answer None. Wrapped, so every caller that handles a run
        # it cannot own (N2 to N5) halts on it, naming the framework (#4311).
        try:
            framework = resolve_framework(config) if "framework" in config else TestFramework.PYTEST
        except UnknownFrameworkError as e:
            raise TestFileOwnershipError(str(e)) from e
        if framework is None:
            if multi:
                raise TestFileOwnershipError(
                    f"framework_configs names {config.get('framework')!r}, "
                    f"which is not a test framework"
                )
            framework = TestFramework.PYTEST  # the single-framework default, unchanged
        directory = os.path.normpath(config.get("working_directory") or ".")
        out.append(RunFramework(config, framework, directory))
    return out


def inside(relative: str, directory: str) -> bool:
    """`relative` (to the repository root) is in `directory` or below it."""
    return directory == "." or relative == directory or relative.startswith(directory + os.sep)


def _depth(directory: str) -> int:
    return 0 if directory == "." else directory.count(os.sep) + 1


def owner_of(path: str, frameworks: list[RunFramework], root: str) -> int:
    """The index in `frameworks` of the one framework that runs `path`: the
    frameworks whose file type it is, in the deepest directory that holds
    it, told apart by the file's name when two share it (#4236). Raises
    TestFileOwnershipError when none does or more than one does."""
    root = os.path.abspath(root)
    absolute = os.path.normpath(path if os.path.isabs(path) else os.path.join(root, path))
    if not (absolute == root or absolute.startswith(root + os.sep)):
        raise TestFileOwnershipError(
            f"test file {path} is outside the repository {root}; no framework "
            f"of this run would run it"
        )
    relative = os.path.relpath(absolute, root)
    candidates = [
        index for index, run in enumerate(frameworks)
        if relative.endswith(source_extensions(run.framework)) and inside(relative, run.directory)
    ]
    if candidates:
        deepest = max(_depth(frameworks[i].directory) for i in candidates)
        candidates = [i for i in candidates if _depth(frameworks[i].directory) == deepest]
    if len(candidates) > 1:
        chosen = choose_by_test_name([frameworks[i].framework for i in candidates], relative)
        candidates = [i for i in candidates if frameworks[i].framework in chosen]
    if len(candidates) == 1:
        return candidates[0]
    labels = ", ".join(run.label for run in frameworks)
    if not candidates:
        raise TestFileOwnershipError(
            f"test file {relative} belongs to no framework of this run "
            f"({labels}): none runs its file type in a directory that holds "
            f"it, so nothing would run it"
        )
    raise TestFileOwnershipError(
        f"test file {relative} belongs to more than one framework of this run "
        f"({', '.join(frameworks[i].label for i in candidates)}); "
        f"the run cannot say which one runs it"
    )


def measures_lines(framework: TestFramework) -> bool:
    """Whether a framework's coverage is of lines (#4436). Playwright's is of
    scenarios: a browser test names no line of the source."""
    return framework != TestFramework.PLAYWRIGHT


def judges_source(path: str, run: RunFramework, frameworks: list[RunFramework]) -> bool:
    """`path` (POSIX, relative to the repository) is source this framework is
    judged on (#4436): its file type, in its directory, and no framework that
    measures lines in a deeper directory holds it. `owner_of`'s rule, for a
    source file: a Vitest in `web/` judges `web/src/a.ts`, and a Jest at the
    root does not."""
    native = path.replace("/", os.sep)

    def holds(candidate: RunFramework) -> bool:
        return (
            measures_lines(candidate.framework)
            and path.endswith(source_extensions(candidate.framework))
            and inside(native, candidate.directory)
        )

    if not holds(run):
        return False
    deepest = max(_depth(other.directory) for other in (run, *frameworks) if holds(other))
    return _depth(run.directory) == deepest


def is_test_file(path: str) -> bool:
    """Whether a file N4 wrote is a test file (#4245): a Python file named
    `test_*` in a `tests/` directory, N4's rule since #460, or a file ending
    in one of the JavaScript test suffixes N0 resolves (`JS_TEST_SUFFIXES`).
    Which framework runs it is `owner_of`'s question, not this one's."""
    posix = path.replace("\\", "/")
    name = posix.rsplit("/", 1)[-1]
    if name.endswith(".py"):
        return "/tests/" in posix and name.startswith("test_")
    return name.endswith(JS_TEST_SUFFIXES)
