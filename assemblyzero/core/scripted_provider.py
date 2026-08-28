"""A drafter and reviewer made of committed fixtures (#2567).

The factory has no test of the factory. Eight thousand unit tests exercise
functions; nothing exercises a ROLL. Every defect of the 2026-08-27 campaign
lived in the seams between stages — guards fighting across nodes (#2555), the
janitor sweeping what the loader reads (#2551), the merge mangling between
drafter and checker (#2559) — and seams only light up when a whole roll runs.
Until now the only end-to-end harness was a live roll of a real issue, which
costs an afternoon and real tokens per defect found.

`ScriptedProvider` is the transport, and ONLY the transport, replaced. The
graph, the janitors, the gates, the file writes, the halt path and the
enforcement all run for real. A response comes from a committed fixture
chosen by matching the call against rules, so the same roll replays
byte-identically on every machine with no network.

## Routing is explicit, and a miss is loud

A provider that silently returns a default when no rule matches produces a
roll that "passes" while exercising nothing. Every call must match a rule;
an unmatched call returns a FAILED `LLMCallResult` naming the stage, the
call number, and the rules that were tried. A test asserting a green path
therefore cannot accidentally pass on a fixture set that does not cover it.

## Why not extend MockProvider

`MockProvider` cycles a list and ignores the prompt, which is right for a
unit test of one node and wrong for a roll: the drafter, the reviewer and
the analyst are different callers, and a roll's shape is exactly which of
them is asked what, in what order. Routing on the call is the feature.

## Recording is half the value

`calls` keeps every (stage, system prompt head, content head) in order, so a
test can assert the PATH the graph took — that the revision loop ran twice,
that the reviewer saw the second draft, that no stage was skipped. A roll
that reaches the right end state by the wrong route is a defect this catches
and an end-state assertion does not.

#2572's deterministic tier rides on this: a preserved BAD response replayed
through the real machinery is a `ScriptedRule` whose fixture is the response
that killed a run.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from assemblyzero.core.llm_provider import LLMCallResult, LLMProvider


@dataclass(frozen=True)
class ScriptedRule:
    """One routing rule: when this matches, answer with this text.

    `stage` is a label for assertions and error messages, never a matcher.
    Matching is on the call itself so the rule stays true when a stage is
    renamed.
    """

    stage: str
    #: Regex matched against the system prompt. None matches anything.
    system_pattern: str | None = None
    #: Regex matched against the content. None matches anything.
    content_pattern: str | None = None
    #: The response text. Mutually exclusive with `fixture`.
    response: str | None = None
    #: A file under the fixture root, read verbatim. Preferred for anything
    #: longer than a line: a fixture on disk can be diffed and replayed.
    fixture: str | None = None
    #: Answer only the Nth matching call (1-indexed), so a revision loop can
    #: be scripted round by round. None answers every matching call.
    on_call: int | None = None
    #: Fail this call instead of answering it, with this message. The
    #: halt-path rolls are built from these.
    fail_with: str | None = None

    def matches(self, system_prompt: str, content: str) -> bool:
        if self.system_pattern and not re.search(
            self.system_pattern, system_prompt or "", re.IGNORECASE | re.DOTALL
        ):
            return False
        if self.content_pattern and not re.search(
            self.content_pattern, content or "", re.IGNORECASE | re.DOTALL
        ):
            return False
        return True


@dataclass
class ScriptedCall:
    """One recorded invocation."""

    index: int
    stage: str
    system_head: str
    content_head: str
    answered: bool


class ScriptedProvider(LLMProvider):
    """An LLM made of fixtures, routed by what the caller asked."""

    def __init__(
        self,
        rules: list[ScriptedRule],
        *,
        fixture_root: Path | None = None,
        model: str = "scripted",
    ) -> None:
        self._rules = list(rules)
        self._fixture_root = Path(fixture_root) if fixture_root else None
        self._model = model
        self._call_count = 0
        self._per_stage_counts: dict[str, int] = {}
        self.calls: list[ScriptedCall] = []

    @property
    def provider_name(self) -> str:
        return "scripted"

    @property
    def model(self) -> str:
        return self._model

    @property
    def stages_called(self) -> list[str]:
        """The path the roll actually took, in order."""
        return [call.stage for call in self.calls]

    def _load(self, rule: ScriptedRule) -> str:
        if rule.response is not None:
            return rule.response
        if rule.fixture is None:
            return ""
        if self._fixture_root is None:
            raise ValueError(
                f"rule for stage {rule.stage!r} names fixture "
                f"{rule.fixture!r} but the provider has no fixture_root"
            )
        path = self._fixture_root / rule.fixture
        # Deliberately NOT caught: a missing fixture is a broken test, and a
        # broken test must fail at the fixture rather than three stages later
        # as a mysterious drafter failure.
        return path.read_text(encoding="utf-8")

    def _select(
        self, system_prompt: str, content: str
    ) -> tuple[ScriptedRule | None, str | None]:
        """Pick the rule for this call, or explain why none was picked.

        Two properties are load-bearing and neither is the obvious
        first-match-wins:

        **Ambiguity is an error, not a precedence question.** If rules for
        two different STAGES both match one call, the fixture set is wrong:
        `system_pattern="draft"` also matches "You review the draft", and
        first-match-wins would route the reviewer's call to the drafter and
        produce a green roll that exercised the wrong path. That is the
        exact class of silent misrouting this harness exists to catch, so it
        fails loudly instead.

        **`on_call` numbers the calls to a STAGE, not to a rule object.**
        Several rules with the same stage are one scripted sequence — round
        1, round 2 — so the counter belongs to the stage. Counting per rule
        object makes each rule's counter lag by however many earlier rules
        declined, which silently breaks every sequence past the second.
        """
        matched = [
            rule for rule in self._rules
            if rule.matches(system_prompt, content)
        ]
        if not matched:
            return None, None

        stages = sorted({rule.stage for rule in matched})
        if len(stages) > 1:
            return None, (
                f"ScriptedProvider: call {self._call_count} matched rules "
                f"for {len(stages)} different stages ({', '.join(stages)}). "
                f"Overlapping patterns route a call to whichever rule was "
                f"listed first, which is how a roll goes green having "
                f"exercised the wrong path. Tighten the patterns so exactly "
                f"one stage matches (#2567)."
            )

        stage = stages[0]
        seen = self._per_stage_counts.get(stage, 0) + 1
        self._per_stage_counts[stage] = seen

        for rule in matched:
            if rule.on_call == seen:
                return rule, None
        for rule in matched:
            if rule.on_call is None:
                return rule, None
        scripted_rounds = sorted(
            r.on_call for r in matched if r.on_call is not None
        )
        return None, (
            f"ScriptedProvider: call {self._call_count} is round {seen} of "
            f"stage {stage!r}, but the fixture set scripts only rounds "
            f"{scripted_rounds} and has no catch-all rule. The roll ran "
            f"longer than the script — either the loop is not converging or "
            f"the script is short a round (#2567)."
        )

    def invoke(
        self,
        system_prompt: str,
        content: str,
        timeout_seconds: int = 300,
        response_schema: dict | None = None,
        json_schema: dict | None = None,
    ) -> LLMCallResult:
        self._call_count += 1
        rule, problem = self._select(system_prompt or "", content or "")

        head_s = (system_prompt or "")[:160].replace("\n", " ")
        head_c = (content or "")[:160].replace("\n", " ")

        if rule is None:
            self.calls.append(
                ScriptedCall(
                    self._call_count, "UNMATCHED", head_s, head_c, False
                )
            )
            if problem is None:
                tried = ", ".join(
                    f"{r.stage}(sys={r.system_pattern!r})" for r in self._rules
                ) or "(no rules)"
                problem = (
                    f"ScriptedProvider: call {self._call_count} matched no "
                    f"rule. system={head_s!r} content={head_c!r}. "
                    f"Tried: {tried}. A roll that reaches an unscripted call "
                    f"is exercising a path the fixture set does not cover — "
                    f"add a rule rather than a default (#2567)."
                )
            return LLMCallResult(
                success=False,
                response=None,
                raw_response=None,
                error_message=problem,
                provider=self.provider_name,
                model_used=self._model,
                duration_ms=0,
                attempts=1,
            )

        self.calls.append(
            ScriptedCall(
                self._call_count, rule.stage, head_s, head_c,
                rule.fail_with is None,
            )
        )

        if rule.fail_with is not None:
            return LLMCallResult(
                success=False,
                response=None,
                raw_response=None,
                error_message=rule.fail_with,
                provider=self.provider_name,
                model_used=self._model,
                duration_ms=0,
                attempts=1,
            )

        text = self._load(rule)
        return LLMCallResult(
            success=True,
            response=text,
            raw_response=text,
            error_message=None,
            provider=self.provider_name,
            model_used=self._model,
            duration_ms=1,
            attempts=1,
        )


#: Set by `use_scripted_provider` so `get_provider` can hand the same
#: instance to every caller in one roll. A roll has ONE drafter and ONE
#: reviewer; handing out fresh instances would reset the call counters that
#: `on_call` and the recorded path depend on.
_ACTIVE: ScriptedProvider | None = None


def set_active(provider: ScriptedProvider | None) -> None:
    global _ACTIVE
    _ACTIVE = provider


def get_active() -> ScriptedProvider | None:
    return _ACTIVE
