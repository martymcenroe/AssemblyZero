# Implementation report: #3760

## A missing first-party module's message names the one that exists

`assemblyzero/workflows/implementation_spec/nodes/validate_completeness.py`:

- New `_same_named_modules(module, repo_root, base_ref)`: modules in the same top-level package whose final name matches the missing one's, found under the source roots on disk and with `git ls-tree` on the run's base, as dotted paths, at most three, the missing module itself excluded.
- `check_import_targets_exist`'s failure message adds, for each unresolvable first-party module that has such a match, `` `boostgauge.stingray` -> did you mean `boostgauge.skins.stingray`? ``. Third-party modules and modules with no match get no suggestion. The verdict is unchanged.

Found on boostgauge #2, run `run-issue2-040123` (2026-10-07 04:01 Central), the first run with #3754's stricter resolution: the spec imported `boostgauge.stingray` on two of four drafts and the spec stage hit its revision cap, the message never having said where `stingray` actually lives.
