# Implementation Report: adversarial review runs on 3.8 Flash (#4192)

## What happened

PR #4191 (#4178) made 3.8 Flash the only Gemini the client sends, since agy lists no Pro and the operator forbids Argon. The adversarial path refused Flash at both ends: `resolve_adversarial_model` before the request, and `verify_model_is_pro` on the reply. So the `impl.adversarial` seat, `gemini:3.1-pro` → `gemini-3.8-flash-high`, failed with `ForbiddenModelError` on every run.

The agent that wrote #4191 recorded that breakage as the operator's decision. It was not. He approved the no-Argon path, and at 6:50 PM Central on 2026-10-21 he rejected the broken review outright. He wants adversarial review running.

The Flash refusal in this path was agent-written (#2286, #2374, #3808). Nothing traces it to the operator.

## What landed

| File | Change |
|---|---|
| `assemblyzero/workflows/testing/adversarial_gemini.py` | `resolve_adversarial_model` keeps its `FORBIDDEN_MODELS` check, which refuses Argon, and then requires the id to be in `config.AGY_GEMINI_MODELS` in place of the Flash and Lite refusal. `verify_model_is_pro` refuses a reply naming a forbidden model, and accepts one in `AGY_GEMINI_MODELS` or naming Pro. Both ends of one call accept the same models (#2374). |
| `docs/reports/4178/implementation-report.md`, `docs/reports/4178/test-report.md` | The sentence saying the operator approved the broken review is replaced by what happened. |

Also corrected on GitHub: the ruling comment on #4178 (edited in place) and PR #4191's body. The squash commit message on `main`, `9242caae`, cannot change; this report and #4192 record the correction.

## Not changed

- The profiles keep `gemini:3.1-pro` for the adversarial seat.
- `FORBIDDEN_MODELS` is unchanged. It refuses Argon, and the retired Flash ids it lists stay refused.
