"""Can pinning read this complaint? (#2557, swept as a class under #2576.)

The 2026-08-27 deadlock had two required halves: a completeness failure
whose message addressed its target in a scheme pinning could not read, and
pinning enforcing anyway because the message happened to mint garbage
tokens. The repaired invariant — *a change a completeness failure demands
is never revertible by pinning in the same round* — holds mechanically only
for complaints pinning can actually READ.

So the property is not "is this message well written" but a mechanical
question with a yes or no answer:

    Does ``named_tokens(message) | named_line_ranges(message)`` address at
    least one line of the draft the message is complaining about?

If yes, the drafter's mandated edit lands in a region the enforcement will
unlock. If no, the drafter makes the demanded change and pinning reverts
it as touching unnamed content — the loop then burns its cap producing
byte-identical drafts, which is exactly what #2555 measured.

This module is the classifier. It owns no policy: it reports what the
pinning vocabulary sees, and the caller decides. `tests/unit/
test_completeness_message_addressability.py` drives every real check with a
fixture that fails it and asserts on the REAL emitted message, so a future
rewording that drops the address fails the suite the day it is written.

Registry class: **the demanded change is never refusable** — see
`docs/standards/0029-defect-class-registry.md`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from assemblyzero.workflows.implementation_spec.revision_pinning import (
    demands_additions,
    named_line_ranges,
    named_tokens,
)

#: The three ways a complaint can stand with respect to enforcement. The
#: taxonomy is three-way, not two, and the middle one is why: a complaint
#: that demands NEW content has no line to cite by construction, so failing
#: to address the draft is correct for it rather than a defect. #2560 added
#: the exemption that carries those.
ADDRESSED = "addressed"
DEMANDS_ADDITION = "demands-addition"
UNADDRESSABLE = "unaddressable"

#: A token this short matches half the draft by accident. `named_tokens`
#: already drops anything under three characters; this is the second bound,
#: applied to the MATCH rather than the token, because a one-word token like
#: "the" would otherwise "address" every line and report a false pass.
MIN_MATCH_CHARS = 4


@dataclass
class Addressability:
    """What the pinning vocabulary sees in one message."""

    addressed: bool
    tokens: tuple[str, ...] = ()
    ranges: tuple[tuple[int, int], ...] = ()
    #: 1-based draft lines the message reaches, in order.
    matched_lines: tuple[int, ...] = ()
    #: Ranges the message cites that fall outside the draft entirely. These
    #: are worse than no citation: they read as an address and unlock
    #: nothing, so they are reported separately rather than folded into
    #: `addressed`.
    out_of_bounds: tuple[tuple[int, int], ...] = ()
    via: tuple[str, ...] = field(default_factory=tuple)
    #: True when the message trips `demands_additions` -- the #2560 exemption
    #: that frees a locked region introducing new content.
    demands_addition: bool = False

    @property
    def verdict(self) -> str:
        """ADDRESSED, DEMANDS_ADDITION, or UNADDRESSABLE.

        Order matters. A complaint that both addresses the draft and demands
        an addition is ADDRESSED: it has a citable line, which is the
        stronger guarantee, and the addition exemption is a fallback rather
        than an equal alternative.
        """
        if self.addressed:
            return ADDRESSED
        if self.demands_addition:
            return DEMANDS_ADDITION
        return UNADDRESSABLE

    def summary(self) -> str:
        if self.addressed:
            return (
                f"addressed via {', '.join(self.via)}; reaches "
                f"{len(self.matched_lines)} draft line(s)"
            )
        if self.demands_addition:
            return (
                "demands an addition: no line to cite by construction, and "
                "the #2560 exemption carries it"
            )
        if self.out_of_bounds:
            return (
                f"NOT addressed: cites {self.out_of_bounds} which falls "
                f"outside the draft"
            )
        if self.tokens:
            return (
                f"NOT addressed: {len(self.tokens)} token(s) parsed but none "
                f"appears in the draft"
            )
        return "NOT addressed: the pinning vocabulary parses nothing at all"


def addresses_draft(message: str, draft: str) -> Addressability:
    """Does this complaint name at least one line of the draft it describes?

    Both halves of the vocabulary are consulted, because they fail in
    different directions. A token addresses the draft when it actually
    OCCURS in it -- a backticked span naming something the draft does not
    contain parses fine and unlocks nothing. A line range addresses the
    draft when it falls inside it -- #2555's fence complaint carried
    ``line 1`` from a quoted SyntaxError, a position inside a snippet
    rather than a draft address, which is why `named_line_ranges` requires
    the dash and why an out-of-bounds range is reported, not counted.
    """
    lines = (draft or "").splitlines()
    total = len(lines)

    tokens = tuple(sorted(named_tokens("", [message or ""])))
    ranges = named_line_ranges([message or ""])

    matched: set[int] = set()
    via: list[str] = []

    lowered = [line.lower() for line in lines]
    token_hit = False
    for token in tokens:
        if len(token) < MIN_MATCH_CHARS:
            continue
        for index, line in enumerate(lowered, start=1):
            if token in line:
                matched.add(index)
                token_hit = True
    if token_hit:
        via.append("named_tokens")

    out_of_bounds: list[tuple[int, int]] = []
    range_hit = False
    for start, end in ranges:
        if start > total:
            out_of_bounds.append((start, end))
            continue
        for line_no in range(start, min(end, total) + 1):
            matched.add(line_no)
            range_hit = True
    if range_hit:
        via.append("named_line_ranges")

    return Addressability(
        addressed=bool(matched),
        tokens=tokens,
        ranges=ranges,
        matched_lines=tuple(sorted(matched)),
        out_of_bounds=tuple(out_of_bounds),
        via=tuple(via),
        demands_addition=demands_additions([message or ""]),
    )
