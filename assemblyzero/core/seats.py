"""Seats and model profiles: which model every decision in every node goes to (#3563).

A *seat* is a named place in a workflow where a model is asked something. The
registry below is the closed list; nothing outside it can be named in a
profile, and every model-calling site on a workflow path resolves its model
through :func:`resolve` (or :func:`resolve_active` where no run state reaches
the call) instead of carrying a spec of its own.

A *profile* is a TOML file that maps seats to a provider spec and an effort:

    name = "gemini"
    [defaults]
    spec = "gemini:3.1-pro"
    effort = "max"
    [seats."impl.code.small"]
    spec = "gemini:3.1-pro-low"

Built-in profiles live in ``assemblyzero/profiles/``. The one a run uses is
chosen once, at run start, by this precedence (umbrella #3562):

1. ``--models <name-or-path>`` on the entry point;
2. ``AZ_MODEL_PROFILE`` in the environment;
3. ``<target>/.assemblyzero/models.toml``;
4. the built-in ``gemini.toml`` (ADR 0234: Gemini in agy drafts and validates).

``--mock`` selects the built-in ``mock.toml`` over all four, because a mock run
must never reach a real transport. Per-seat overrides (``--seat name=spec``,
and the old ``--drafter`` / ``--reviewer`` flags mapped onto it) and an
``--effort`` flag apply on top of whichever file won.

The loaded profile is a plain dict and is snapshotted into run state as
``state["model_profile"]``, so a checkpoint carries it and a resumed run reads
the snapshot, never the file.
"""

from __future__ import annotations

import contextlib
import contextvars
import copy
import hashlib
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Mapping

#: The closed registry: dotted seat name -> the site it serves.
SEATS: dict[str, str] = {
    "requirements.analyze": "N0c requirements-ambiguity analysis (analyze_requirements.py)",
    "requirements.analyze.escalation": "N0c's one retry after a timeout (analyze_requirements.py)",
    "requirements.draft": "N1 issue and LLD drafter (generate_draft.py)",
    "requirements.review": "N3 issue and LLD reviewer (review.py)",
    "requirements.contract_fidelity": "the roll's contract-fidelity preflight (contract_fidelity.py)",
    "spec.draft": "N2 implementation-spec drafter (generate_spec.py)",
    "spec.review": "N5 implementation-spec reviewer (review_spec.py)",
    "impl.test_plan.review": "N1 test-plan reviewer (review_test_plan.py)",
    "impl.test_plan.revise": "N1_5 test-plan revisor (revise_test_plan.py)",
    "impl.code": "N4 coder (implementation/claude_client.py via routing.py)",
    "impl.code.small": "N4 coder for scaffolds, __init__.py, conftest.py and files under fifty lines (routing.py)",
    "impl.augment_tests": "N4c test augmentation (augment_tests.py)",
    "impl.adversarial": "N7.5 adversarial test writer (adversarial_gemini.py)",
    "orchestrator.triage_summary": "the orchestrator's brief summary (orchestrator/stages.py)",
    "visual_gate.translate": "the visual gate's Modify translation (visual_gate/modify.py)",
    "scout.analyze": "the scout workflow's gap analysis (scout/nodes.py)",
    "tools.audit_deferred_scope": "tools/audit_deferred_scope.py's classifier",
}

#: Which legacy state key each seat answered to before profiles existed. The
#: loader writes ``config_drafter`` / ``config_reviewer`` from these for one
#: release (#3563 requirement 5), and :func:`_legacy_profile` reads them back
#: for callers that still build state by hand.
LEGACY_DRAFTER_SEATS = (
    "requirements.analyze",
    "requirements.draft",
    "spec.draft",
    "impl.test_plan.revise",
)
LEGACY_REVIEWER_SEATS = (
    "requirements.review",
    "spec.review",
    "impl.test_plan.review",
)

PROFILES_DIR = Path(__file__).resolve().parent.parent / "profiles"
DEFAULT_PROFILE = "gemini"
MOCK_PROFILE = "mock"
ENV_VAR = "AZ_MODEL_PROFILE"
TARGET_PROFILE = Path(".assemblyzero") / "models.toml"

_TOP_KEYS = frozenset({"name", "description", "defaults", "seats"})
_SEAT_KEYS = frozenset({"spec", "effort"})


class ProfileError(ValueError):
    """A profile that cannot be used. Fails closed, naming what is wrong."""


@dataclass(frozen=True)
class Seat:
    """One seat, resolved under one profile."""

    name: str
    spec: str
    effort: str | None
    resolved_model_id: str
    provider: str  # the LLMProvider class name ``get_provider`` builds
    profile: str

    def build(self):
        """The transport for this seat, through the one choke point."""
        from assemblyzero.core.llm_provider import get_provider

        return get_provider(self.spec, effort=self.effort)


# ---------------------------------------------------------------------------
# Spec checks
# ---------------------------------------------------------------------------


def _provider_class(provider: str) -> str:
    return {
        "claude": "ClaudeCLIProvider",
        "anthropic": "AnthropicProvider",
        "gemini": "GeminiProvider",
        "mock": "MockProvider",
        "scripted": "ScriptedProvider",
    }.get(provider, provider)


def check_spec(spec: str, where: str) -> tuple[str, str, str]:
    """``(provider, resolved model id, provider class)`` for a spec, or ProfileError.

    ``where`` names the seat (or flag) in every message, so a bad profile says
    which line to fix.

    Fails closed on the two things #3563 requirement 2 names: a spec that does
    not parse under ``parse_provider_spec``, and a model ``FORBIDDEN_MODELS``
    fences. A provider or alias this module does not know is NOT refused here:
    ``get_provider`` is the authority on what it can build and refuses it when
    the seat is used, with its own message. The resolved id is the provider's
    map entry when there is one, else the model as written.
    """
    from assemblyzero.core.config import FORBIDDEN_MODELS
    from assemblyzero.core.llm_provider import (
        AnthropicProvider,
        ClaudeCLIProvider,
        GeminiProvider,
        parse_provider_spec,
    )

    if not isinstance(spec, str) or not spec.strip():
        raise ProfileError(f"{where}: spec is empty")
    try:
        provider, model = parse_provider_spec(spec.strip())
    except ValueError as e:
        raise ProfileError(f"{where}: {e}") from e

    lowered = model.strip().lower()
    if provider == "gemini":
        resolved = getattr(GeminiProvider, "MODEL_MAP", {}).get(lowered)
        if resolved is None:
            # Checked against the fence in its full form, so `gemini:3-pro`
            # is caught as `gemini-3-pro`.
            resolved = lowered if lowered.startswith("gemini-") else f"gemini-{lowered}"
    elif provider == "claude":
        resolved = getattr(ClaudeCLIProvider, "MODEL_MAP", {}).get(lowered, lowered)
    elif provider == "anthropic":
        resolved = getattr(AnthropicProvider, "MODEL_MAP", {}).get(lowered, lowered)
    else:
        resolved = model.strip()

    # Exact match, then family: FORBIDDEN_MODELS carries specific ids and
    # family names, and a family entry is only meaningful as a substring
    # (the rule resolve_adversarial_model applies, now applied to every seat).
    for forbidden in FORBIDDEN_MODELS:
        entry = forbidden.lower()
        if resolved.lower() == entry or entry in resolved.lower():
            raise ProfileError(
                f"{where}: {spec!r} resolves to {resolved!r}, which is forbidden "
                f"by FORBIDDEN_MODELS entry {forbidden!r}"
            )
    return provider, resolved, _provider_class(provider)


def _check_effort(effort: Any, where: str) -> str | None:
    if effort is None:
        return None
    if not isinstance(effort, str) or not effort.strip():
        raise ProfileError(f"{where}: effort must be a non-empty string")
    return effort.strip()


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def builtin_profiles() -> list[str]:
    """Names of the built-in profiles, sorted."""
    return sorted(p.stem for p in PROFILES_DIR.glob("*.toml"))


def builtin_path(name: str) -> Path:
    path = PROFILES_DIR / f"{name}.toml"
    if not path.is_file():
        raise ProfileError(
            f"no built-in profile named {name!r}. Built-in: {', '.join(builtin_profiles())}"
        )
    return path


def _named_or_path(value: str, how: str) -> Path:
    """A name resolves against the built-in directory; a path is read as given."""
    text = value.strip()
    if not text:
        raise ProfileError(f"{how}: empty profile name")
    if text.endswith(".toml") or "/" in text or "\\" in text:
        path = Path(text)
        if not path.is_file():
            raise ProfileError(f"{how}: profile file {text!r} does not exist")
        return path
    return builtin_path(text)


def parse_profile(text: str, source: str) -> dict:
    """Validate a profile's TOML text and return its snapshot dict."""
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise ProfileError(f"{source}: not valid TOML: {e}") from e

    unknown = set(data) - _TOP_KEYS
    if unknown:
        raise ProfileError(f"{source}: unknown top-level key(s) {sorted(unknown)}")
    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ProfileError(f"{source}: profile has no name")

    defaults = data.get("defaults", {})
    if not isinstance(defaults, dict) or set(defaults) - _SEAT_KEYS:
        raise ProfileError(f"{source}: [defaults] may carry only spec and effort")
    default_spec = defaults.get("spec")
    if default_spec is not None:
        check_spec(default_spec, f"{source} [defaults]")
    default_effort = _check_effort(defaults.get("effort"), f"{source} [defaults]")

    seats: dict[str, dict] = {}
    for seat_name, entry in (data.get("seats") or {}).items():
        where = f"{source} seat {seat_name!r}"
        if seat_name not in SEATS:
            raise ProfileError(
                f"{where}: not a seat in the registry. Seats: {', '.join(SEATS)}"
            )
        if not isinstance(entry, dict) or set(entry) - _SEAT_KEYS:
            raise ProfileError(f"{where}: may carry only spec and effort")
        if "spec" in entry:
            check_spec(entry["spec"], where)
        seats[seat_name] = {
            key: (entry[key].strip() if isinstance(entry[key], str) else entry[key])
            for key in entry
        }
        if "effort" in entry:
            _check_effort(entry["effort"], where)

    missing = [s for s in SEATS if "spec" not in seats.get(s, {})] if default_spec is None else []
    if missing:
        raise ProfileError(
            f"{source}: no [defaults] spec, and these seats name none: {', '.join(missing)}"
        )

    return {
        "name": name.strip(),
        "source": source,
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "defaults": {"spec": default_spec, "effort": default_effort},
        "seats": seats,
        "overrides": {},
        "selected_by": "",
    }


def load_profile(path: Path | str) -> dict:
    """Read and validate one profile file."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        raise ProfileError(f"cannot read profile {path}: {e}") from e
    return parse_profile(text, str(path))


def select_profile_path(
    models: str | None = None,
    target_repo: Path | str | None = None,
    environ: Mapping[str, str] | None = None,
) -> tuple[str, Path]:
    """``(how it was chosen, path)`` by the precedence in the module docstring."""
    env = os.environ if environ is None else environ
    if models:
        return "flag", _named_or_path(models, "--models")
    if env.get(ENV_VAR, "").strip():
        return "env", _named_or_path(env[ENV_VAR], ENV_VAR)
    if target_repo:
        candidate = Path(target_repo) / TARGET_PROFILE
        if candidate.is_file():
            return "target", candidate
    return "builtin", builtin_path(DEFAULT_PROFILE)


def parse_seat_overrides(values: list[str] | None) -> dict[str, str]:
    """``["impl.code=claude:opus", ...]`` -> ``{"impl.code": "claude:opus"}``."""
    out: dict[str, str] = {}
    for raw in values or []:
        if "=" not in raw:
            raise ProfileError(f"--seat {raw!r}: expected <seat>=<provider:model>")
        seat_name, spec = (part.strip() for part in raw.split("=", 1))
        out[seat_name] = spec
    return out


def apply_overrides(
    profile: dict,
    overrides: Mapping[str, str] | None = None,
    effort: str | None = None,
) -> dict:
    """A copy of ``profile`` with per-seat spec overrides and an effort override."""
    result = copy.deepcopy(profile)
    for seat_name, spec in (overrides or {}).items():
        where = f"override for seat {seat_name!r}"
        if seat_name not in SEATS:
            raise ProfileError(f"{where}: not a seat in the registry. Seats: {', '.join(SEATS)}")
        check_spec(spec, where)
        result["seats"].setdefault(seat_name, {})["spec"] = spec
        result["overrides"][seat_name] = spec
    effort = _check_effort(effort, "--effort")
    if effort:
        result["defaults"]["effort"] = effort
        for entry in result["seats"].values():
            entry["effort"] = effort
        result["overrides"]["effort"] = effort
    return result


def load_run_profile(
    models: str | None = None,
    target_repo: Path | str | None = None,
    *,
    mock: bool = False,
    overrides: Mapping[str, str] | None = None,
    effort: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict:
    """The profile a run starts with, ready to snapshot into ``state["model_profile"]``."""
    if mock:
        how, path = "mock", builtin_path(MOCK_PROFILE)
    else:
        how, path = select_profile_path(models, target_repo, environ)
    profile = load_profile(path)
    profile["selected_by"] = how
    return apply_overrides(profile, overrides, effort)


def add_profile_arguments(parser) -> None:
    """``--models`` and ``--seat`` on an entry point's argparse parser."""
    parser.add_argument(
        "--models",
        default=None,
        metavar="NAME_OR_PATH",
        help=(
            "Model profile for every seat: a built-in name "
            f"({', '.join(builtin_profiles())}) or a TOML path. Default: "
            f"${ENV_VAR}, else <target>/{TARGET_PROFILE.as_posix()}, else "
            f"the built-in {DEFAULT_PROFILE!r} (#3562)."
        ),
    )
    parser.add_argument(
        "--seat",
        action="append",
        default=[],
        metavar="SEAT=SPEC",
        help="Override one seat's provider spec, e.g. impl.code=claude:sonnet (repeatable).",
    )


def _is_offline_spec(spec: str) -> bool:
    return spec.strip().lower().startswith(("mock:", "scripted:"))


def profile_from_args(
    args,
    target_repo: Path | str | None,
    legacy: Mapping[str, tuple[str, ...]] | None = None,
    *,
    mock_overrides: Mapping[str, str] | None = None,
) -> dict:
    """The run profile an entry point's parsed arguments select.

    ``legacy`` maps an old flag's attribute name (``drafter``, ``reviewer``)
    to the seats it now overrides; ``--seat`` wins over a legacy flag for the
    same seat. Under ``--mock`` only ``mock:``/``scripted:`` overrides apply,
    because a mock run must never reach a real transport; any other is named
    and dropped. ``mock_overrides`` are the entry point's own mock choices
    (the issue workflow's ``mock:draft``).
    """
    overrides = parse_seat_overrides(_seat_arg(args))
    for attr, seat_names in (legacy or {}).items():
        value = _str_arg(args, attr)
        if value:
            for seat_name in seat_names:
                overrides.setdefault(seat_name, value)
    mock = getattr(args, "mock", False) is True
    if mock:
        for seat_name, spec in list(overrides.items()):
            if not _is_offline_spec(spec):
                print(f"[models] --mock: ignoring {seat_name}={spec}; a mock run stays offline")
                del overrides[seat_name]
        for seat_name, spec in (mock_overrides or {}).items():
            overrides.setdefault(seat_name, spec)
    return load_run_profile(
        _str_arg(args, "models"),
        target_repo,
        mock=mock,
        overrides=overrides,
        effort=_str_arg(args, "effort"),
    )


def _str_arg(args, name: str) -> str | None:
    """An argparse attribute when it is a non-empty string, else None.

    Callers sometimes hand a ``Mock`` for ``args``; an attribute they did not
    set is then a Mock, which must read as "not given", never as a value.
    """
    value = getattr(args, name, None)
    return value if isinstance(value, str) and value.strip() else None


def _seat_arg(args) -> list[str]:
    value = getattr(args, "seat", None)
    return [v for v in value if isinstance(v, str)] if isinstance(value, list) else []


def default_profile() -> dict:
    """The built-in default, loaded fresh."""
    profile = load_profile(builtin_path(DEFAULT_PROFILE))
    profile["selected_by"] = "builtin"
    return profile


def default_spec(seat_name: str) -> str:
    """The built-in default profile's spec for one seat.

    For library signatures that take a spec and need a default: they read it
    here rather than restating it, so the profile stays the one source.
    """
    return seat_in(default_profile(), seat_name).spec


# ---------------------------------------------------------------------------
# Resolving
# ---------------------------------------------------------------------------


def seat_in(profile: dict, seat_name: str) -> Seat:
    """Resolve one seat under one profile."""
    if seat_name not in SEATS:
        raise ProfileError(f"{seat_name!r} is not a seat in the registry")
    entry = profile.get("seats", {}).get(seat_name, {})
    defaults = profile.get("defaults", {})
    spec = entry.get("spec") or defaults.get("spec")
    effort = entry.get("effort", defaults.get("effort"))
    where = f"profile {profile.get('name')!r} seat {seat_name!r}"
    _, resolved, provider_class = check_spec(spec, where)
    return Seat(
        name=seat_name,
        spec=spec,
        effort=effort,
        resolved_model_id=resolved,
        provider=provider_class,
        profile=str(profile.get("name", "")),
    )


def seat_table(profile: dict) -> dict[str, Seat]:
    """Every registry seat, resolved under ``profile``, in registry order."""
    return {name: seat_in(profile, name) for name in SEATS}


def legacy_keys(profile: dict) -> dict[str, str]:
    """``config_drafter`` / ``config_reviewer`` / ``config_effort`` for one release.

    Written by the entry points beside ``model_profile`` so a caller that has
    not moved to :func:`resolve` keeps working (#3563 requirement 5). Nothing
    on a workflow path reads them any more.
    """
    drafter = seat_in(profile, "requirements.draft")
    reviewer = seat_in(profile, "requirements.review")
    return {
        "config_drafter": drafter.spec,
        "config_reviewer": reviewer.spec,
        "config_effort": reviewer.effort or "",
    }


def _legacy_profile(state: Mapping[str, Any]) -> dict:
    """The profile a hand-built state implies, for callers not yet on profiles.

    One release of compatibility, in one place (#3563 requirement 5). Before
    profiles each node chose its own spec: the legacy keys where set, a mock
    spec in mock mode, ``gemini:3.1-pro`` otherwise. This reproduces those
    choices so a test or tool that builds state without ``model_profile``
    behaves as it did, and so the nodes themselves carry no such branches.
    """
    mock = bool(state.get("config_mock_mode") or state.get("mock_mode"))
    profile = load_profile(builtin_path(MOCK_PROFILE if mock else DEFAULT_PROFILE))
    profile["selected_by"] = "legacy-state"
    drafter = str(state.get("config_drafter") or "").strip()
    reviewer = str(state.get("config_reviewer") or "").strip()
    effort = str(state.get("config_effort") or "").strip() or None
    overrides: dict[str, str] = {}
    if mock:
        # The old mock branches: an LLD drafts from mock:lld, an issue from
        # mock:draft (#3533), and only an explicitly mock drafter was honoured.
        if drafter.startswith("mock:"):
            overrides["requirements.draft"] = drafter
        elif state.get("workflow_type") == "issue":
            overrides["requirements.draft"] = "mock:draft"
    else:
        if drafter:
            for seat_name in LEGACY_DRAFTER_SEATS:
                overrides[seat_name] = drafter
            from assemblyzero.workflows.requirements.nodes.analyze_requirements import (
                escalated_drafter,
            )

            overrides["requirements.analyze.escalation"] = escalated_drafter(drafter) or drafter
        if reviewer:
            for seat_name in LEGACY_REVIEWER_SEATS:
                overrides[seat_name] = reviewer
    return apply_overrides(profile, overrides, effort)


def profile_of(state: Mapping[str, Any]) -> dict:
    """The run's profile: the snapshot when there is one, else what the state implies."""
    snapshot = state.get("model_profile") if hasattr(state, "get") else None
    if isinstance(snapshot, dict) and snapshot.get("seats") is not None:
        return snapshot
    return _legacy_profile(state)


def resolve(state: Mapping[str, Any], seat_name: str) -> Seat:
    """The seat ``seat_name`` under the run's profile."""
    return _remember(seat_in(profile_of(state), seat_name))


# ---------------------------------------------------------------------------
# The active profile, for calls no run state reaches
# ---------------------------------------------------------------------------

_ACTIVE: contextvars.ContextVar[dict | None] = contextvars.ContextVar(
    "assemblyzero_model_profile", default=None
)


@contextlib.contextmanager
def using_profile(profile: dict) -> Iterator[dict]:
    """Make ``profile`` the one :func:`resolve_active` answers from, for a block.

    The coder's helpers (N4, N4c) are ten calls deep from the node that holds
    the state; the node enters this once instead of threading the profile
    through every signature.
    """
    token = _ACTIVE.set(profile)
    try:
        yield profile
    finally:
        _ACTIVE.reset(token)


def active_profile() -> dict:
    """The profile set by :func:`using_profile`, else the run's profile set by
    :func:`set_run_profile`, else the run-start precedence applied to the
    current environment (flag excepted: there is none here)."""
    current = _ACTIVE.get()
    if current is not None:
        return current
    if _RUN_PROFILE is not None:
        return _RUN_PROFILE
    how, path = select_profile_path(None, None)
    profile = load_profile(path)
    profile["selected_by"] = how
    return profile


def resolve_active(seat_name: str) -> Seat:
    """The seat under the active profile."""
    return _remember(seat_in(active_profile(), seat_name))


# ---------------------------------------------------------------------------
# The run's profile and the last seat resolved, for the per-call record (#3565)
# ---------------------------------------------------------------------------

_RUN_PROFILE: dict | None = None

_LAST_SEAT: contextvars.ContextVar[Seat | None] = contextvars.ContextVar(
    "assemblyzero_last_seat", default=None
)


def set_run_profile(profile: dict | None) -> None:
    """Record the profile this process's run started with.

    Entry points call it once, after loading. :func:`active_profile` falls
    back to it, so seats no state reaches (the triage summary, the visual
    gate, contract fidelity) follow the run's ``--models`` choice, and the
    telemetry writers read its name.
    """
    global _RUN_PROFILE
    _RUN_PROFILE = profile


def current_profile_name() -> str:
    """The run's profile name, for telemetry rows: never empty."""
    try:
        return str(active_profile().get("name", "")) or DEFAULT_PROFILE
    except Exception:  # noqa: BLE001 - a telemetry row never costs a run
        # fail-open: a profile that cannot be read here was already reported
        # at run start; the row still says which default applies.
        return DEFAULT_PROFILE


def _remember(seat: Seat) -> Seat:
    _LAST_SEAT.set(seat)
    return seat


def last_resolved_seat(spec: str) -> str:
    """The name of the seat resolved last, when it resolved to ``spec``.

    A node resolves its seat and then builds the provider from the seat's
    spec, so the two meet here. When the spec differs (an explicit override
    passed straight to ``get_provider``), the call is recorded with no seat
    rather than a wrong one.
    """
    seat = _LAST_SEAT.get()
    if seat is None or seat.spec.strip().lower() != (spec or "").strip().lower():
        return ""
    return seat.name


def describe(profile: dict) -> str:
    """One block of text naming the profile and every seat, for run logs."""
    lines = [
        f"[models] profile {profile.get('name')} ({profile.get('selected_by') or 'given'}; "
        f"{profile.get('source')}; sha256 {str(profile.get('sha256', ''))[:12]})"
    ]
    for name, seat in seat_table(profile).items():
        effort = f" effort={seat.effort}" if seat.effort else ""
        lines.append(f"[models]   {name:<34} {seat.spec}{effort}")
    return "\n".join(lines)
