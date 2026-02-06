# Wiki Alignment Audit

## Purpose

Verify that GitHub Wiki content matches repository documentation. Catches:
- Wiki pages that are out of sync with repo docs
- Broken links between wiki and repo
- Missing wiki pages for key docs

## Trigger

- Weekly (part of full cleanup)
- After major documentation updates
- When wiki structure changes

## Procedure

### Step 1: List Wiki Pages

```bash
# Clone wiki repo
git clone https://github.com/{{GITHUB_REPO}}.wiki.git /tmp/wiki

# List wiki pages
ls /tmp/wiki/*.md
```

### Step 2: Compare with Repo Docs

For each wiki page, check if corresponding repo doc exists:

```bash
# For each wiki page, find matching repo doc
for wiki_page in /tmp/wiki/*.md; do
  basename=$(basename "$wiki_page" .md)

  # Check if matching doc exists
  find docs -name "*$basename*" -type f
done
```

### Step 3: Check for Staleness

Compare modification dates:

```bash
# Wiki last modified
git -C /tmp/wiki log -1 --format="%ci" -- "Page.md"

# Repo doc last modified
git log -1 --format="%ci" -- "docs/page.md"
```

### Step 4: Check Links

Verify links in wiki point to valid repo locations:

```bash
# Extract links from wiki page
grep -oP '\[.*?\]\(.*?\)' /tmp/wiki/Page.md

# Check if targets exist
```

### Step 5: Remediation

| Finding | Action |
|---------|--------|
| Wiki older than repo | Update wiki from repo |
| Wiki newer than repo | Review - wiki may have updates to merge |
| Broken links | Fix links in wiki |
| Missing wiki page | Create page if needed for discoverability |

## Output Format

```markdown
## Wiki Alignment Audit - {DATE}

### Summary
- Wiki pages checked: {N}
- In sync: {N}
- Stale: {N}
- Missing: {N}

### Alignment Status
| Wiki Page | Repo Doc | Status | Last Wiki | Last Repo |
|-----------|----------|--------|-----------|-----------|
| Home | README.md | ✅ Sync | Jan 10 | Jan 10 |
| Setup | docs/setup.md | ⚠️ Stale | Dec 15 | Jan 5 |

### Actions Taken
- Updated {N} wiki pages
- Fixed {N} broken links
- Created {N} new pages

### Remaining Issues
| Issue | Notes |
|-------|-------|
| Wiki/Feature.md | No corresponding repo doc |
```

---

*Template from: AssemblyZero/.claude/templates/docs/wiki-alignment-audit.md*
