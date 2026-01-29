# DN-001: Context Injection for Governance Workflows

**Status:** Proposed
**Date:** 2026-01-29
**Applies to:** LLD Workflow, future governance workflows

## Problem Statement

The issue workflow currently operates with minimal context - just an issue number or a brief file. For more complex workflows like LLD writing, the agent needs additional context:

- Reference implementations (e.g., how issue workflow was built)
- Related reports from similar work
- Code files that will be modified
- Recent commit history showing patterns
- Prior art from other projects

Without this context, the LLD writer produces generic output that misses project-specific patterns and conventions.

## Requirements

1. **Explicit context** - User can specify files/directories to include
2. **No RAG (yet)** - Keep it simple, avoid vector databases for now
3. **Composable** - Works with other flags like `--auto`, `--select`
4. **Inspectable** - User can see what context is being included

## Options Considered

### Option A: `--context` Flag (Recommended)

```bash
python tools/run_lld_workflow.py --issue 87 \
    --context tools/run_issue_workflow.py \
    --context docs/reports/done/82-implementation-report.md \
    --context docs/audit/done/governance-notes/
```

**Pros:**
- Simple to implement
- Familiar CLI pattern (multiple flags)
- User has full control
- Easy to debug

**Cons:**
- Verbose for many files
- No glob support (must list each file)

### Option B: Context Manifest File

```bash
python tools/run_lld_workflow.py --issue 87 --manifest context.yaml
```

Where `context.yaml`:
```yaml
issue: 87
context:
  - path: tools/run_issue_workflow.py
    label: "Reference implementation"
  - path: docs/reports/done/82-*.md
    label: "Recent reports"
    type: glob
  - path: git:HEAD~10..HEAD
    label: "Recent commits"
    type: git-log
```

**Pros:**
- Supports globs and special sources (git log)
- Reusable manifest files
- Can add metadata (labels, types)

**Cons:**
- More complex to implement
- Another file to manage
- Overkill for simple cases

### Option C: Convention-Based Discovery

```bash
python tools/run_lld_workflow.py --issue 87 --discover
```

Auto-discovers context from:
- `docs/context/{issue-id}/` directory
- Files mentioned in issue body
- Related issues mentioned in issue body

**Pros:**
- Zero configuration for common cases
- Encourages consistent project structure

**Cons:**
- Magic behavior harder to debug
- May include irrelevant files
- Requires strict conventions

## Recommendation

**Start with Option A (`--context` flag)**, with a path to Option B.

### Phase 1: Simple `--context` Flag

```python
# CLI arguments
parser.add_argument("--issue", required=True, help="GitHub issue number")
parser.add_argument("--context", action="append", default=[],
                    help="Additional context files/dirs (can specify multiple)")
parser.add_argument("--auto", action="store_true",
                    help="Auto mode: skip VS Code, auto-send to Gemini")
```

### Phase 2: Add Glob Support (Optional)

```python
parser.add_argument("--context", action="append", default=[],
                    help="Context files (supports globs: 'docs/**/*.md')")

# In processing:
from glob import glob
expanded = []
for pattern in args.context:
    matches = glob(pattern, recursive=True)
    expanded.extend(matches if matches else [pattern])
```

### Phase 3: Manifest File (Future)

Only if Phase 1/2 proves insufficient. Likely triggers:
- Need for git log injection
- Need for web URL fetching
- Complex multi-project context

## Implementation Sketch

### State Schema Addition

```python
class LLDWorkflowState(TypedDict, total=False):
    issue_number: int
    issue_body: str
    context_files: list[str]  # New field
    context_content: str      # Assembled context for prompt
    # ... existing fields
```

### Context Assembly Node

```python
def assemble_context(state: LLDWorkflowState) -> dict:
    """N0.5: Assemble context from provided files."""
    context_parts = []

    for ctx_path in state.get("context_files", []):
        path = Path(ctx_path)

        if path.is_file():
            content = path.read_text(encoding="utf-8", errors="replace")
            context_parts.append(f"## Reference: {path.name}\n\n```\n{content}\n```")

        elif path.is_dir():
            for f in sorted(path.iterdir()):
                if f.is_file() and f.suffix in (".md", ".py", ".json", ".yaml"):
                    content = f.read_text(encoding="utf-8", errors="replace")
                    context_parts.append(f"## Reference: {f.name}\n\n```\n{content}\n```")
        else:
            print(f"[WARN] Context path not found: {ctx_path}")

    return {"context_content": "\n\n".join(context_parts)}
```

### Prompt Integration

```python
def build_lld_prompt(state: LLDWorkflowState) -> str:
    prompt = f"""## Issue #{state['issue_number']}

{state['issue_body']}

"""

    if state.get("context_content"):
        prompt += f"""## Additional Context

The following files are provided as reference for patterns, conventions, and prior art:

{state['context_content']}

"""

    prompt += """## Task

Write a Low-Level Design document following the LLD template...
"""
    return prompt
```

## Enhancements from Issue Workflow to Port

The following features from the issue workflow should be ported to the LLD workflow:

| Feature | Issue Workflow | LLD Workflow Equivalent |
|---------|----------------|-------------------------|
| `--select` | Pick from `ideas/active/` | Pick from `docs/LLDs/drafts/` or existing issue LLDs |
| `--auto` | Skip VS Code, auto-Gemini | Same behavior |
| Source cleanup | Move idea to `ideas/done/` | Move draft to `LLDs/active/` after approval |
| Resume | `--resume` with SQLite checkpoint | Same pattern |
| Audit trail | `docs/audit/active/{slug}/` | `docs/audit/active/{issue-id}-lld/` |
| Turn limit prompt | Configurable recursion | Same pattern |
| Encrypted file detection | git-crypt awareness | Same pattern |

## Testing Strategy

1. **Unit tests** for context assembly node
2. **Integration test** verifying context appears in prompt
3. **Manual test** with real LLD generation comparing with/without context

## Open Questions

1. **Token limits** - What happens when context exceeds model limits?
   - Proposed: Warn user, truncate oldest context files first

2. **Binary files** - How to handle non-text files in context dirs?
   - Proposed: Skip with warning, only include known text extensions

3. **Sensitive content** - Should we scan for secrets in context?
   - Proposed: No, trust user to not include `.env` files

## References

- Issue #82: `--brief` cleanup fix (pattern for source file handling)
- Issue #75: `--auto` flag implementation
- `tools/run_issue_workflow.py`: Reference implementation
