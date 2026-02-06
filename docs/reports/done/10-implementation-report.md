# Implementation Report: Issue #10 - Unleashed PTY Wrapper

**Issue:** [#10](https://github.com/martymcenroe/AssemblyZero/issues/10)
**Branch:** `10-unleashed-pty-wrapper`
**Date:** 2026-01-14
**Status:** Implementation Complete

---

## Summary

Implemented a PTY wrapper (`unleashed.py`) that auto-approves Claude Code permission prompts after a configurable countdown, providing a dead man's switch for unattended operation.

---

## Files Created

| File | Lines | Description |
|------|-------|-------------|
| `tools/unleashed.py` | ~400 | Main PTY wrapper implementation |
| `tools/unleashed` | ~20 | Bash wrapper for PATH integration |
| `docs/skills/0603-unleashed.md` | ~200 | Full documentation |

---

## Design Decisions

### 1. PTY Library: winpty

Followed existing pattern from `claude-usage-scraper.py`. The `winpty` library provides:
- Full TUI fidelity with ANSI support
- Non-blocking reads via background thread
- Process lifecycle management

### 2. Threading Model

Three background threads:
- `PtyReader` - Non-blocking PTY output reading
- `InputReader` - Non-blocking keyboard input (msvcrt on Windows)
- Main loop - Coordinates state, overlay, and injection

### 3. Footer Detection

Regex pattern with flexible Unicode handling:
```python
FOOTER_PATTERN = re.compile(
    r'Esc to cancel[-·–—\s]+Tab to add additional instructions',
    re.IGNORECASE
)
```

Handles middle dot (·), en-dash (–), em-dash (—), and ASCII hyphen.

### 4. ANSI Overlay

Non-corrupting overlay using cursor save/restore:
```python
CURSOR_SAVE = '\x1b[s'
CURSOR_RESTORE = '\x1b[u'
CURSOR_HOME = '\x1b[H'
```

Overlay draws at top-left, restores cursor to prevent TUI corruption.

### 5. Cancel Detection

Only printable keys cancel the countdown:
```python
def is_printable_key(char: str) -> bool:
    return len(char) == 1 and (char.isprintable() or char in '\r\n\t')
```

This prevents accidental cancellation from modifier keys (Shift, Ctrl, Alt alone).

### 6. Logging Strategy

Dual logging approach:
- **Raw log** (`*.log`) - Full byte stream for debugging
- **Event log** (`*.jsonl`) - Structured events for auditing

Screen context captured on footer detection for audit trail.

---

## Deviations from Issue Spec

### 1. Horizontal Rule Detection (Deferred)

The issue mentioned optional secondary validation using `─` (U+2500) horizontal rule. This was **not implemented** for MVP since footer detection alone is sufficient and more reliable.

### 2. Modifier Key Detection (Simplified)

Rather than explicitly detecting Shift/Ctrl/Alt alone, the implementation uses `is_printable_key()` which naturally excludes non-printable characters. Same effect, simpler code.

### 3. Window Resize Events (Not Implemented)

The issue mentioned handling window resize events. The current implementation uses initial terminal size but does not dynamically resize. This is acceptable for typical usage where terminal size is stable.

---

## Architecture

```
User Input ──▶ InputReader ──┬──▶ Unleashed ──▶ PTY Process
                             │       │              │
                             │       ▼              ▼
                             │  Footer Check   PtyReader
                             │       │              │
                             │       ▼              ▼
                             └─▶ Countdown ◀── stdout display
                                    │
                                    ▼
                               EventLogger
```

---

## Key Code Sections

### Footer Detection (`unleashed.py:190-193`)
```python
def _detect_footer(self, text: str) -> bool:
    clean_text = strip_ansi(text)
    return bool(FOOTER_PATTERN.search(clean_text))
```

### Countdown Loop (`unleashed.py:207-246`)
```python
for remaining in range(self.delay, 0, -1):
    self.overlay.show(remaining)
    # Check for user input during this second
    start = time.time()
    while time.time() - start < 1.0:
        user_input = self.input_reader.read_nowait()
        if user_input:
            for char in user_input:
                if is_printable_key(char):
                    # User cancelled
                    ...
```

### Auto-Inject (`unleashed.py:257-260`)
```python
if not self.dry_run:
    if self.pty_process and self.pty_process.isalive():
        self.pty_process.write('\r')
    self.logger.log_event("AUTO_APPROVED", context=screen_context[:500])
```

---

## Dependencies

No new dependencies added. Uses existing `pywinpty` from `pyproject.toml`.

---

## Testing Notes

Test with `--dry-run` to verify detection without injection:
```bash
unleashed --dry-run
```

See `test-report.md` for full test scenarios and results.

---

## Related Documentation

- Skill documentation: `docs/skills/0603-unleashed.md`
- Test report: `docs/reports/10/test-report.md`
