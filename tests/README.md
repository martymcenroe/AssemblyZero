# Test organization & what CI runs

This is the consistent rule for where a test lives vs. whether CI runs it (#1579, #1580).

## The three locations

| Location | Runs in CI? | For |
|----------|-------------|-----|
| `tests/unit/` | **Yes — every push & PR** (`tools/test-gate.py tests/unit/`) | Hermetic, fast tests. No network, no real credentials, no real subprocess to external services (mock or local-only is fine). |
| `tests/integration/` | **Yes — push to `main` only** (`tools/test-gate.py tests/integration/ -m integration`, `ASSEMBLYZERO_MOCK_MODE=1`) | Slower / orchestration / timing-sensitive / real **local** subprocess (git, spawned Python). Must carry the `integration` marker. |
| `tests/` (root) | **No — intentionally excluded** | Needs real credentials, real network, or operator-only resources that must never run unattended in CI. |

CI invocation lives in `.github/workflows/ci.yml`. Note CI collects **only** `tests/unit/` and `tests/integration/` — a hermetic test left at the root silently never runs. Put hermetic tests under `tests/unit/`.

## Rules

1. **Default to `tests/unit/`.** If a test is hermetic, it belongs there so the fast gate covers it.
2. **`tests/integration/` requires the marker.** Add `pytestmark = pytest.mark.integration` (module-level) — the gate runs with `-m integration`, so an unmarked file there is silently deselected.
3. **The root is for credential/network/operator-only tests, and each must self-guard** — a module-level `pytest.mark.skipif` on a missing credential/path, or an explicit skip — so it is *intentionally* excluded, never *accidentally* run. Current residents:
   - `test_designer.py` — calls real `gh` (auth/issue) in its integration-marked tests.
   - `test_universal_claude_md.py` — reads an operator-machine-only absolute path (`pytestmark = skipif(not path.exists())`).
4. **Never move a failing test into a green gate to make it pass, and never rewrite an assertion just to match current output.** If a dormant root test fails when brought into CI, it's either stale or a real regression — file an issue and `xfail(strict=False)` it with the issue reference until resolved (e.g. #1599).

## Importing tools / reaching the repo root from a test

`tests/conftest.py` puts both the repo root and `tools/` on `sys.path` (computed off the conftest's own location), so tests `import <tool_module>` by bare name from any subdirectory — no per-file `sys.path` fixup needed when a test moves.

For tests that compute a path from `__file__` (e.g. `spec_from_file_location`, reading a fixture under `docs/`), the repo root is **`Path(__file__).resolve().parents[2]`** from `tests/unit/` or `tests/integration/` — one level deeper than the `parents[1]` that worked at the root. This is the fix to apply when relocating such a test (#1580).
