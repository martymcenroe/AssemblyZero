# Test Report — Guard the #2283 Landing Embed (#3448)

```
poetry run pytest tests/unit/test_land_2283_guard.py -q
7 passed
```

## Why It Is Unit-Tested Rather Than Exercised

The script cannot be run to test it. It decrypts the classic PAT, and an agent
must never parent that process (ADR-0216, and the operator rule in
`_pat_session`'s docstring). So the guard is verified as a pure function, which
is why `would_drop()` takes two `bytes` arguments and touches no network.

## The Two That Carry the Weight

**`test_the_actual_regression_this_guard_exists_for`** reconstructs the real
case — main carrying `concurrency:` and `setup-python@v7` against an embed
carrying neither — and asserts both are reported. It fails if the guard ever
stops catching the thing it was written for, which is the only property that
makes it worth shipping.

**`test_the_shipped_embed_drops_nothing_from_the_repos_own_workflow`** points
the guard at the repo's actual `ci.yml`. A guard that catches other people's
drift while shipping stale content itself would be theatre.

That second one is deliberately **not** an equality assertion, and the reason is
specific. The embed is ahead of `ci.yml` by the tier steps until the operator
runs the script, and equal to it afterwards. An equality check would fail for
exactly as long as the landing is pending — going red on merge to main and
staying red until an unrelated manual step happened. Asserting the guard's own
property instead is green in both states and still catches a future `ci.yml`
edit the embed does not learn about.

Verified against both states rather than assumed. Against the branch's workflow
the embed is identical, so nothing drops. Against `origin/main`'s workflow the
lines the embed lacks are exactly four:

```
# CI Workflow - Unit tests on every push/PR, integration tests on main
# Issues #325, #116, #225
        if: github.event_name == 'push' && github.ref == 'refs/heads/main'
        run: poetry run python tools/test-gate.py tests/integration/ -v --tb=short -m integration
```

which are precisely the four in `INTENDED_REMOVALS`, so the guard returns empty
there too.

## The Rest

Identical content drops nothing; declared `INTENDED_REMOVALS` do not trip it;
blank lines are ignored; reordering alone is not treated as dropping.

## What Is Not Verified

**No end-to-end run.** No branch was created, no PUT was issued, no PR opened.
The network path — Contents API semantics, the blob-sha update, the merge poll —
is unchanged from a script that has landed workflow files before, but it is
unexercised here and this report does not claim otherwise.

**The guard does not validate YAML.** It compares lines. An embed that is
current but malformed passes it; that failure surfaces on the workflow run, not
here.
