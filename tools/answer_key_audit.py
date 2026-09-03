#!/usr/bin/env python3
"""Run the pipeline's mechanical gates over code known to be right (#2722).

The logic lives in ``assemblyzero.speedrun.answer_key`` so the unit tests run
the same code this prints.

    poetry run python tools/answer_key_audit.py --repo /c/.../boostgauge
    poetry run python tools/answer_key_audit.py --repo <path> --save

Read-only against the target repo. Writes nothing except the optional saved
copy under ``docs/audits/``.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from assemblyzero.core.utf8_console import install as _install_utf8_console  # noqa: E402

_install_utf8_console()

from assemblyzero.speedrun.answer_key import audit, render  # noqa: E402


def default_save_path(repo: Path, when: datetime | None = None) -> Path:
    when = when or datetime.now()
    return (
        REPO_ROOT / "docs" / "audits"
        / f"0907-answer-key-audit-{repo.name}-{when:%Y-%m-%d}.md"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", required=True, type=Path,
                        help="target repository whose main carries the answer key")
    parser.add_argument("--save", action="store_true",
                        help="also write the report under docs/audits/")
    parser.add_argument("--save-path", type=Path, default=None)
    args = parser.parse_args(argv)

    repo = args.repo.resolve()
    if not repo.is_dir():
        print(f"No such repository: {repo}")
        return 2

    verdicts, coverage = audit(repo)
    text = render(repo, verdicts, coverage)
    print(text)

    if args.save or args.save_path:
        target = args.save_path or default_save_path(repo)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        print(f"Saved to {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
