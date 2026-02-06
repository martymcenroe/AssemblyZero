# Coding Standards & Operational Procedures

Generic coding standards for AI-assisted development. Projects may extend with project-specific rules.

## 1. Prime Directives for AI Agents

* **Plan Before Execute:** Discuss multi-step plans with the Orchestrator BEFORE running commands. Never batch destructive operations without explicit approval.
* **Root-Relative Paths:** Always generate file paths relative to the project root.
* **Explicit Handoff:** At the end of every code generation turn, provide a "Verification Block".
* **Protocol Adherence:** Follow the Orchestration Protocol defined in your project's documentation.

## 2. Forbidden Commands (NEVER USE)

AI agents must NEVER use these commands under ANY circumstances:

| Command | Why Forbidden | Use Instead |
|:--------|:--------------|:------------|
| `git reset --hard` | Destroys commit history, irrecoverable | `git revert <commit>` to undo safely |
| `git reset HEAD~N` | Rewrites history on shared branches | `git revert` for published commits |
| `git push --force` | Overwrites remote history, breaks collaboration | `git push --force-with-lease` (with approval) |
| `git clean -fd` | Permanently deletes untracked files | `git status` first, then `git clean -n` (dry run) |
| `pip install` | Bypasses dependency lock file | `poetry add <package>` |
| `pip freeze` | Creates requirements.txt instead of lock | `poetry export` if needed |

**Rationale:**
- **History Rewriting:** Git reset rewrites commit history. Once pushed, this breaks other developers' branches.
- **Data Loss:** Git reset --hard and git clean -fd permanently delete uncommitted work.
- **Dependency Chaos:** pip install modifies site-packages without updating lock files.

**The Golden Rule:** If you need to undo a pushed commit, use `git revert`. It preserves history.

## 3. Python Development

* **Dependency Management:** Use `poetry add <package>`. NEVER use `pip install` directly.
* **Linting:** Follow PEP 8.
* **Type Hinting:** Required for all function signatures.

## 4. Git Workflow ("The Flip Turn")

1. **Issue:** Discovery (`gh issue list`).
2. **Worktree:** Isolation (`git worktree add ../Project-{IssueID} -b {IssueID}-short-desc`).
3. **Edit:** Implementation.
4. **Stage:** Preparation (`git add`).
5. **Commit:** Conventional (`type: desc (ref #ID)`).
6. **Push:** Team Visibility (`git push -u origin HEAD`). REQUIRED.
7. **PR:** Review (`gh pr create`).
8. **Merge:** Finalize.
9. **Cleanup:** Remove worktree and delete branches.

## 5. Documentation

* **Update First:** Update the relevant `docs/` file *before* writing code.
* **Lessons Learned:** Log new discoveries in lessons-learned file.

## 6. Naming Conventions

### 6.1 Branch Naming
Format: `{IssueID}-short-description`

| Example | Correct |
|:--------|:--------|
| Issue #25 → Auth gate | `25-auth-gate` ✅ |
| ~~`feature/auth-gate-issue-25`~~ | ❌ Too verbose |
| ~~`feat/wire-engine`~~ | ❌ Missing issue ID |

### 6.2 Commit Message Format
Format: `type: description (KEYWORD #ID)`

Types: `feat`, `fix`, `docs`, `chore`, `test`, `refactor`

**Issue Keywords:**
* **`ref #ID`:** Commit contributes to issue, work is in-progress.
* **`close #ID`:** Issue's "Definition of Done" is fully met.

### 6.3 Testing Before Closing
**CRITICAL:** AI agents must NEVER close an issue until human testing is complete.

1. AI agent commits with `(ref #ID)`
2. AI agent reports completion
3. User tests the implementation
4. User confirms results
5. **ONLY THEN** may the issue be closed

## 7. Documentation Standards

### 7.1 Link Formatting
* **Relative Paths Only:** All internal links use relative paths.
* **No Search URLs:** Don't wrap file references in search engine URLs.

### 7.2 The Inventory Rule
* Every project should maintain a file inventory as source of truth.
* Add new files to inventory immediately upon creation.

### 7.3 The Legacy Protocol
To keep docs folder focused on active truth, archive outdated files:

1. **Move:** `git mv docs/old-spec.md docs/legacy/`
2. **Update:** Change inventory status to Legacy.

### 7.4 Log File Formatting
* **Line Length:** 100 characters maximum per line.
* **URLs:** Use markdown link syntax, never bare URLs.
* **Tables:** Maximum 5-6 columns with abbreviated headers.

## 8. Git Worktree Protocols

### 8.1 The "Parallel Universe" Model
Use `git worktree` to maintain isolated environments for different features.

```text
Projects/
├── MyProject/              # Main Worktree - always on 'main'
├── MyProject-95-feature/   # Linked Worktree
└── MyProject-80-bugfix/    # Linked Worktree
```

### 8.2 The Golden Rule
**You cannot check out the same branch in two worktrees simultaneously.**

* **To update:** Don't checkout main. Run `git fetch origin main` and `git merge origin/main`.
* **To browse:** Open a separate terminal in the main folder.

### 8.3 Common Commands
* **Create:** `git worktree add ../Project-99-feature -b feature/99-name`
* **List:** `git worktree list`
* **Remove:** `git worktree remove ../Project-99-feature`

---

*Source: AssemblyZero/docs/standards/coding-standards.md*
*Project-specific extensions may exist in project's local documentation.*
