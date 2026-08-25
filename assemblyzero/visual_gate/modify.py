"""The Modify verb's model pass (#2518): words in, contract deltas out.

Free text like "the red bar should be thinner" contains no number. The model
pass translates each feedback item into a concrete contract delta against the
manifest's own keys, and the loop is iterative -- render, look, modify --
until Approve. The design's worked example (the operator's actual five-part
2026-08-25 message) is the acceptance scenario and the test fixture.

Two guardrails run HERE, after decomposition and before any render:

* a colour delta is checked against the contract's separation floor by
  computation (floor.floor_violations), never by eyeball;
* a delta that would change a value a landed ruling pinned halts for the
  operator instead of silently overriding the ruling.

The transport is injectable. The default is the fleet's governance transport
(GeminiClient, ADR 0220); tests inject fakes and exercise this module's own
logic -- prompt construction, parsing, guardrails -- which is the part that
is ours to break.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from assemblyzero.visual_gate.floor import floor_violations

#: What a decomposed item can be. Mirrors the design comment's table.
KINDS = (
    "approve-element",   # pin these values; exclude from further deltas
    "modify-geometry",   # concrete numeric delta on a manifest key
    "modify-colour",     # RGB delta, or candidates when the ask is adjectival
    "contract-gap",      # the contract does not specify this; file/extend
    "reject-note",       # a complaint with no actionable delta
)

_SYSTEM = """You translate an operator's visual feedback into concrete deltas
against a numeric render contract. You answer ONLY with a JSON array. Each
element is an object:
  {"kind": one of %s,
   "key": a contract key from the manifest, or null,
   "value": the new value (number, or [r,g,b]), or null,
   "candidates": optional list of [r,g,b] when the colour ask is adjectival
                 and has no unique answer,
   "note": one sentence quoting or restating the operator's words}
Rules: never invent a contract key -- if the feedback names something the
manifest has no key for, that is a contract-gap. An adjectival colour ask
("more like a tachometer red") gets candidates, not a single guess. A pure
compliment is approve-element for the element's keys.""" % (KINDS,)


@dataclass(frozen=True)
class FeedbackItem:
    kind: str
    key: str | None
    value: object
    candidates: tuple = ()
    note: str = ""


@dataclass
class ModifyPlan:
    """What one Modify round decided, after guardrails."""

    deltas: dict = field(default_factory=dict)        # key -> value
    candidate_sets: dict = field(default_factory=dict)  # key -> [rgb, ...]
    pinned: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    floor_refusals: list[str] = field(default_factory=list)
    ruling_conflicts: list[str] = field(default_factory=list)

    @property
    def halted_on_ruling(self) -> bool:
        return bool(self.ruling_conflicts)


def build_prompt(text: str, manifest: dict) -> tuple[str, str]:
    """(system, content) for the transport."""
    values = manifest.get("values", {})
    lines = [
        f"  {key}: {entry.get('value')!r}"
        + (" [RULED -- pinned by a landed ruling]" if entry.get("ruled") else "")
        for key, entry in sorted(values.items())
    ]
    content = (
        "Contract manifest keys and current values:\n"
        + "\n".join(lines)
        + "\n\nPalette entries (name: [r,g,b]):\n"
        + "\n".join(
            f"  {name}: {list(rgb)}"
            for name, rgb in sorted(manifest.get("palette", {}).items())
        )
        + f"\n\nOperator feedback, verbatim:\n{text}\n"
    )
    return _SYSTEM, content


def parse_items(raw: str) -> list[FeedbackItem]:
    """The model's array, validated. Raises on garbage -- a Modify built on
    an unparsed answer would render nobody's intent."""
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        raise ValueError(f"no JSON array in model output: {raw[:200]!r}")
    items = []
    for entry in json.loads(match.group(0)):
        kind = entry.get("kind")
        if kind not in KINDS:
            raise ValueError(f"unknown item kind: {kind!r}")
        items.append(FeedbackItem(
            kind=kind,
            key=entry.get("key"),
            value=entry.get("value"),
            candidates=tuple(tuple(c) for c in entry.get("candidates") or ()),
            note=str(entry.get("note", "")),
        ))
    return items


def decompose(text: str, manifest: dict, transport) -> list[FeedbackItem]:
    """One model pass: operator words -> validated items."""
    system, content = build_prompt(text, manifest)
    return parse_items(transport(system, content))


#: Provider spec for the translation pass: top-tier Gemini through the
#: provider LAYER, which pairs the model id with its transport. The first
#: live Modify (#2521, run-issue331-172000) constructed GeminiClient bare,
#: whose default model is core.config.REVIEWER_MODEL -- a Claude id -- and
#: the Gemini validator rejected it before any call was made. get_provider
#: is the house pattern every workflow node routes through; the spec is the
#: reviewer default the spec stage already uses (AZ #1434).
TRANSLATION_PROVIDER = "gemini:3.1-pro"


def default_transport(system: str, content: str) -> str:
    """The fleet's provider layer (ADR 0220 / #2521). Imported lazily so the
    gate's non-Modify paths never touch credentials."""
    from assemblyzero.core.llm_provider import get_provider

    result = get_provider(TRANSLATION_PROVIDER).invoke(system, content)
    response = (getattr(result, "response", None) or "").strip()
    if not getattr(result, "success", False) or not response:
        raise RuntimeError(
            f"visual-gate Modify translation failed via "
            f"{TRANSLATION_PROVIDER}: "
            f"{getattr(result, 'error_message', '') or 'empty response'}"
        )
    return response


def plan_from_items(
    items: list[FeedbackItem], manifest: dict, *,
    separation_floor: float, ruled: dict,
) -> ModifyPlan:
    """Guardrails, by computation, before any render.

    Ruling conflicts collect rather than short-circuit so the halt names
    EVERY contradicted ruling in one message -- the operator rules once, not
    once per relaunch.
    """
    plan = ModifyPlan()
    values = manifest.get("values", {})
    palette = manifest.get("palette", {})

    def _ruled_value(key: str):
        if key in ruled:
            return ruled[key]
        entry = values.get(key) or {}
        return entry.get("value") if entry.get("ruled") else None

    for item in items:
        if item.kind == "approve-element":
            if item.key:
                plan.pinned.append(item.key)
            continue
        if item.kind == "contract-gap":
            plan.gaps.append(item.note or (item.key or "unnamed gap"))
            continue
        if item.kind == "reject-note":
            plan.gaps.append(f"(reject-note) {item.note}")
            continue
        if not item.key:
            plan.gaps.append(f"(no key resolved) {item.note}")
            continue
        if item.key in plan.pinned:
            continue

        pinned_value = _ruled_value(item.key)
        proposed = item.value if item.value is not None else (
            list(item.candidates[0]) if item.candidates else None
        )
        if pinned_value is not None and proposed != pinned_value:
            plan.ruling_conflicts.append(
                f"'{item.key}' is pinned by a landed ruling at {pinned_value!r}; "
                f"the feedback asks for {proposed!r} ({item.note}). An operator "
                f"ruling, not a gate delta, changes it."
            )
            continue

        if item.kind == "modify-colour":
            candidates = item.candidates or (
                (tuple(item.value),) if item.value else ()
            )
            cleared = []
            for rgb in candidates:
                findings = floor_violations(
                    rgb, palette, separation_floor, replacing=item.key,
                )
                if findings:
                    plan.floor_refusals.extend(findings)
                else:
                    cleared.append(tuple(int(c) for c in rgb))
            if len(cleared) == 1 and item.value is not None:
                plan.deltas[item.key] = list(cleared[0])
            elif cleared:
                plan.candidate_sets[item.key] = [list(c) for c in cleared]
            continue

        # modify-geometry
        plan.deltas[item.key] = item.value

    return plan
