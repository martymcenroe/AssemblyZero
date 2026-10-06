# Implementation report: #3633

## `new_repo.py` no longer writes `GEMINI.md`

- `tools/new_repo.py`: `create_gemini_md` and step 7, which called it, are removed. The generated file inventory's tree and key-files table no longer list the file. The step numbers after 7 are unchanged: they are console labels, and the sequence already carried 5b, 11a, 11b2 and 13b.
- `.claude/templates/GEMINI.md.template`: deleted. Nothing in `tools/` read it; the generator carried its text inline.
- `docs/standards/0009-structure-schema.json`: the `GEMINI.md` entry (`required: true`) is gone. `new_repo.py` is the schema's only reader, so this is what stops the scaffolder treating the file as required.
- `docs/standards/0009-canonical-project-structure.md`, `docs/standards/0011-audit-decisions.md`, `docs/runbooks/0901-new-project-setup.md`, `docs/runbooks/0933-workflow-readiness-audit.md`: the file is no longer listed as required or checked for; the readiness audit now checks that it is absent.

Left as they are: `tools/fix_gemini_ack.py`, a cleanup of existing files rather than the generator; the dated audits under `docs/audits/` and the fixture string in `tests/unit/test_audit_deferred_scope.py`, which quote the template's name as data; and `docs/runbooks/0953-repo-rename-checklist.md`, which names `GEMINI.md` as a class of stale reference to search for.
