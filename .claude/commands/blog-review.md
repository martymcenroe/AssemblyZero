---
description: Run Gemini 3 review on a blog draft
argument-hint: "<draft-path>"
scope: global
---

# Blog Review

Run AI-powered review on a blog draft using Gemini 3 Pro Preview.

## Usage

```
/blog-review drafts/2026-01-14-unleashed-from-AssemblyZero.md
/blog-review C:\Users\mcwiz\Projects\dispatch\drafts\my-post.md
```

## Execution

### Step 1: Locate the Draft

If the path is relative, resolve it from:
1. Current working directory
2. `C:\Users\mcwiz\Projects\dispatch\` (dispatch repo)

Read the draft file and extract:
- **Title**: From frontmatter `title:` field, or first `# ` heading
- **Content**: The full markdown content

### Step 2: Build the Review Prompt

Read the prompt template from:
`C:\Users\mcwiz\Projects\dispatch\.claude\gemini-prompts\blog-review.txt`

Replace placeholders:
- `{{TITLE}}` → extracted title
- `{{BLOG_CONTENT}}` → full draft content

### Step 3: Write Temporary Prompt File

Write the expanded prompt to a temp file in the scratchpad directory.

### Step 4: Run Gemini Review

Execute:
```bash
poetry run --directory /c/Users/mcwiz/Projects/AssemblyZero python /c/Users/mcwiz/Projects/AssemblyZero/tools/gemini-retry.py --prompt-file /path/to/temp-prompt.txt
```

### Step 5: Display Results

Show the Gemini response which includes:
- **Overall Assessment**: Ready to publish? Strongest element? What needs work?
- **[BLOCKING] Issues**: Must fix before publication
- **[HIGH] Priority Issues**: Should fix before publication
- **[SUGGESTION] Improvements**: Nice to have
- **Employment Showcase Score**: 1-10 rating
- **Recommended Next Steps**

### Step 6: Cleanup

Delete the temporary prompt file.

## Notes

- Uses Gemini 3 Pro Preview for deep reasoning
- Review takes 30-60 seconds depending on draft length
- If quota is exhausted, gemini-retry.py will rotate credentials automatically
- The review prompt is optimized for employment showcase blog posts

## Error Handling

If the draft file doesn't exist, report the error and suggest checking the path.

If Gemini fails after all retries, report the failure and suggest trying again later.
