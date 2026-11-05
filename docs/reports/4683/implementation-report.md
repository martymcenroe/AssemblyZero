# Implementation report: #4683

An implementation run on a TypeScript target (a Vitest web suite beside a Python suite) halted at N4 on iteration 0, file 3 of 8: a 3,666-line, 171,540-byte Python module. N4 asked for it whole. Both attempts came back as the one new function the spec asked for, and the size gate (#587) refused them: "File shrank drastically from 3666 lines to 67 lines". The edit script (#2407) never engaged, because `should_use_edit_script` returns False when there is no failure to fix, and on a first draft there is none. A 30,172-byte TypeScript module was next in the same run, on the same path.

## What changed

- R1, `edit_script_fix.py`: `LARGE_FILE_CHARS = 30_000`, half of `CODE_GEN_PROMPT_CAP` (#644). A whole-file draft carries the file in and back out, so a file over half the cap cannot make the round trip inside it. `is_large_file(change_type, existing_content)` is true for a Modify file at or over it.
- R2, `edit_script_fix.py`: `build_code_edit_script_draft_prompt` asks for the change the spec describes for the file, in the same edit-block format the fix prompt uses and `apply_code_edit_script` applies. It carries the file's description, its Section 6 subsection, the files the run may change and the current file, and says nothing about failing tests. `previous_attempt_section` is what a retried edit script is told about the one before it.
- R2, `unrequested_changes.py`: `spec_subsection(spec, path)` returns a file's Section 6 subsection as written, heading to next heading, prose and diffs together. It reads headings with the module's existing `_HEADING`, tracking fences line by line as `spec_hunks` does.
- R1, R3, R4, `orchestrator.py`: `edit_large_file` changes a large file by edit script on every iteration. A first draft sends the draft prompt; a fix sends the fix prompt with the spec subsection as its reference. The patched file goes through `validate_code_response` against the file it patches, so the size gate, the Python syntax check and the JSON Schema keyword check hold for it. An attempt that cannot be used is retried with its reason up to `MAX_FILE_RETRIES`; when none holds it raises `ImplementationError` naming every attempt. It never falls back to a whole-file rewrite.
- R5, `orchestrator.py`: a large test file in a fix iteration whose patch never holds is left as it is and the operator is alerted, as #2866 rules for every test file.
- `orchestrator.py`: `try_edit_script_fix`'s call and apply move into `run_edit_script`, which both paths share. A call that raises propagates from it, so each caller alerts in its own handler, as the loud-failure check requires. `try_edit_script_fix` makes the same alerts with the same records as before. `implement_code` builds no whole-file prompt for a large file, so no `[PRUNE]` line appears for a prompt nothing sends.
- `gate_registry.py`: `edit_large_file`'s raise is a site of `impl.file_generation_failed`, the same retry budget as `generate_file_with_retry`'s, so no halt row is added.

## What did not change

A file under 30,000 characters takes the whole-file path on its first draft and the edit script on a fix, exactly as before (R6). The fix prompt's text is unchanged. #4299, the fix path writing an edit script's output without `validate_code_response`, is still open: the large-file path validates, the small-file fix path does not.

## The real files

Of the halted run's eight files, the two over the threshold are the 171,540-byte Python module and the 30,172-byte TypeScript module. The other five Modify files (8,573 to 21,811 bytes) keep the whole-file path, and the eighth is an Add.
