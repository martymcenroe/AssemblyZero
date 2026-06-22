# ADR 0221: Orchestrator artifact lifecycle — LLD/spec are permanent and land via a merged PR; a terminal stage lands them and cleans up

- **Status:** Accepted (operator decision 2026-06-22)
- **Date:** 2026-06-22
- **Related:** #1531, #1624, #1625, #1626, #1627, #1628 (the six orchestrator-pollution defects); Chiron defects report (martymcenroe/Chiron PR #108, commit `f40eb0d`); #1390 (methodology); #238 (LLDs reference, not close); #1459 (LLD worktree+PR rewire); #1504 / #1505 (testing `repo_root=worktree_path`); #1556 / PR #1560 (cleanup-skill worktree removal); #1458 (lineage gitignored)

## Context

During 2026-05-30 → 2026-06-02 the orchestrator built four Chiron issues and left a large mess on the target repo. Chiron's report catalogued nine pollution items; six were filed as AZ issues. Four of them — #1531 (LLD-PR leak), #1624 (LLD orphan), #1625 (spec orphan), #1628 (worktree orphans) — share one root cause:

**The orchestrator's intermediate artifacts (the LLD and the implementation spec) are written to the target repo's main working tree because downstream stages read them back by path, but no end-of-pipeline step ever lands them on `main` or removes them.**

Verified data flow on `main` at `84650e3`:

- LLD finalize writes `docs/lld/active/LLD-NNN.md` to the target working tree and mirrors a copy into a `{N}-lld` worktree → LLD PR (`requirements/nodes/finalize.py:397-400`, `:154-244`).
- The LLD PR carries `No-Issue:` and deliberately does not close the issue (`requirements/git_operations.py:34-42`, `:197-211`; #238). Nothing merges or retires it (#1531).
- The spec stage reads the LLD **by path from the target working tree** (`implementation_spec/nodes/load_lld.py:232-261`; the orchestrator passes the target path at `orchestrator/stages.py:489`).
- The impl stage reads both the spec and the LLD from `original_repo_root` = the target repo (`testing/nodes/load_lld.py:808-819`, `:860-875`).

So the working-tree copies are **load-bearing through the impl stage** — they are not dead pollution; they only become redundant at end-of-run. The gating question: are these artifacts permanent (land on `main`) or scaffolding (discard)?

## Decision

**The LLD and the implementation spec are permanent project history.** They land on the target's `main` via a **merged** PR.

1. **The LLD PR merges; it is not retired unmerged (#1531).** This makes the system's existing intent law — the LLD PR body already instructs "merge to land it on main" (`requirements/git_operations.py:205-211`). The report's R6 suggestion to retire the LLD PR unmerged is rejected: the impl PR is carved fresh from target `main` and does **not** contain the LLD (`orchestrator/stages.py:544-558`), so retiring the LLD PR unmerged would orphan the LLD, not supersede it.

2. **The spec rides the LLD PR (#1625).** The spec stage mirrors `spec-NNNN-*.md` into the existing `{N}-lld` worktree and amends the LLD PR (reusing the `_mirror_to_worktree` + commit pattern). Both land together when the LLD PR merges. Merging the LLD PR does **not** close the parent issue (the `No-Issue:` body preserves #238) — the impl PR remains the issue-closer.

3. **A terminal orchestrator stage performs end-of-run landing + cleanup.** Added as a `cleanup` stage after `pr` in `STAGE_ORDER` — this fits the existing generic-loop graph (`orchestrator/graph.py:170-197`); there is no "pr success branch" to edge a node off, contrary to #1628's description. It:
   - **(a)** Polls the LLD PR to `mergeable_state: clean` and squash-merges it (lands LLD + spec). Bounded by a timeout; on timeout, leave the PR open and defer to manual `/cleanup`, with a clear message.
   - **(b)** Removes the now-redundant working-tree copies of the LLD and spec from the target (#1624) — performed **here, post-merge**, NOT at LLD-finalize, where deleting the file breaks the spec stage that reads it. Scope the deletion to the LLD/spec artifacts only (the LLD-finalize `created_files` list also contains the mutable `lld-status.json`, `finalize.py:434-436`, which must not be deleted).
   - **(c)** Removes the LLD and impl worktrees by **reusing** `testing/nodes/cleanup_helpers.py` (`check_pr_merged`, `remove_worktree`, `delete_local_branch`); plain `git worktree remove`, no `--force`; `git branch -d` only on the merged LLD branch (never `-D`).

4. **Reports already land correctly (#1626).** The testing workflow runs with `repo_root = worktree_path` (`orchestrator/stages.py:578-580`), so reports are written inside the impl worktree; committing a `post-finalize` checkpoint lands them via the impl PR. No lifecycle change needed — just the missing commit.

5. **The N8 cp_docs (907/908) are the one artifact that must NOT land on an external `main` (#1627).** They are AZ-internal stage documentation. Suppress them for external-repo runs via the **existing** `skip_docs` / `doc_scope` switch (`testing/graph.py:415`, `testing/nodes/document.py:246-275`), set by the orchestrator when `target_repo != assemblyzero_root` — not a new `emit_cp_docs` config key (the snippet in #1627 references `state['config']` / `target_repo` / `assemblyzero_root`, none of which exist in `TestingWorkflowState`).

## Consequences

- **#1531, #1624, #1625, #1628 become one coordinated terminal-stage change**, not three independent rounds. The Chiron report's "Round 1 standalone #1624" is superseded — #1624's deletion is unsafe except as the last step of the terminal cleanup, after the LLD PR has merged.
- **#1626 and #1627 stay independent and land first** (no dependency on the lifecycle decision).
- The orchestrator now performs a merge (the LLD PR) and blocks briefly at the end to do so. The LLD PR is simple (one doc, `No-Issue:` exemption), so Cerberus + pr-sentinel clear it quickly.
- **The impl PR is still human/Cerberus-merged, not auto-merged by the orchestrator.** Its branch is already pushed to origin in the `pr` stage, so the terminal stage may remove the impl *worktree* safely while leaving the impl *branch* (PR open) intact. Final impl-branch cleanup remains `/cleanup`'s job after that PR merges (#1556 stays valid for the impl side).
- Two PRs per orchestrated issue (LLD+spec PR, impl PR).

## Implementation sequence

Detailed per-issue steps live in the issues; summary order:

1. **#1626** — reports `post-finalize` checkpoint (independent).
2. **#1627** — suppress cp_docs for external repos via `skip_docs` (independent).
3. **State plumbing** — capture the LLD PR URL + `{N}-lld` worktree path into `OrchestrationState`.
4. **#1625** — spec rides the LLD PR (needs step 3).
5. **#1531 + #1624 + #1628** — the terminal `cleanup` stage (merge the LLD PR, delete redundant working-tree copies, remove worktrees), reusing `cleanup_helpers`.

## Fleet artifacts

Touched by the eventual implementation (not by this ADR): `orchestrator/{graph,stages,state}.py`, `requirements/nodes/finalize.py`, `implementation_spec/nodes/finalize_spec.py`, `testing/nodes/finalize.py` (or `testing/graph.py`), `testing/nodes/document.py` / `orchestrator/stages.py`. This ADR changes no code.
