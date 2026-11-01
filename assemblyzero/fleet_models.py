#!/usr/bin/env python3
"""The fleet's one model switch: which model plays each role (#4450).

`config/fleet-models.toml` names, for each role a model plays anywhere in the fleet, the model that
plays it. This module is the only reader of that file. A tool asks for its role and never names a
model or a provider itself:

    model = model_for("judge")
    model.provider, model.id          # "agy", "gemini-3.8-flash-high"

Standard library only, and nothing here imports the rest of the package, so a tool outside this
repository's environment can load this one file by its path. A second repository holds a thin
`fleet_switch.py` that does that, never a copy of this logic or of the table.

A role that cannot be played stops the run. `ModelSwitchError` is built on `SystemExit`, so a tool's
`except Exception` around its model call cannot swallow it, record "unchecked" and carry on. The
message names the role and the model, and nothing falls back to another model.

    python assemblyzero/fleet_models.py --check     every role, exit 1 when one has no live model
    python assemblyzero/fleet_models.py judge       the provider and id of one role
"""

from __future__ import annotations

import argparse
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

FILE = Path(__file__).resolve().parent.parent / "config" / "fleet-models.toml"
LIVE = "live"
STATUSES = frozenset({LIVE, "retired"})
# How a model is reached. A closed list: a new way of reaching a model is added here on purpose.
PROVIDERS = frozenset({"agy", "codex", "claude", "gemini-api"})


class ModelSwitchError(SystemExit):
    """A role cannot be played: the run stops, naming the role and the model."""

    def __init__(self, message: str) -> None:
        super().__init__(f"STOPPED: {message}")


@dataclass(frozen=True)
class Model:
    """The model playing one role."""

    role: str
    name: str
    provider: str
    id: str


def load(path: Path | None = None) -> dict:
    """The parsed file. A file that is missing or unreadable stops the run."""
    source = path or FILE
    try:
        return tomllib.loads(source.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ModelSwitchError(f"the fleet's model switch cannot be read at {source}: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ModelSwitchError(f"the fleet's model switch at {source} is not valid TOML: {exc}") from exc


def forbidden(path: Path | None = None) -> tuple[str, ...]:
    """The ids and families never used, whatever a role says."""
    return tuple((load(path).get("policy") or {}).get("forbidden") or ())


def fault(table: dict, role: str, name: str) -> str | None:
    """Why this model cannot play this role, or None when it can."""
    entry = (table.get("models") or {}).get(name)
    if not isinstance(entry, dict):
        return f"role {role!r} names model {name!r}, which is not under [models]"
    if entry.get("provider") not in PROVIDERS:
        return f"role {role!r}: model {name!r} has provider {entry.get('provider')!r}, not one of {sorted(PROVIDERS)}"
    if entry.get("status") not in STATUSES:
        return f"role {role!r}: model {name!r} has status {entry.get('status')!r}, not one of {sorted(STATUSES)}"
    model_id = str(entry.get("id") or "")
    if not model_id:
        return f"role {role!r}: model {name!r} has no id"
    banned = ((table.get("policy") or {}).get("forbidden") or ())
    for family in banned:
        if family.lower() in model_id.lower():
            return f"role {role!r}: model {name!r} ({model_id}) is forbidden by {family!r}"
    if entry["status"] != LIVE:
        return f"role {role!r}: model {name!r} ({model_id}) is {entry['status']}, and nothing replaces it"
    return None


def names_of(table: dict, role: str) -> tuple[str, ...]:
    """The model names under a role: one for most roles, several for a role like speech."""
    value = (table.get("roles") or {}).get(role)
    if value is None:
        raise ModelSwitchError(f"no role {role!r} in the fleet's model switch")
    return (value,) if isinstance(value, str) else tuple(value)


def models_for(role: str, path: Path | None = None) -> tuple[Model, ...]:
    """Every model playing this role. Any one that cannot play it stops the run."""
    table = load(path)
    found = []
    for name in names_of(table, role):
        problem = fault(table, role, name)
        if problem:
            raise ModelSwitchError(problem)
        entry = table["models"][name]
        found.append(Model(role, name, entry["provider"], entry["id"]))
    return tuple(found)


def model_for(role: str, path: Path | None = None) -> Model:
    """The one model playing this role. A role with several is read with `models_for`."""
    found = models_for(role, path)
    if len(found) != 1:
        raise ModelSwitchError(f"role {role!r} has {len(found)} models, so it is read with models_for")
    return found[0]


def of_provider(provider: str, path: Path | None = None) -> tuple[str, ...]:
    """The ids of every model reached through this provider, live or retired."""
    models = load(path).get("models") or {}
    return tuple(entry["id"] for entry in models.values() if entry.get("provider") == provider)


def problems(path: Path | None = None) -> list[str]:
    """Every role that cannot be played. An empty list means every role has a live model."""
    table = load(path)
    found = []
    for role in table.get("roles") or {}:
        for name in names_of(table, role):
            problem = fault(table, role, name)
            if problem:
                found.append(problem)
    return found


def report(path: Path | None = None) -> list[str]:
    """One line for every role, then a line for every role that cannot be played."""
    table = load(path)
    lines = []
    for role in table.get("roles") or {}:
        for name in names_of(table, role):
            entry = (table.get("models") or {}).get(name) or {}
            lines.append(f"{role:16}{name:22}{entry.get('provider', '?'):12}{entry.get('id', '?')}"
                         f"  {entry.get('status', '?')}")
    return lines + [f"NO LIVE MODEL: {problem}" for problem in problems(path)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("role", nargs="?", help="one role, printed as its provider and id")
    parser.add_argument("--check", action="store_true", help="every role; exit 1 when one has no live model")
    args = parser.parse_args(argv)
    if args.role:
        for model in models_for(args.role):
            print(model.provider, model.id)
        return 0
    print("\n".join(report()))
    return 1 if args.check and problems() else 0


if __name__ == "__main__":
    sys.exit(main())
