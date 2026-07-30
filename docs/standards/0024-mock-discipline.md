# Standard 0024 — Mock Discipline: MagicMock Only at Documented I/O Boundaries

**Status:** Active
**Date:** 2026-07-29
**Origin:** #948 (audit mandate), motivated by three production incidents (§2)
**Companion:** #1934 (replacement execution batch)

## 1. The rule

1. `MagicMock` / `Mock` / `AsyncMock` are acceptable **only** at genuine I/O
   boundaries: subprocess execution, network calls, filesystem side effects
   you cannot route through `tmp_path`, wall-clock time, randomness, and
   external SDK clients.
2. Every such use carries an inline justification comment at the
   construction site, prefixed `# mock-ok:` — e.g.
   `# mock-ok: real PTY spawn needs a console host`. A `MagicMock` without
   one is a review finding.
3. Internal domain objects are **never** MagicMocked. Use, in order of
   preference:
   - the real class, when construction is cheap (`LLMCallResult(...)`,
     `RetryPolicy.default()`, `CompletenessCheck(...)` — most of our
     dataclasses cost nothing);
   - a **typed fake**: a small class with explicit attributes and the
     production method signature, returning real result objects;
   - a pytest fixture building real data structures.
4. A fake that stands in for a call the test claims to exercise must carry
   **proof-of-life**: an invocation counter the test asserts
   (`assert fake.invocations == 1`). A mock that is never hit is a test
   that is lying about its coverage.
5. Mocks must be **killable and finite**: any fake standing in for a
   process, stream, or connection must expose the same terminal behavior
   the real object has (EOF, dead-child, close) so bounded-drain loops can
   exit. A mock that nothing can end will hang or leak exactly where the
   real object would not (§2, incident three).

## 2. Why — three incidents, one disease

**The hasattr placebo (#856).** Production added
`if hasattr(result, "response")`. `hasattr` is always True on a MagicMock,
so 16 tests passed while the real path crashed on
`parse_structured_feedback(MagicMock)`. The suite verified the mock's
willingness to invent attributes, not the code.

**The dead mock burning money (#956).** Two tests mocked
`assemblyzero.core.gemini_client` at sys.modules level after #773 had
rerouted production through `get_provider`. The mock was dead code; one
test silently made a real Claude API call every run (~$0.05, network-flaky)
and the other passed through a fast-path with no LLM at all. Fixed in PR
#1933 with the typed-fake + proof-of-life pattern (§4).

**The unkillable mock that took down a CI runner (#1915).** A drain-bound
test wired `proc.read` to a mock that never raised EOF while
`proc.isalive` stayed True — a child no kill could end. The leaked drain
thread spun at ~97,500 calls/sec with MagicMock recording every call;
memory grew without bound and the runner VM died at ~30 minutes with zero
pytest output. The production code was correct; the mock modeled an object
that cannot exist.

## 3. Audit snapshot (2026-07-29, #948)

- `tests/`: **673 MagicMock occurrences across 96 files.** Top offenders
  listed in #1934 (32/26/25/24… per file).
- `assemblyzero/` source: clean — its 10 references are the adversarial
  validator's own no-mock enforcement (`adversarial_validator.py` bans
  mock usage in pipeline-GENERATED tests) and defensive comments.
- `sentinel/`: zero.

The irony the audit surfaced: the pipeline already refuses mocks in tests
it generates. This standard extends the same discipline to the hand-written
suite that guards the pipeline itself.

## 4. The reference pattern

From PR #1933 (`tests/unit/test_testing_workflow.py`):

```python
class FakeReviewerProvider:
    """Typed fake per standard 0024: explicit attributes, real result type."""

    provider_name = "fake"
    model = "fake-reviewer"

    def __init__(self, response_text):
        self._response = response_text
        self.invocations = 0          # proof-of-life (§1.4)

    def invoke(self, system_prompt="", content="",
               json_schema=None, response_schema=None):
        self.invocations += 1
        return LLMCallResult(          # REAL result object, not a Mock
            success=True,
            response=self._response,
            raw_response=self._response,
            error_message=None,
            provider="fake",
            model_used="fake-reviewer",
            duration_ms=1,
            attempts=1,
        )
```

The test then asserts both the behavior AND `fake.invocations == 1`.
A rerouted call path makes the counter assertion fail loudly instead of
letting a dead mock pass silently for years.

## 5. Enforcement

- **Review rule (now):** new tests introducing `MagicMock` without a
  `# mock-ok:` boundary justification fail code review. Reviewers cite
  this standard by number.
- **Replacement batch (#1934):** existing usage migrates top-offender-first;
  I/O-boundary keepers gain their `# mock-ok:` comments as files are
  touched.
- **Optional finisher (tracked in #1934):** a lint/pre-commit check
  flagging `MagicMock` imports in files without any `# mock-ok:` marker.

## 6. Boundary examples

| Mocking this | Verdict |
|---|---|
| `subprocess.run` / PTY spawn | mock-ok (I/O boundary) — but killable, §1.5 |
| `gh` / GitHub API calls | mock-ok (network) |
| `time.sleep` in retry tests | mock-ok (wall clock) |
| `GeminiClient` inside `GeminiProvider` tests | mock-ok (SDK/network edge) — return real `GeminiResult`-shaped data |
| `LLMCallResult`, `RetryPolicy`, state dicts | never — construct the real thing |
| A provider handed to a workflow node | typed fake with proof-of-life (§4) |
| A workflow state or config | never — build the real TypedDict |
