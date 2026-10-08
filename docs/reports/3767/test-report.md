# Test Report: #3767 and #3764

## New tests

- `tests/unit/test_failopen_tags_3767.py` (11):
  - an unparseable Python fence fails the draft as `python_fences_parse`;
  - a callee that does not parse raises `CompletenessCannotCheck`;
  - the node turns that into `completeness_cannot_check`, an ERROR line, and a HALT route;
  - a grace revision still reaches N2;
  - a failed `pr` stage routes to `terminal`;
  - an unwritable durable copy stops `_save_lld_file` with an ERROR line;
  - the five keys are absent from the loud-failure baseline.
- `tests/unit/test_restore_prefers_durable_and_base.py` (5):
  - the durable copy wins over a graveyard draft;
  - `origin/<base>` wins over an older graveyard copy;
  - a graveyard copy that is not the settled LLD is refused and named;
  - one that is the settled LLD is used;
  - with no settlement record, the graveyard is still the last resort.

## Tiers (run locally, no speedrun roll running)

```
pytest tests -q                                   29 failed, 11567 passed, 66 skipped, 90 deselected, 6 xfailed
  after the gate-registry row: the 8 new failures  130 passed
pytest -m "integration or e2e or adversarial"     83 passed, 7 skipped
```

The 8 failures that came from this change were the gate registry and the halt-site walker. They were caused by the new halt return, which shifted the cap's return index. All 8 pass once `spec.completeness_cannot_check` is registered.

The other 21 fail identically on unchanged `main`, measured on 2026-10-07 for PR #4138:
- `test_auto_reviewer_wait_loop.py` (16);
- `TestRunJsGate` (2);
- `test_adr_references_resolve`;
- `test_full_pipeline_success`;
- `test_checkpoint_carries_no_enums`, which passes when run alone.

None touches these files.

## Audits

```
audit_loud_failure.py --check            PASS -- 318 site(s)
audit_fail_open.py --check --strict      PASS -- 312 files, 9660 sites
audit_halt_sites.py --check --strict     PASS -- 150 halt sites, every one registered
```

## Lint

Ruff findings per changed file are unchanged against `origin/main`, and the two new test files have none.
