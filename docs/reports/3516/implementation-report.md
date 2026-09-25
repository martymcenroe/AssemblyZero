# Implementation Report: agy tool-execution posture (#3516)

## What was asked

Run a recorded experiment, invoking `agy` exactly as `GeminiClient` does, that asks it to run a shell command and to write a file at an absolute path, with and without `--sandbox`. Put the verbatim results in ADR 0220 or a successor. Pass `--sandbox` if it changes anything, and pin that with a test. Write the blast-radius statement where the operator can point at it.

## What was found

| Invocation | Shell (`whoami`) | File at an absolute path outside the temp cwd |
|---|---|---|
| `agy -p --model gemini-3.1-pro-high` (the client before this change) | ran, answered `mcwiz` | written |
| `agy --sandbox -p ...` | refused (`createAppContainer: ShellExecute failed`) | **written** |
| `agy --sandbox --mode plan -p ...` | refused | **written**; the plan auto-approved |

`--sandbox` removes shell execution. Nothing available removes file writes. The verbatim responses are in ADR 0233.

## What changed

| File | Change |
|---|---|
| `assemblyzero/core/gemini_client.py` | `AGY_SAFETY_ARGS = ["--sandbox"]`, inserted into the PTY argv and the stdin argv |
| `docs/adrs/0233-agy-tool-execution-posture.md` | New ADR, Proposed: the experiment, the verbatim results, the blast-radius statement, and open questions |
| `docs/adrs/0220-antigravity-cli-migration.md` | Finding 2 points to ADR 0233 |
| `tests/unit/test_agy_sandbox_args.py` | New: pins the flag on both transports |
| `tests/unit/test_gemini_client.py` | One argv assertion now includes `--sandbox` |

## Blast radius, as recorded in ADR 0233

Inside the workflow, with `--sandbox`, `agy` cannot run a shell command. It can still write a file at any path the operator's Windows account can write, without asking, and it keeps its own state under `~/.gemini/antigravity-cli/`.

## Held for the operator

- Accepting ADR 0233.
- #3517 (both adversarial roles on `agy`), which rests on the premise this experiment disproved.
