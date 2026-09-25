# Implementation Report: the coder has a seat, and it runs on Gemini (#3553)

Landed inside #3563, as umbrella #3562 orders. The full change is in `docs/reports/3563/implementation-report.md`; this is the coder's part of it.

## What was wrong

`implementation/claude_client.py:236` built its provider as `get_provider(f"claude:{model or 'opus'}")`. The model came from `routing.select_model_for_file`, which returned a hardcoded Haiku id (`routing.py:17`) for scaffolds, `__init__.py`, `conftest.py` and files under fifty lines, and `CLAUDE_MODEL` (`core/config.py:36`) for everything else. No flag, state key or profile reached it, so the coder was on Claude whatever a run asked for. N4c (`augment_tests.py`) used the same routing at `--effort low`.

## What changed

- `routing.py` returns a seat: `impl.code.small` by the same four rules, `impl.code` otherwise. `select_model_for_file` now returns the spec that seat resolves to under the active profile. `HAIKU_MODEL` is gone; `CODE_SEAT` and `SMALL_SEAT` replace it in the package's exports.
- `call_claude_for_file(prompt, ..., model=None, seat=None)` resolves `seat` (default `impl.code`) under the active profile and hands the resolved spec to `get_provider`, with the seat's effort unless one is given. An explicit `model` must be a full provider spec. A bare id such as `claude-haiku-4-5-20251001` is refused as `[NON-RETRYABLE]`, so the coder can never fall back to Claude by string concatenation.
- `implement_code` (N4) enters `using_profile(profile_of(state))` around its unchanged body. The batch path for small `Add` files now checks the seat, not a Haiku model id.
- N4c resolves its own seat, `impl.augment_tests`.

Under `gemini.toml`, the default, every coder call is `gemini:3.1-pro` through `GeminiProvider`, which is `agy` over stdin with `--sandbox` (ADR 0220, ADR 0233). Under `claude.toml` the coder is exactly what it was before: Sonnet, and Haiku for small files. The Claude path is reachable only by naming it: `--models claude`, `--seat impl.code=claude:sonnet`, or a profile file.

## Requirements of #3553, as amended by its comment

| Requirement | Where |
|---|---|
| 1. A spec for the code-writing seat, every writing node through `get_provider(spec)` | `--seat impl.code=<spec>` / `impl.code.small` on `run_implement_from_lld.py` (the comment replaced the tool-specific flag with the seat); `claude_client.py` |
| 2. Default `gemini:3.1-pro` through `agy`, with `--sandbox` | `gemini.toml`; the transport's `--sandbox` is pinned by `test_agy_sandbox_args.py` |
| 3. The writer spec in the run record and the PR body | #3565, the recording child, per the umbrella's order |
| 4. A writing node on a Gemini spec never constructs the Claude CLI provider | `tests/unit/test_implement_code_routing.py` |

## No gap found in the coder's path

The coder's calls are text in and a fenced file out (`build_system_prompt`, `extract_code_block`), and the edit-script path is the same shape with a different system prompt. Nothing on the path uses a Claude-only argument: `json_schema` is never passed, and the prompt-caching note in the system prompt is a comment, not an API parameter. So no follow-up issue was filed under #3553 for a Gemini-incompatible behaviour. Whether Gemini writes code as well as Sonnet did is the first boostgauge comparison's question (#3566).
