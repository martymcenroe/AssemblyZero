# Implementation report: #3754, #3755, #3756

The implementation spec's completeness gate now refuses a spec that names first-party code which does not exist, or calls existing code with keywords it does not take. Both shapes passed before, on boostgauge #2 run `run-issue2-024542` (2026-10-07 02:45 Central): the spec imported `boostgauge.renderer`, which exists nowhere, and built `Telltale(duration=...)` against `Telltale.__init__(self, window, decay_rate=None)` in a file the plan did not own. The tests built from it could not pass; the implementer answered NO-EDIT for both, correctly, and the green phase ended at 11 of 13 after five iterations.

## #3754: an import resolves only as the module itself

`assemblyzero/workflows/implementation_spec/nodes/validate_completeness.py`: new `_module_candidates(module_path)` returns `a/b.py` and `a/b/__init__.py` only; `_import_resolves` and `_resolves_on_base` both use it. The parent forms (`a.py`, `a/__init__.py`), added with the check in #842 on the reading "from a.b import c — c might be a name inside a.b.py", are gone: the regex captures the module path `a.b`, which the two forms already cover, so the parent forms only ever let `pkg.<anything>` pass.

`tests/unit/test_implementation_spec_workflow.py::test_resolves_parent_module_src_layout` encoded that reading (it expected `foo.bar.Baz`, a name inside `foo/bar.py`, to resolve). It is replaced by `test_a_name_inside_a_module_is_not_a_module` (`foo.bar` resolves, `foo.bar.Baz` does not) and `test_a_missing_submodule_of_a_real_package_does_not_resolve` (the boostgauge shape, plus a planned Add still resolving).

## #3755: keyword arguments against the real signature

New check `check_call_signatures_match` (classified FACT in `check_classification.py`), run as check 6b after the import check:

- Parses the spec's Python fences with `ast` (tagged Python or untagged, as `_scan_fences` routes them); a fence that does not parse is left to `python_fences_parse`.
- For each `from <first-party module> import <name> [as alias]`, reads the module from the checkout or the run's base (`_module_source`), skips it if the plan Adds or Modifies that file, and reads the callee's signature by `ast` (`_accepted_keywords`): a class through its own `__init__`, or a function. A class without its own `__init__`, or a signature with `**kwargs`, is not judged.
- Flags each call `name(kw=...)` whose `kw` is not among the positional-or-keyword or keyword-only parameters, naming the call, the keyword and the real signature.

Both `except` branches abstain and are ruled `# fail-open:` in the code. The addressability sweep lists the new check as uncovered beside `check_import_targets_exist` (both need a real repo tree); its own test file drives it against one. The classification count test moves from 16 to 17 with a sentence for the new check.

## #3756: a spec settlement names the gate that approved it

Run 53's spec settled when it passed the old gate, and `--fresh` preserves settled artifacts, so without this the new checks would never have seen it.

- `assemblyzero/core/settlement.py`: `collect_inputs` takes an optional `stage`; `gate_input("spec")` adds `gate:spec-completeness`, the hash of `check_classification.CLASSIFICATIONS`'s names sorted one per line. Other stages, and callers that pass no stage, are unchanged.
- Both real callers pass the stage: `orchestrator/stages.py::current_inputs`, which writes settlements, and `tools/speedrun_roll.py::settlement_inputs`, which verifies them.
- A spec settled before this has no gate input and `verify` reports `gate:spec-completeness: a new input the settled artifact was not derived from` once, which is the intent.

## Fail-open baseline

Regenerated; totals only (9556 to 9589 sites, 558 to 560 findings).
