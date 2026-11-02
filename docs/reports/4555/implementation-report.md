# Implementation report: #4555

The implementation workflow halted at N0 on a private TypeScript target with class `unknown`. N0 reads the words of a spec for the test files it names, and the spec's Section 6 changed an existing test file with a git-style diff opening `--- a/web/tests/replay.test.ts` / `+++ b/web/tests/replay.test.ts`. The reader took `a/web/tests/replay.test.ts` and `b/web/tests/replay.test.ts` for two more test files, looked for their runner in directories named `a` and `b`, and found none.

## Where planned paths are read

Every place that reads planned file paths out of a spec or LLD was checked:

- `framework_detector._named_test_paths` reads every word of the document. It is the only reader that met the diff headers, and every reader of the spec's test files goes through it: `named_js_test_paths` and `named_test_files`, so framework resolution (`frameworks_named_by_lld`, `resolve_framework`, `resolve_framework_dirs`), `framework_source` and the LLD-decides rule.
- Section 2's table (`extract_files_to_modify`, `lld_path_enforcer`, `infer_module_path`) is read from its cells, and Section 6 (`extract_plan_code`, `spec_hunks`, `planned_test_files`) from its headings. Neither reads a diff header; both are unchanged.
- `changed_lines` reads git's own `git diff` output, not a spec, and already took one `b/` off.

## What changed

- R1, `assemblyzero/utils/diff_headers.py` (new): the one reader of a unified diff's file headers for anything that reads planned paths out of a spec or LLD. The grammar is closed and enumerated in the module: `--- <name>`, `+++ <name>` and `diff --git <name> <name>` at column 0; in a text a `---` line is a header only above a `+++` header, and a `+++` line only below a `---` one; exactly one leading `a/` or `b/` comes off; `/dev/null` names no file; a name without a prefix is kept; git's C-quoting and tab-ended names are read; a `---`/`+++` name holding a space with no tab after it is not a header's. `with_header_paths` replaces each header line by the paths it names and leaves every other line as it was. No regular expression decides anything.
- R2, `framework_detector.py`: `_named_test_paths` reads the document through `with_header_paths` before splitting it into words, so each of its consumers sees `web/tests/replay.test.ts`.
- R3: only a header line is rewritten, so `a/b.ts` in a table, in prose, or on a lone `---` line keeps its path.
- `changed_lines.py`: shares git's quoting (`git_unquoted`) with the new module instead of keeping a copy. Its `b/` rule for git's output is unchanged.
- R4, `core/errors.py`, `testing/nodes/load_lld.py`, `core/halt_node.py`, `core/recovery_plan.py`: N0's unresolvable-framework halt carries `[FRAMEWORK UNRESOLVED]`, a constant shared by the writer and the classifier. `classify_error` returns `framework_unresolved`, checked before the patterns that read quoted text, since the message quotes paths. The recovery plan says the halt is not transient, what to change, and that a resume halts the same way until the spec or the tree changes. The gate row `impl.framework_unresolved` still matches its site.

## What did not change

A test file whose directory declares no runner still halts N0, now with a class. A path written in a table, a heading or prose is read as before.

## The real spec

N0 run on the approved spec and its target with no model call, its audit and log writers replaced by no-ops so nothing was written to the target, now loads: Vitest in `web` for `web/tests/replay.test.ts`, pytest at the root for the spec's one Python test file, eight files to implement, ten requirements, five executable test functions. Nothing else in N0 halts on it. On `main` the same call halts on `a/web/tests/replay.test.ts`.
