#!/usr/bin/env python3
"""The fleet's public, non-secret identifiers, read from config/fleet-ids.json (#4165).

    import fleet_ids
    fleet_ids.get("cerberus_app_id")        # the Cerberus App ID, as a string

A program reads an identifier here instead of hard-coding it or prompting the
operator for it. On 2026-09-27 `tools/cerberus_worker_key.py` asked him for the
Cerberus App ID, which `tools/deploy_cerberus_secrets.py` already held.

The file is generated from the operator's private registry. Change a value there and
regenerate; never edit the file here. Standard library only.
"""

from __future__ import annotations

import json
from pathlib import Path

REGISTRY = Path(__file__).resolve().parents[1] / "config" / "fleet-ids.json"


def load(path: Path = REGISTRY) -> dict[str, dict]:
    """Every entry, by key: {"value", "what"}."""
    return json.loads(path.read_text(encoding="utf-8"))["ids"]


def get(key: str, path: Path = REGISTRY) -> str:
    """One identifier's value. An unknown key raises, naming every key there is."""
    ids = load(path)
    if key not in ids:
        raise KeyError(f"no fleet id {key!r}; known: {', '.join(sorted(ids))}")
    return str(ids[key]["value"])
