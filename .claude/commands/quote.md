---
description: Memorialize a Discworld quote to Claude's World wiki
allowed-tools: Bash, Read, Edit
scope: global
---

# Quote Memorialization

When the user invokes `/quote`, you should find and memorialize the most recent Discworld-inspired quote from this conversation.

## Step 1: Find the Quote

Look back through the last 1-3 turns of conversation for a Discworld-style quote. These typically appear as:
- Blockquoted text with Discworld character attribution
- Pratchett-style philosophical observations
- In-character statements from Discworld personas (Vetinari, Vimes, DEATH, etc.)

Extract:
- **QUOTE**: The quoted text itself
- **OCCASION**: A brief description of what prompted it (e.g., "On completing the migration")
- **CONTEXT**: The fuller context of what was happening when the quote was offered
- **SOURCE**: If it's a direct Pratchett quote, the book title (e.g., "Lords and Ladies")

If no quote is found in recent turns, inform the user.

## IMPORTANT: Naming Convention

On Claude's World wiki, **never** refer to the human as "the user", "the human", or "the orchestrator".

**The human is "The Great God Om"** — the source of Intent who is carried by Brutha (the RAG system).

The first mention of "The Great God Om" on Claude's World links to a hidden page: `[The Great God Om](The-Great-God-Om)`

Subsequent mentions can just say "Om" without the link.

## Step 2: Get Accurate Timestamp

Run this command to get the current system time:
```bash
powershell -Command "Get-Date -Format 'yyyy-MM-dd HH:mm'"
```

Parse the output into DATE (yyyy-MM-dd) and TIME (HH:mm).

## Step 3: Read Current Wiki

Read: `C:\Users\mcwiz\Projects\AssemblyZero\wiki\Claudes-World.md`

## Step 4: Check Date Section

- If a section `### {DATE}` already exists, append the new entry to that section
- If not, create a new date section before `## About This Page`

## Step 5: Format Quote Entry

**For direct Pratchett quotes (with SOURCE):**
```markdown
---

**{TIME}** — *{OCCASION}*
> "{QUOTE}"

*— Terry Pratchett, {SOURCE}*

**Context:** {CONTEXT}
```

**For in-character quotes (no SOURCE):**
```markdown
---

**{TIME}** — *{OCCASION}*
> "{QUOTE}"

**Context:** {CONTEXT}
```

## Step 6: Update Wiki File

Use Edit tool to insert the new entry before `## About This Page`.

## Step 7: Commit to AssemblyZero

```bash
git -C /c/Users/mcwiz/Projects/AssemblyZero add wiki/Claudes-World.md
```

```bash
git -C /c/Users/mcwiz/Projects/AssemblyZero commit -m "docs(wiki): add quote to Claude's World"
```

```bash
git -C /c/Users/mcwiz/Projects/AssemblyZero push
```

## Step 8: Sync Wiki Repo

```bash
cp /c/Users/mcwiz/Projects/AssemblyZero/wiki/Claudes-World.md /c/Users/mcwiz/Projects/AssemblyZero.wiki/
```

```bash
cp /c/Users/mcwiz/Projects/AssemblyZero/wiki/The-Great-God-Om.md /c/Users/mcwiz/Projects/AssemblyZero.wiki/
```

```bash
git -C /c/Users/mcwiz/Projects/AssemblyZero.wiki add Claudes-World.md The-Great-God-Om.md
```

```bash
git -C /c/Users/mcwiz/Projects/AssemblyZero.wiki commit -m "sync: add quote"
```

```bash
git -C /c/Users/mcwiz/Projects/AssemblyZero.wiki push
```

## Step 9: Confirm

Tell the user: "Quote memorialized to Claude's World wiki."
