"""What a Modify reply changed that the spec's hunks did not ask for (#4522).

A whole-file reply can change any line of the file it replaces. On a real run
one rewrote a field of a target's schema that no requirement touched; every
test, all fourteen steps and adversarial review passed, and a person reading
the diff found it. The spec's Section 6 gives each Modify file's change as
unified-diff hunks, so a changed line can be held against them: inside a hunk,
or one of its lines, it was asked for, and anything else is reported.

The report advises and does not stop the run. A hunk's line numbers are the
spec writer's and are not trusted; a hunk is placed in the base by its own
context and removed lines.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

#: A Section 6 subsection heading: `### 6.N `path` (Change)`. The same form
#: `load_lld.extract_plan_code` reads.
_HEADING = re.compile(r"###\s+6\.\d+\s+`([^`]+)`")

#: The elision a spec writes for context it leaves out.
_ELISION = "..."


@dataclass(frozen=True)
class Hunk:
    """One hunk of a spec's diff: its base side (context and removed lines,
    in order) and the lines it adds and removes."""

    old: tuple[str, ...]
    added: tuple[str, ...]
    removed: tuple[str, ...]


@dataclass(frozen=True)
class Unrequested:
    """A changed line no hunk asked for. `line` counts from 1, in the new file
    for a line added or changed and in the base for one removed."""

    line: int
    text: str
    kind: str


def _hunks_of(fence: list[str]) -> list[Hunk]:
    hunks: list[Hunk] = []
    old: list[str] = []
    added: list[str] = []
    removed: list[str] = []

    def close() -> None:
        if old or added or removed:
            hunks.append(Hunk(tuple(old), tuple(added), tuple(removed)))
        old.clear()
        added.clear()
        removed.clear()

    for line in fence:
        if line.startswith("@@"):
            close()
        elif line.startswith(("--- ", "+++ ", "\\")):
            continue
        elif line.startswith("+"):
            added.append(line[1:])
        elif line.startswith("-"):
            removed.append(line[1:])
            old.append(line[1:])
        else:
            old.append(line.removeprefix(" "))
    close()
    return hunks


def spec_hunks(spec_content: str) -> dict[str, list[Hunk]]:
    """Every `diff` fence's hunks under each Section 6 heading, by path.

    A file whose subsection carries no diff fence is absent: what the spec
    asked of it cannot be told line by line. Fences are tracked line by line,
    so a `## ` line inside a fence never reads as a heading.
    """
    out: dict[str, list[Hunk]] = {}
    in_section = in_fence = False
    current: str | None = None
    fence: list[str] | None = None
    for line in spec_content.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            if not in_fence:
                in_fence = True
                tag = stripped[3:].strip().lower()
                fence = [] if (in_section and current and tag == "diff") else None
            else:
                in_fence = False
                if fence is not None and current:
                    out.setdefault(current, []).extend(_hunks_of(fence))
                fence = None
            continue
        if in_fence:
            if fence is not None:
                fence.append(line)
            continue
        if line.startswith("## "):
            in_section = line[3:].lstrip().startswith("6.")
            current = None
        elif in_section and line.startswith("### "):
            heading = _HEADING.match(line)
            current = heading.group(1).strip() if heading else None
    return {path: hunks for path, hunks in out.items() if hunks}


def _locate(hunk: Hunk, base: list[str]) -> tuple[int, int] | None:
    """Where in the base this hunk's base side sits, as [start, end), or None
    when it cannot be found. Anchored on the longest run of its lines the base
    holds, compared without indentation, and widened to the hunk's length."""
    old = [line.strip() for line in hunk.old if line.strip() != _ELISION]
    if not old:
        return None
    matcher = SequenceMatcher(None, base, old, autojunk=False)
    match = matcher.find_longest_match(0, len(base), 0, len(old))
    if match.size < min(2, len(old)):
        return None
    start = max(0, match.a - match.b)
    return start, min(len(base), start + len(old))


def unrequested_lines(base_text: str, new_text: str, hunks: list[Hunk]) -> list[Unrequested]:
    """The lines `new_text` changed against `base_text` that no hunk covers.

    A change is covered when it falls inside, or at the edge of, a hunk's place
    in the base, or when its text is a line the hunks add or remove. A changed
    line reports its new text; a deleted one reports what it removed. Blank
    lines are never reported.
    """
    base = [line.strip() for line in base_text.splitlines()]
    new_raw = new_text.splitlines()
    new = [line.strip() for line in new_raw]
    regions = [region for region in (_locate(h, base) for h in hunks) if region]
    added = {line.strip() for h in hunks for line in h.added}
    removed = {line.strip() for h in hunks for line in h.removed}

    found: list[Unrequested] = []
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, base, new, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        if any(i1 <= end and i2 >= start for start, end in regions):
            continue
        if tag == "delete":
            found.extend(
                Unrequested(i + 1, base[i], "removed")
                for i in range(i1, i2) if base[i] and base[i] not in removed
            )
            continue
        found.extend(
            Unrequested(j + 1, new[j], "added")
            for j in range(j1, j2) if new[j] and new[j] not in added
        )
    return found
