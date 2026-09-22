# Implementation Report — Dependabot Config Tests Follow the File (#3443)

## The Failure

`main`'s CI was red. Three tests failed and nothing else did:

```
FAILED tests/unit/test_dependabot_config.py::test_config_exists_and_is_valid_yaml
FAILED tests/unit/test_dependabot_config.py::test_exactly_the_three_specified_ecosystems
FAILED tests/unit/test_dependabot_config.py::test_the_sentinel_entry_targets_the_lockfile_that_had_the_alerts
3 failed, 10459 passed, 69 skipped, 7 deselected, 6 xfailed
```

One cause for all three: `.github/dependabot.yml` does not exist. #3415 renamed it
to `.github/dependabot.yml.disabled` to stop the Actions minute burn. That was
deliberate, is documented, and remains the intended state until the post-October
review.

Nothing regressed. The config is intact inside the `.disabled` file. The suite was
red about a rename.

## The Change

`tests/unit/test_dependabot_config.py` pinned one hardcoded path:

```python
CONFIG = ROOT / ".github/dependabot.yml"
```

so it reported on the file's *name* rather than the config's *content*. It is
replaced by a resolver that follows the config wherever it lives:

```python
def _config() -> Path:
    present = [p for p in (ENABLED, DISABLED) if p.is_file()]
    assert present, "...the config was not renamed, it was lost"
    assert len(present) == 1, "...ambiguous which one GitHub reads"
    return present[0]
```

Three call sites now go through it: `_loaded()`, `test_config_exists_and_is_valid_yaml`,
and `test_the_config_is_not_a_workflow_file`. No assertion was weakened and none
was removed.

## Why Not Skip Them While Disabled

Skipping is the obvious fix and the wrong one. The config would sit unchecked for
the entire disabled window — exactly when nobody is looking at it — and be
re-enabled unexamined. The guard these tests provide (#1923) is against a config
that silently stops matching reality when a directory is renamed or a manifest
moves. That risk does not pause because Dependabot is off.

Following the file keeps every content assertion live while disabled, and makes
re-enabling a pure rename with no test edit, so the flip cannot be forgotten.

## What the Change Adds

The ambiguity assertion is new behaviour, not a restatement. Two copies present at
once is a real state — a half-finished re-enable — in which it is unclear which
file GitHub reads. That is now a failure rather than a coin flip.

## Scope

Untouched: `.github/dependabot.yml.disabled` itself, the disable decision, and
#3412, the open Dependabot PR.
