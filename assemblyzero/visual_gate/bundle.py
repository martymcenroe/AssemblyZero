"""Review bundles: where a gate round's evidence lives (#2518).

Layout, in the TARGET repo's gitignored data dir::

    data/visual-gate/<issue>/round-001/
        render-*.png            what the operator judges
        manifest.json           the contract values that produced it
        feedback-pending.json   sentinel: served, awaiting the operator
        feedback.json           the operator's answer (written by the server)
    data/visual-gate/<issue>/approved/
        approved.png            the stamped render
        approved.json           sha256, source round, accumulated deltas,
                                measurements read from the picture

The bundle is machine-local working state, same class as speedrun run logs.
``feedback.json``'s appearance IS the wake signal: the serving run polls for
it, and a killed run reads it on resume -- either path lands in the same
verb dispatch.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

VERBS = ("approve", "reject", "modify")


def gate_root(target_repo: Path | str, issue: int) -> Path:
    return Path(target_repo) / "data" / "visual-gate" / str(issue)


def round_dirs(root: Path) -> list[Path]:
    """Existing round dirs, oldest first. Zero-padded names sort as time."""
    if not root.is_dir():
        return []
    return sorted(p for p in root.iterdir() if p.is_dir() and p.name.startswith("round-"))


def next_round_dir(root: Path) -> Path:
    existing = round_dirs(root)
    n = int(existing[-1].name.split("-")[1]) + 1 if existing else 1
    path = root / f"round-{n:03d}"
    path.mkdir(parents=True)
    return path


def write_pending(round_dir: Path, url: str) -> None:
    (round_dir / "feedback-pending.json").write_text(
        json.dumps({
            "served_at": datetime.now(tz=timezone.utc).isoformat(),
            "url": url,
        }, indent=2),
        encoding="utf-8",
    )


def read_feedback(round_dir: Path) -> dict | None:
    """The operator's answer, or None while it is pending.

    A malformed answer raises rather than reading as absent -- a half-written
    file must not dispatch a verb, and json.loads on a file mid-write is the
    one race here; the server writes to a temp name and renames, so a present
    ``feedback.json`` is always complete.
    """
    path = round_dir / "feedback.json"
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("verb") not in VERBS:
        raise ValueError(f"feedback.json carries unknown verb: {data.get('verb')!r}")
    return data


def write_feedback(round_dir: Path, verb: str, text: str) -> Path:
    """Atomic: temp-write then rename, in the destination dir (house rule)."""
    if verb not in VERBS:
        raise ValueError(f"unknown verb: {verb!r}")
    payload = {
        "verb": verb,
        "text": text,
        "submitted_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    final = round_dir / "feedback.json"
    tmp = round_dir / "feedback.json.tmp"
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(final)
    return final


def bundle_images(round_dir: Path) -> list[Path]:
    return sorted(round_dir.glob("*.png"))


def stamp_approved(
    root: Path, round_dir: Path, image: Path, *,
    deltas: list[dict], measurements: list[dict],
) -> Path:
    """The Approve verb's durable record: the picture and its provenance."""
    approved_dir = root / "approved"
    approved_dir.mkdir(parents=True, exist_ok=True)
    dest = approved_dir / "approved.png"
    shutil.copy2(image, dest)
    (approved_dir / "approved.json").write_text(
        json.dumps({
            "sha256": hashlib.sha256(dest.read_bytes()).hexdigest(),
            "source_round": round_dir.name,
            "source_image": image.name,
            "approved_at": datetime.now(tz=timezone.utc).isoformat(),
            "deltas": deltas,
            "measurements": measurements,
        }, indent=2),
        encoding="utf-8",
    )
    return dest
