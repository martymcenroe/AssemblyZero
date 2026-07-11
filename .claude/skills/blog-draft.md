---
description: Create a blog draft in dispatch repo from any project
argument-hint: "\"Title of the post\""
scope: global
---

# Blog Draft

Create a blog post draft in the dispatch repo, stamped with the source project.

**This skill is a thin wrapper.** All deterministic work — project-anchor
detection, date stamping, Windows-safe slug generation, model attribution from
config, filename collision guard, template scaffolding — lives in tested Python
(`blog_draft.py`, 36 tests). The skill runs the script and reports; it does NOT
re-implement any of that logic in prose. If the scaffold ever looks wrong, fix
the script, not this file.

## Usage

```
/blog-draft "My Amazing Discovery"
/blog-draft "How I Fixed the Bug"
```

## Execution

### Step 1: Run the scaffolder

```bash
(cd /c/Users/mcwiz/Projects/unleashed && poetry run python src/blog_draft.py \
  --title "{TITLE}" \
  --project-path "{CURRENT_PROJECT_ROOT}")
```

`{CURRENT_PROJECT_ROOT}` is the repo you are working in (the script anchors the
draft's `source_project` to it). The script prints the created draft's full
path; on a filename collision it refuses rather than overwriting — report that
to the user instead of working around it.

### Step 2: Report

- Full path to the created draft (clickable link + plain path per house style).
- Suggested next steps: fill in the scaffold's sections, run `/blog-review` in
  dispatch when ready.

## Notes

- Drafts are **not committed** until explicitly requested.
- The dispatch repo has a `STYLE-GUIDE.md` — read it if tone guidance is needed.
- `--dry-run` previews without writing; `--date` overrides the stamp if the
  user asks for a specific date.
