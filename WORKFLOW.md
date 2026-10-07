# WORKFLOW.md - AssemblyZero Development Workflow

Projects using this workflow: Aletheia, Talos, Clio, maintenance, Hermes, RCA-PDF

---

## Gemini Reviews

Gemini reviews are handled by the workflow scripts. Do not call Gemini directly outside the pipeline.

---

## Loud Failure (standard 0034)

Every failure is loud, logged with details, stops the processing that depends on it, and alerts the operator (ADR 0236). There are no fall-throughs, and the `# fail-open:` tag is withdrawn. The rule, with examples: `docs/standards/0034-loud-failure.md`. `tests/unit/test_loud_failure_check.py` fails the unit tier on a new swallowed handler, tag or unrouted node error. Every implementation report states compliance in its "Loud-failure compliance" section.

---

## Worktree Isolation (AssemblyZero)

**Code changes MUST be made in a worktree. Docs/CLAUDE.md can be committed directly to main.**

```bash
git worktree add ../AssemblyZero-{IssueID} -b {IssueID}-short-desc
git -C ../AssemblyZero-{IssueID} push -u origin HEAD
poetry install --directory ../AssemblyZero-{IssueID}
```

Post-merge cleanup procedure is in `CLAUDE.md`.
