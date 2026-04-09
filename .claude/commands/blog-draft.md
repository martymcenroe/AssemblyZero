---
description: Create a blog draft in dispatch repo from any project
argument-hint: "\"Title of the post\""
scope: global
---

# Blog Draft

Create a blog post draft in the dispatch repo, stamped with the source project.

## Usage

```
/blog-draft "My Amazing Discovery"
/blog-draft "How I Fixed the Bug"
```

## Execution

### Step 1: Extract Context

1. Get the **source project** from the current working directory:
   - Extract project name from path (e.g., `/c/Users/mcwiz/Projects/AssemblyZero` → `AssemblyZero`)

2. Get **today's date** in YYYY-MM-DD format

3. Generate **slug** from the title:
   - Lowercase, replace spaces with hyphens, remove special characters
   - Example: "My Amazing Discovery" → "my-amazing-discovery"

### Step 2: Create Draft File

**Location:** `C:\Users\mcwiz\Projects\dispatch\drafts\{date}-{slug}-from-{project}.md`

**Template:**

```markdown
---
title: "{title}"
source_project: {project}
created: {date}
status: draft
tags: []
---

# {title}

*[Opening hook - what's the problem or insight?]*

---

## The Context

[What were you working on? What led to this?]

## The Discovery/Solution

[The meat of the post - what did you learn or build?]

## Why It Matters

[So what? Why should readers care?]

## Try It Yourself

[If applicable - how can readers use this?]

---

*Built with Claude Opus 4.5. Source: {project}*
```

### Step 3: Report

After creating the file, report:
- Full path to the draft
- Suggested next steps (fill in sections, run `/blog-review` when ready)

## Notes

- Drafts are **not committed** until explicitly requested
- The dispatch repo has a `STYLE-GUIDE.md` - read it if tone guidance is needed
- Use `/blog-review` in dispatch to get AI feedback on drafts
