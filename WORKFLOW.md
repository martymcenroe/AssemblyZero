# WORKFLOW.md - AssemblyZero Development Workflow

Projects using this workflow: Aletheia, Talos, Clio, maintenance, Hermes, RCA-PDF

---

## Gemini Reviews

Gemini reviews are handled by the workflow scripts. Do not call Gemini directly outside the pipeline.

---

## Worktree Isolation (AssemblyZero)

**Code changes MUST be made in a worktree. Docs/CLAUDE.md can be committed directly to main.**

```bash
git worktree add ../AssemblyZero-{IssueID} -b {IssueID}-short-desc
git -C ../AssemblyZero-{IssueID} push -u origin HEAD
poetry install --directory ../AssemblyZero-{IssueID}
```

Post-merge cleanup procedure is in `CLAUDE.md`.
