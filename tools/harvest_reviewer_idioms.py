"""Harvest framework idioms the spec reviewer dictates, for the #2397 contract.

Read-only. Scans a target repo's readiness verdicts for call expressions the
reviewer names in backticks, and reports which ones the gate-agreement corpus
(tests/fixtures/reviewer_idioms/framework_idioms.py) does not yet cover.

WHY THIS EXISTS RATHER THAN READING A PROMPT
--------------------------------------------
#2397 proposed sourcing the corpus from the reviewer's prompt "where it
enumerates" the idioms. It does not enumerate them. Neither review_spec.py nor
generate_spec.py names a single one — the reviewer is a general model applying
its own knowledge of pytest best practice, so the population is not derivable
from our code. The only honest source is what the reviewer has actually said,
which is on disk in the lineage.

WHAT IT CANNOT DO
-----------------
It cannot tell a framework idiom from a repo-owned one. `apply_exit_write()` and
`request.config.getoption(...)` are the same shape to a regex, and only the
first is the target repo's business. Output is a triage list for a human, not an
auto-updater. Nothing is written.

Usage:
    poetry run python tools/harvest_reviewer_idioms.py --repo /c/.../boostgauge
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

#: A backticked call expression: `receiver.method(args)` or `func(args)`.
_IDIOM_RE = re.compile(r"`([a-zA-Z_][a-zA-Z0-9_.]*\([^`]*\))`")

_CORPUS = (
    Path(__file__).parent.parent
    / "tests" / "fixtures" / "reviewer_idioms" / "framework_idioms.py"
)


def _corpus_text() -> str:
    if not _CORPUS.exists():
        print(f"corpus not found: {_CORPUS}", file=sys.stderr)
        return ""
    return _CORPUS.read_text(encoding="utf-8")


def _call_key(idiom: str) -> str:
    """`request.config.getoption("--x", False)` -> `request.config.getoption(`."""
    return idiom.split("(", 1)[0] + "("


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", required=True, help="Target repo root")
    ap.add_argument(
        "--all",
        action="store_true",
        help="List every harvested idiom, not just uncovered ones",
    )
    args = ap.parse_args()

    repo = Path(args.repo)
    lineage = repo / "docs" / "lineage"
    if not lineage.is_dir():
        print(f"no lineage directory under {repo}", file=sys.stderr)
        return 2

    verdicts = sorted(lineage.rglob("*readiness-verdict*.md"))
    if not verdicts:
        print(f"no readiness verdicts under {lineage}", file=sys.stderr)
        return 2

    corpus = _corpus_text()
    found: dict[str, set[str]] = {}
    for verdict in verdicts:
        try:
            text = verdict.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in _IDIOM_RE.finditer(text):
            idiom = m.group(1)
            found.setdefault(idiom, set()).add(
                str(verdict.relative_to(repo)).replace("\\", "/")
            )

    covered, uncovered = [], []
    for idiom in sorted(found):
        (covered if _call_key(idiom) in corpus else uncovered).append(idiom)

    print(f"verdicts scanned : {len(verdicts)}")
    print(f"idioms harvested : {len(found)}")
    print(f"covered by corpus: {len(covered)}")
    print(f"NOT covered      : {len(uncovered)}")

    if args.all and covered:
        print("\n-- covered --")
        for idiom in covered:
            print(f"  {idiom}")

    if uncovered:
        print("\n-- candidates for triage --")
        print("   (a repo-owned call belongs here and needs no action; a")
        print("    FRAMEWORK call does not, and is a deadlock waiting to happen)")
        for idiom in uncovered:
            sources = sorted(found[idiom])
            print(f"  {idiom}")
            print(f"      seen in: {sources[0]}"
                  + (f" (+{len(sources) - 1} more)" if len(sources) > 1 else ""))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
