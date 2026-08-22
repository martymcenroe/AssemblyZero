# Runbook 0953 — Renaming a repository

**Audience:** operator, with agent assistance where noted.
**When:** any time a repository's name changes on GitHub.
**Why it exists:** the rename itself is easy. Everything that referenced the old
name by absolute path is not, and it fails silently.

---

## 0. Read this first

GitHub is thorough about its half. After a rename it redirects the old
`owner/name` indefinitely: remotes keep working, clone URLs keep working, `gh`
calls keep working, the web UI keeps working.

**That redirect is the hazard.** Nothing breaks loudly, so nothing prompts the
follow-through. A rename can look complete for months while the local side has
never been touched at all.

What the redirect does not cover is every absolute filesystem path that named the
old directory. Those live in agent configuration, and agent configuration fails
**open** — a hook whose `command` points at a deleted script does not error, it
simply never runs, while the config still reads as protected.

One prior rename left 17 files across 11 locations pointing at a directory that
no longer existed, including a `PreToolUse` safety hook that failed open for
months before anyone noticed.

**A rename is a fleet event, not a local one.** Other repositories reference the
renamed one by absolute path. Step 3 is the half that gets missed.

---

## 1. GitHub side

1. Rename in **Settings → General → Repository name**.
2. Confirm the redirect is live:

   ```bash
   gh api repos/<owner>/<OLD-NAME> --jq .name
   ```

   This should print the **new** name. If it prints the old name, the rename did
   not happen. If it 404s, something other than a rename occurred — stop and
   find out what.

3. Note both names. You need the old one for the sweep in step 3.

---

## 2. Local directory and git remotes

The directory on disk does **not** follow the rename, and neither does `origin`.

1. Close any editor or terminal sitting in the directory. A held handle makes the
   rename fail on Windows in ways that are hard to read.

2. Check for uncommitted work **before** moving anything:

   ```bash
   git -C <old-dir> status --short
   git -C <old-dir> worktree list
   ```

   Commit or deliberately preserve anything dirty first. Do not proceed with a
   plan to sort it out afterwards.

3. Rename the directory to match the new repo name.

4. Update the remote so it stops relying on the redirect:

   ```bash
   git -C <new-dir> remote set-url origin https://github.com/<owner>/<NEW-NAME>.git
   git -C <new-dir> remote -v
   ```

5. **Worktrees.** Every worktree cut from the old directory records an absolute
   path to it and to its `.git` directory. They do not follow either. From the
   renamed directory:

   ```bash
   git -C <new-dir> worktree list
   git -C <new-dir> worktree repair
   ```

   `worktree repair` fixes the links in both directions. Re-run `worktree list`
   afterwards and confirm every entry resolves.

---

## 3. Config sweep — the half that gets missed

Two passes. The first covers the renamed repo; the second covers every other
repo that named it.

### 3a. Surfaces inside the renamed repo

| file | what carries a path |
|---|---|
| `.claude/project.json` | `inherit_from`, `TOOLS_DIR`, `PROJECT_ROOT`, `PROJECT_NAME` |
| `.claude/settings.json` | hook `command` paths — **fail open, no error** |
| `.claude/settings.local.json` | permission entries naming absolute paths |
| `.claude/commands/*.md` | invocation examples with hard-coded tool paths |
| `.claude/tools/*` | generated scripts embedding the old directory |
| `.gemini/**`, `GEMINI.md` | the same class of reference |
| `CLAUDE.md` | worktree patterns, project root, tooling paths |

**`.gemini` is not optional.** Renames get done at the GitHub level without the
local `.claude` / `.gemini` side being touched at all — that is the recurring
failure this runbook exists to stop. A repo can carry both; sweep both.

### 3b. Every other repo that referenced the old name

This is a fleet-wide grep, not a per-repo one. A reference to the renamed repo
can sit in any other repo's `.claude/` or `.gemini/` config.

### 3c. Scheduled tasks

Any task whose action path names the old directory. Enumerate with
`Get-ScheduledTask` and resolve each action through its launcher chain — a `.vbs`
wrapper calling a `.ps1` calling a repo script hides the path two levels down.

---

## 4. Verification — runnable, not a read-through

A checklist nobody re-runs proves the state of one moment. Run the detector:

```bash
poetry run python tools/rename_rot_detect.py
```

It reports two things and exits non-zero while either is non-empty:

- **renamed remotes** — a checkout whose `origin` resolves to a different name
- **dead paths** — an absolute `Projects/<name>` in agent config where `<name>`
  is not present on disk

It is deliberately generalized: it does not know which rename produced a finding,
so it covers the next one too. Read-only; it reports and a human decides.

The rename is not finished until this run is clean, or until every remaining
finding is one you have looked at and accepted.

---

## 5. Hook verification — parsing is not firing

A `settings.json` that parses proves nothing. A hook whose `command` points at a
deleted path is syntactically perfect and completely inert, and that is exactly
how the last failure went unnoticed.

After the sweep, confirm each registered hook **actually fires**: trigger the
condition it guards and observe the denial or the log line. If a hook is meant to
block something, try the thing and watch it get blocked.

An untested hook after a rename should be assumed dead.

---

## 6. Definition of done

- [ ] `gh api repos/<owner>/<OLD-NAME> --jq .name` prints the new name
- [ ] directory renamed; `origin` updated to the new URL, not relying on redirect
- [ ] `git worktree list` resolves for every entry after `worktree repair`
- [ ] config swept inside the renamed repo, `.claude` **and** `.gemini`
- [ ] config swept across every other repo referencing the old name
- [ ] scheduled tasks checked, launcher chains resolved
- [ ] detector run and clean, or every finding explicitly accepted
- [ ] each registered hook observed firing, not merely present

---

## Notes

**Wikis rename too.** A repository's wiki is a separate git repository at
`<name>.wiki`. A local wiki checkout carries its own remote and does not follow
the rename.

**Case-only renames still count.** Changing capitalisation is a rename to GitHub
and produces the same redirect, while Windows treats the path as unchanged. The
mismatch is invisible locally and real in `origin`.

**The old name lives on in prose.** Runbooks, ADRs and issue bodies naming the
old repo are not covered here. They are documentation debt rather than breakage,
and rewriting historical records is usually the wrong call — but be aware that a
search for the new name will not find them.
