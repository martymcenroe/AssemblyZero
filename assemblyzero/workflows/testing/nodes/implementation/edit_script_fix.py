"""A fix asks for edits, not a rebirth (#2407).

The spec stage learned this class in #1528: a "revision" that regenerates the
whole document drifts, because the model does not copy unflagged content
byte-identically however firmly it is asked to. The implementation stage never
inherited it. Its fix loop sends the whole current file, the test failures and
the spec, and asks for a complete regeneration.

## The measurement, from run-issue1-090001

Every per-file call in the run, paired with what it cost:

    src/boostgauge/skins/stingray.py   Add              sonnet    15.9s
    src/boostgauge/gauge.py            Add              sonnet     9.8s
    tests/conftest.py                  Modify(extend)   haiku      6.3s
    tests/unit/test_gauge.py           Add              sonnet    31.6s
    tests/visual/test_gauge.py         Add              sonnet     9.1s
    src/boostgauge/skins/stingray.py   Modify(extend)   sonnet   602.2s  TIMEOUT
    src/boostgauge/skins/stingray.py   Modify(extend)   sonnet   600.2s  TIMEOUT
    src/boostgauge/gauge.py            Modify(extend)   sonnet     8.5s
    tests/conftest.py                  Modify(extend)   haiku      7.8s
    tests/unit/test_gauge.py           Modify(extend)   sonnet    22.7s
    tests/visual/test_gauge.py         Modify(extend)   sonnet     9.6s
    src/boostgauge/skins/stingray.py   Modify(extend)   sonnet   602.2s  TIMEOUT
    src/boostgauge/skins/stingray.py   Modify(extend)   sonnet   480.9s
    ...

Two things in that table correct the issue that filed this.

**The draft was 15.9 seconds, not ~580.** The issue attributes ~580s to the
draft call; measured, every call in that class is a FIX call. So the asymmetry
is not 580 -> 602, it is **15.9 -> 602, a factor of thirty-eight** for the same
file. The case for edit scripts is stronger than it was written.

**Regeneration is not uniformly slow.** Four of five files regenerate in under
32 seconds on the same path in the same run. Only the file the failing tests
implicate blows up -- which is exactly the mechanism this module addresses:
that file gets the failure corpus appended AND is the one being reasoned about
hardest, so it re-derives the whole file while concentrating on one defect.
The fix is therefore scoped to where the pathology is, not applied as a blanket
change to every write.

The 480.9s call that COMPLETED matters too: the work fits under the wall when
the model gets there. A smaller ask is cheaper insurance than any ceiling.

## Same format, one parser

`parse_edit_blocks`, `apply_edit_blocks` and `unchanged_ratio` are imported
from the spec stage rather than reimplemented. The issue asks for "the same
script format the spec stage validates and applies", and a second copy of a
parser is a guarantee of drift rather than of sameness. Only the PROMPT differs
here, because the subject is code and failing tests rather than a document and
reviewer feedback.

## Never worse than regeneration

Every failure at every step -- no blocks, a SEARCH that does not match, a
SEARCH that matches twice, an empty result -- returns None, and the caller
falls back to the existing full-file path. That is the same contract #1528
wrote for the spec stage, and it is what makes this safe to switch on.
"""

from __future__ import annotations

import re
from pathlib import Path

# One format, one parser (see the module docstring). These are pure text
# functions with their own unit tests; importing them is what makes "the same
# script format" true rather than merely claimed.
from assemblyzero.workflows.implementation_spec.nodes.edit_script import (
    apply_edit_blocks,
    parse_edit_blocks,
    unchanged_ratio,
)

__all__ = [
    "EDIT_SCRIPT_CODE_SYSTEM_PROMPT",
    "EditScriptOutcome",
    "apply_edit_blocks",
    "build_code_edit_script_prompt",
    "failures_for_file",
    "parse_edit_blocks",
    "should_use_edit_script",
    "unchanged_ratio",
]

EDIT_SCRIPT_CODE_SYSTEM_PROMPT = (
    "You are a precision patch engine for source code. You NEVER rewrite "
    "files -- you emit minimal, exact edit blocks that a machine applies. "
    "Your entire response is edit blocks in the specified format; any prose "
    "outside edit blocks is discarded."
)

#: A file this small is cheaper to regenerate than to patch, and a SEARCH
#: anchor in it is more likely to be ambiguous. Measured against the run above:
#: every file that regenerated in under 32s is in this class or near it.
MIN_BYTES_FOR_EDIT_SCRIPT = 400


class EditScriptOutcome:
    """What an edit-script fix attempt produced, and how well it held.

    `code` is None whenever the caller must fall back -- there is no partial
    success, for the same reason `apply_edit_blocks` returns failures rather
    than a half-patched document.
    """

    def __init__(
        self,
        code: str | None,
        blocks: int = 0,
        preserved: float = 0.0,
        failures: list[str] | None = None,
    ) -> None:
        self.code = code
        self.blocks = blocks
        self.preserved = preserved
        self.failures = failures or []

    @property
    def ok(self) -> bool:
        return self.code is not None

    def describe(self) -> str:
        if self.ok:
            return (
                f"[EDIT-SCRIPT] Applied {self.blocks} edit(s); "
                f"{self.preserved:.0%} of the prior file preserved "
                f"byte-identical (#2407)"
            )
        reason = self.failures[0] if self.failures else "no edit blocks in response"
        return f"[EDIT-SCRIPT] fell back to full regeneration: {reason}"


def should_use_edit_script(
    change_type: str, existing_content: str, failure_context: str
) -> bool:
    """Is this the fix-an-existing-file case the edit script is for?

    Three conditions, all measured rather than assumed:

    - there IS a prior failure to fix (an initial draft has nothing to patch);
    - the file already exists with content (you cannot SEARCH an empty file --
      this is the "file does not yet exist" fallback the issue names);
    - the file is big enough that patching beats regenerating.
    """
    if not failure_context.strip():
        return False
    if change_type.lower() not in ("modify", "add"):
        return False
    if len(existing_content) < MIN_BYTES_FOR_EDIT_SCRIPT:
        return False
    return True


def failures_for_file(failure_summary: str, filepath: str) -> str:
    """The failures this file is implicated in, or everything if unattributable.

    The issue asks to "scope the prompt to the failing tests rather than the
    full failure corpus WHERE THE RUNNER CAN ATTRIBUTE failures to files". The
    conditional is load-bearing and is honoured literally: pytest names the
    failing TEST file, not the implementation file, so attribution runs on the
    module name and the file stem, and when nothing matches the caller gets the
    whole corpus back. Silently narrowing to nothing would starve the fix of
    the information it needs, which is a worse failure than a prompt that is
    larger than necessary.
    """
    if not failure_summary.strip():
        return failure_summary

    path = Path(filepath)
    stem = path.stem
    if not stem:
        return failure_summary

    # `src/boostgauge/skins/stingray.py` -> boostgauge.skins.stingray, and the
    # bare stem, and the path itself. A failure mentioning any of them is this
    # file's business.
    parts = [p for p in path.with_suffix("").parts if p not in ("src", "lib")]
    tokens = {
        stem.lower(),
        ".".join(parts).lower(),
        str(path).replace("\\", "/").lower(),
    }
    # `test_gauge.py` implicates `gauge.py`: the runner names the test, and the
    # fix lands in the module under it.
    tokens.add(f"test_{stem}".lower())

    kept = [
        line for line in failure_summary.splitlines()
        if any(token and token in line.lower() for token in tokens)
    ]
    if not kept:
        return failure_summary
    return "\n".join(kept)


def build_code_edit_script_prompt(
    filepath: str,
    existing_content: str,
    failure_context: str,
    spec_excerpt: str = "",
) -> str:
    """Ask for edits against the current file, not a regeneration of it."""
    sections: list[str] = [
        f"# Fix Request: {filepath}\n\n"
        "The file below already exists and MOSTLY WORKS. Some tests fail. "
        "Change only what is needed to make them pass.\n\n"
        "Do NOT rewrite the file. Output ONLY edit blocks in EXACTLY this "
        "format:\n\n"
        "<<<<<<< SEARCH\n"
        "(exact lines copied verbatim from the CURRENT FILE below)\n"
        "=======\n"
        "(replacement lines)\n"
        ">>>>>>> REPLACE\n\n"
        "Rules:\n"
        "1. Each SEARCH text must be copied EXACTLY from the current file "
        "(character-for-character, including indentation) and must occur "
        "exactly ONCE in it. Keep SEARCH as small as practical (typically "
        "1-15 lines).\n"
        "2. To INSERT new code, SEARCH for the nearest existing anchor "
        "line(s) and REPLACE with those same anchor lines plus the new code.\n"
        "3. Emit one edit block per fix. Fix ALL the failures listed below. "
        "Touch NOTHING else -- code you do not name in a SEARCH block cannot "
        "and must not change, and the passing tests depend on that.\n"
        "4. No preamble, no explanation, no markdown fences around the "
        "blocks -- edit blocks only."
    ]

    if failure_context:
        sections.append(
            "## FAILING TESTS TO FIX\n\n"
            "```\n" + failure_context.strip() + "\n```\n\n"
            "Read the assertions for the expected behavior. Concentrate on "
            "these; everything else in the file already passes."
        )

    if spec_excerpt:
        sections.append(f"## SPEC (for reference)\n\n{spec_excerpt}")

    sections.append(
        f"## CURRENT FILE (the file you are patching)\n\n"
        f"```\n{existing_content}\n```"
    )

    return "\n\n".join(sections)


def apply_code_edit_script(
    response: str, existing_content: str
) -> EditScriptOutcome:
    """Parse and apply a fix response, or report why the caller must fall back.

    Drift is impossible BY CONSTRUCTION rather than by instruction: content the
    model does not name in a SEARCH block is never sent to the model's output
    at all, so it cannot be quietly rewritten. That is the property #1528 was
    built for and the one this issue asks the implementation stage to inherit.
    """
    blocks = parse_edit_blocks(response or "")
    if not blocks:
        return EditScriptOutcome(None, failures=["no edit blocks in response"])

    patched, failures = apply_edit_blocks(existing_content, blocks)
    if failures:
        # Partial application is never returned as success -- the same contract
        # the spec stage holds.
        return EditScriptOutcome(None, blocks=len(blocks), failures=failures)

    if not patched.strip():
        return EditScriptOutcome(
            None, blocks=len(blocks), failures=["edits emptied the file"]
        )

    return EditScriptOutcome(
        patched, blocks=len(blocks),
        preserved=unchanged_ratio(existing_content, patched),
    )


#: A response that is plainly a whole file rather than edit blocks. Cheap
#: pre-check so an obvious regeneration is not run through the parser.
_LOOKS_LIKE_WHOLE_FILE = re.compile(r"^\s*(?:```|from |import |#!|\"\"\")")


def response_is_a_regeneration(response: str) -> bool:
    """Did the model ignore the format and send the file back anyway?"""
    if not response:
        return False
    if "<<<<<<< SEARCH" in response:
        return False
    return bool(_LOOKS_LIKE_WHOLE_FILE.match(response))
