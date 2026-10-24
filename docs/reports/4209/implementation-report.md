# Implementation Report: #4209

`tests/unit/test_land_2283_guard.py::test_the_shipped_embed_drops_nothing_from_the_repos_own_workflow` asserted that the workflow embedded in `tools/land_2283_ci_tiers.py` drops no line of `.github/workflows/ci.yml`. The embed landed in PR #3459 on 2026-09-22. From then on every line `ci.yml` gains is a line the embed lacks, so the change tracked in #4208 failed the test with 54 lines, and the PR landing that change would fail its own run.

The check now applies only while the landing is pending. Two helpers in the test file decide it:

- `landing_pending(workflow)` is true while `ci.yml` still carries any line in the script's `INTENDED_REMOVALS`, the lines the embed removes on purpose. The script lands its change in one Contents API PUT, so those lines leave `ci.yml` in the same commit that brings the lines it adds.
- `guard_failures(workflow, embed)` returns `would_drop(workflow, embed)` while the landing is pending, and nothing once it has landed.

The test against this checkout's `ci.yml` is renamed `test_the_shipped_embed_drops_nothing_while_its_landing_is_pending` and asserts `guard_failures(...) == []`.

The lines the embed adds could not decide the state, as the issue's requirement 2 first put it. The change in #4208 rewrites two lines the landing wrote, the `# Issues` header and the coverage upload's `if: always()`, and a set of lines cannot tell a line rewritten after the landing from one that has not landed. The lines the landing removes do not come back.

`tools/land_2283_ci_tiers.py` is unchanged. Its own call to `would_drop` has no pending condition, so running it over a `ci.yml` that has moved on still refuses with exit 2. The six tests of `would_drop` are unchanged. No file under `.github/workflows/` is changed.
