"""
transcript_filters.py — Shared garbage pattern matching for PTY transcripts.

Single source of truth for TUI garbage detection. Used by:
- clean_transcript.py (post-session cleaning)

95 compiled regex patterns covering spinners, timing fragments, permission UI,
status bars, agent trees, checklist repaints, CLI help, and garbled TUI artifacts.

Origin: propagated from a private fleet tool via Issue #361.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from assemblyzero.core.projects_root import spellings

# #3609: the Projects root as a transcript spells it, derived, never written out.
_ROOT = spellings()


# --- Compiled patterns (order matters — most frequent first) ---
GARBAGE_PATTERNS = [
    # 1. GENERIC spinner pattern: spinner char(s) + Capitalized verb + optional words + …
    re.compile(
        r'^[\s*·✶✻✽✢●◼❯⏵▐▝▘☵⎿]*\s*'
        r"[A-Z][a-zéèêë'-]+(?:ing|ed|ion|ting|in')\b.*…"
    ),
    re.compile(
        r'^[\s*·✶✻✽✢●◼❯⏵▐▝▘☵⎿]*\s*'
        r"[A-Z][a-zéèêë'-]+(?:ing|ed|ion|ting|in')…?\s*\d*\s*$"
    ),
    re.compile(
        r'^[\s*·✶✻✽✢●◼❯⏵▐▝▘☵⎿]*\s*'
        r'(?:Auto-updating|Pasting\s*text)'
    ),

    # 2. Character-by-character thinking fragments
    re.compile(r'^[\s*·✶✻✽✢]*\s*.{0,10}\s+\(?thinking\)?\s*\)?$'),
    re.compile(r'.{0,6}\(thinking\)\s*$'),

    # 3. Status bar timestamps
    re.compile(r'^\[?\d{2}-\d{2}\s*\d{2}:\d{2}:\d{2}\]?\s+'),

    # 4. Auto-update failed line
    re.compile(r'✗\s*Auto-?update\s*failed'),
    re.compile(r'Auto-?update\s*failed\s*·\s*Try'),

    # 5. Accept edits chrome
    re.compile(r'^⏵+\s*accept\s*edits?\s*on', re.IGNORECASE),
    re.compile(r'⏵+\s*accepteditson', re.IGNORECASE),

    # 6. Permission prompt UI lines
    re.compile(r'^>>>\s*\[PERMISSION\]'),
    re.compile(r'Esc\s*to\s*cancel\s*·'),
    re.compile(r'Esctocancel'),
    re.compile(r'^\s*❯\s*\d+\.\s*(?:Yes|No)'),
    re.compile(r'^\s*\d+\.\s*(?:Yes|No)\s*$'),
    re.compile(r'Do\s*you\s*want\s*to\s*proceed\s*\?'),
    re.compile(r'Doyouwanttoproceed'),

    # 7. Claude Code ASCII logo
    re.compile(r'^[\s▐▝▜▛█▘]*[▐▝▜▛█▘]{3,}'),

    # 8. Ctrl hints
    re.compile(r'^\s*ctrl\+[a-z]\s+to\s+\w+', re.IGNORECASE),

    # 9. Token/timing-only fragments
    re.compile(r'^\s*[\s·✶✻✽✢*]*\s*\d*\.?\d*k?\s*(?:tokens|↑|↓)'),
    re.compile(r'^\s*[\d\s·↑↓]+(?:tokens|thinking)\s*\)?$'),
    re.compile(r'^\s*[\s·✶✻✽✢*]*\d+\s+0?s\s*·\s*[↑↓]'),
    re.compile(r'^\s*\d+\s+·\s+\d+\.?\d*k?\s+tokens'),

    # 10. Bare timing fragments
    re.compile(r'^\s*[\(·]\s*\d+s\s*·\s*(?:timeout|↑|↓)'),
    re.compile(r'^[\s*·✶✻✽✢]*\s*\(?\s*thought for \d+s\)?\s*$'),

    # 11. Press up / image tags / Wait
    re.compile(r'Press\s*up\s*to\s*edit\s*queued'),
    re.compile(r'Pressuptoeditqueued'),
    re.compile(r'^\s*\[Image #\d+\]\s*(?:\(↑ to select\))?\s*$'),
    re.compile(r'^\s*⎿\s*\[Image #\d+\]'),
    re.compile(r'^Wait$'),

    # 12. Path-only status lines
    re.compile(
        r'^(?:s/|' + re.escape(_ROOT["git_bash"]) + '/|' + re.escape(_ROOT["wsl"]) + r'/)'
        r'\S+\s*(?:\(main\)\s*)?.{0,5}$'
    ),
    re.compile(r'^\s*~\\Projects\\\S+\s*.{0,5}$'),
    re.compile('^' + re.escape(_ROOT["windows"]) + r'\\\S+\s*.{0,5}$'),

    # 13. Running N agents lines
    re.compile(r'^Running\s+\d+\s+Bash\s+ag[ne]+ts'),

    # 14. Wrangler boilerplate
    re.compile(r'^⛅️\s*wrangler\s*\d'),
    re.compile(r'^🌀\s*(?:Executing on|To execute on)'),
    re.compile(r'^Resource\s*location:\s*remote$'),

    # 15. Orphan spinner/timing lines
    re.compile(r'^[\s*·✶✻✽✢]*\s*\d{1,3}\s*$'),

    # 16. Bare "Bash command" label
    re.compile(r'^Bash\s+command\s*$'),

    # 17. Partial spinner word (truncated repaints)
    re.compile(r'^[a-z]perspacing'),

    # 18. Token count fragments with thought
    re.compile(r'^\s*[\s·✶✻✽✢*]*\s*\d+\.?\d*k?\s*tokens\s*·\s*thought'),

    # 19. "↑ to select" standalone
    re.compile(r'^\s*\(?↑\s*to\s*select\)?\s*$'),

    # 20. Lines that are ONLY timing
    re.compile(r'^\s*⎿?\s*\((?:timeout\s*\d+\w?s?|\d+s\s*·\s*time\s*o[tu]+\s*\d+\w?s?)\)\s*$'),

    # 21. Plan mode chrome
    re.compile(r'^⏸\s*plan\s*mode\s*on'),
    re.compile(r'^⏸planmodeon'),
    re.compile(r'^●?\s*Entered plan mode'),
    re.compile(r'^Claude is now exploring and designing'),

    # 22. "Worked for Nm Ns" summary
    re.compile(r'^[\s*·✶✻✽✢]*\s*Worked for \d+'),

    # 23. Agent tree lines
    re.compile(r'^[├│└─]+\s(?!.*\w+.*│)'),

    # 24. Done summary
    re.compile(r'^⎿\s*Done\s*\('),

    # 25. Garbled repaints
    re.compile(r'^[A-Z]\s+[a-z]{1,3}\('),
    re.compile(r'^\d+[a-z].*\.sql\)?\s*$'),
    re.compile(r'^\d+\s+more\s+to[lo]*\s+uses'),

    # 27. Partial/bare path fragments
    re.compile(r'^s/\w+\s*\(main\)\s*$'),

    # 28. Generic spinner+timing
    re.compile(r'^[\s*·✶✻✽✢]+.*\(\d+[ms]?\s*\d*s?\s*·\s*[↑↓]'),

    # 29. Bare timing with "tokens"
    re.compile(r'^\s*\d+m?\s*\d*s?\s*·?\s*[↑↓]\s*\d'),

    # 30-31. Checklist repaints
    re.compile(r'^◻\s*(?:Remove|Add|Update|Create)'),
    re.compile(r'^◼\s*(?:Remove|Add|Update|Create)'),

    # 32. Standalone "(ctrl+o to expand)"
    re.compile(r'^\s*\(ctrl\+o\s*to\s*(?:expand|see)'),

    # 33. Bare arrow lines
    re.compile(r'^\s*[↑↓]\s*$'),

    # 35. Bare status line fragments
    re.compile(r'^\s*\+\d+\s+more\s+tool\s+uses'),

    # 36. Permission auto-approve artifacts
    re.compile(r'^\s*\d+\.\s*Yes\s*,?\s*and\s*don'),
    re.compile(r"don'taskagain"),

    # 37. Bare spinner characters
    re.compile(r'^[\s*·✶✻✽✢●]+\s*$'),

    # 38. "Waiting…"
    re.compile(r'^Waiting…'),

    # 39. Activity summary
    re.compile(r'^[\s*·✶✻✽✢]*\s*[A-Z][a-zéèêë]+(?:ed|éed)\s*for\s*\d'),
    re.compile(r'^[\s*·✶✻✽✢]*\s*[A-Z][a-zéèêë]+(?:edfor|éedfor)\d'),

    # 40. ANSI color code fragments
    re.compile(r'^\s*;?\d+m\s'),
    re.compile(r'^255;255;255m\s'),

    # 41. "Reading N file(s)…"
    re.compile(r'^Reading\s*\d+\s*file'),

    # 42. Short garbled fragments
    re.compile(r'^\s*[\s●⎿]*\s*\d+\s+(?:s…|files?\s*\(ctrl)'),

    # 43. Garbled truncated checklist repaints
    re.compile(r'^Create\s+[a-z]*cruiters?\s+m[a-z]*gration'),
    re.compile(r'^Create\s+firs-'),
    re.compile(r'^name-extractor\.js\s*\+'),

    # 44. Garbled tool result
    re.compile(r'^⎿\s+\w+\s+follow-up\s+cr\b'),

    # 45. Timing with garbled text
    re.compile(r'^[\s*·✶✻✽✢]*\s*\w{0,5}\s+\d+\s*0?s\s*·\s*[↑↓]'),

    # 46. Truncated spinner words
    re.compile(r'^Hatch\s+…'),

    # 47. Ultra-short fragment lines
    re.compile(r'^\d+\s+s?…'),

    # 48. Mid-word fragments
    re.compile(r'^[a-z]\s+\w{1,3}\s+the\s+\w+\.\s*$'),

    # 49. Checklist items with › blocked by
    re.compile(r'^◻?\s*Wire\s.*›\s*blocked\s*by'),

    # 50. ⎿ lines with partial checklist content
    re.compile(r'^⎿\s+(?:◼|◻)?\s*(?:Create|Wire|Add|Remove|Update)\s+\w'),

    # 51. Repeated checklist lines
    re.compile(r'^[◼◻✔]\s+(?:Deploy|Wire|Create|Add|Remove|Update|Run|Verify)'),
    re.compile(r'^⎿\s+[◼◻✔]\s+'),

    # 52. "ctrl+o to expand/see all" markers
    re.compile(r'ctrl\+o\s*to\s*(?:expand|see)'),

    # 53. Very short garbled fragments
    re.compile(r'^[\s*·✶✻✽✢]*\s*[a-z]{1,2}\s+[a-z]{1,3}\s*\d*\s*$'),

    # 54. "Running in the background"
    re.compile(r'Running in the background'),

    # 55. Truncated UI hints
    re.compile(r'shift\+tab\s+to\s+cyc'),

    # 56. "Tab to amend"
    re.compile(r'^[\s*·✶✻✽✢]*\s*Tab\s+to\s+amend'),

    # 57. Word-merged task descriptions
    re.compile(r'^[A-Z][a-z]+[A-Z][a-z]+[A-Z][a-z]+\w{10,}$'),

    # 58. Thought fragments
    re.compile(r'^\s*[\s*·✶✻✽✢]*\s*\w{0,6}ought\s+for\s+\d+s?\)'),

    # 59. Garbled spinner fragments with timing
    re.compile(r'^[\s*·✶✻✽✢]+[A-Z]?\s*[a-z]?\s+\d+s\s*·\s*[↑↓]'),

    # 60. Standalone "running N file…"
    re.compile(r'^running\s+\d+\s+file'),

    # 61. Bare timing
    re.compile(r'^\s*\d+\s+s\s*·\s*\d+\.?\d*k?\s*tokens'),

    # 62. Bare "N thought for Ns)"
    re.compile(r'^\s*\d+\s+thought\s+for\s+\d+'),

    # 63. Garbled spinner with …
    re.compile(r'^[\s*·✶✻✽✢]+\s*\w{0,5}\s*…\s*\d+'),

    # 64. Truncated "shift+tab" hint
    re.compile(r'ift\+tab\s+to\s+cyc'),

    # 65. Bare timing without opening paren
    re.compile(r'^\s*\d+s?\s*·\s*timeout\s+\d+'),

    # 66. Truncated "Running in the background"
    re.compile(r'^Runn\w*\s+in\s+the\s+background'),

    # 67. Timeout with Nm Ns format
    re.compile(r'^\s*⎿?\s*\(timeout\s+\d+m?\s*\d*s?\)'),

    # 68. "Task Output <hex>"
    re.compile(r'^Task\s+Output\s+[a-f0-9]+'),

    # 69. "Waiting for task"
    re.compile(r'Waiting\s*for\s*task'),
    re.compile(r'Waitingfortask'),

    # 70. Ultra-garbled spinner fragments
    re.compile(r'^\w{1,5}\s+\w{0,3}…\s*[↑↓]'),

    # 71. CLI help listings
    re.compile(r'\((?:user|usr|sr)\)\s*$'),

    # 72. CLI help — slash command format
    re.compile(r'^/\w[\w-]+\s{2,}\S'),

    # 73. CLI help — garbled command descriptions
    re.compile(r'^(?:unleashed-version|upgrde|usage|sage|ext\s+-usage)\s'),

    # 74. Plan mode chrome
    re.compile(r'^⎿\s*/plan\s+to\s+preview'),
    re.compile(r'^Ready\s+to\s+code\s*\?'),

    # 75. Garbled spinner without leading char but with … + (timing)
    re.compile(r'^[A-Z]\w*\s+\w*\s+\w*\s*…\s*\(\d+[ms]?\s*\d*s?\s*·\s*[↑↓]'),

    # 76. Lone bullet point
    re.compile(r'^\s*●\s*$'),

    # 77. "+N more lines"
    re.compile(r'^\s*\+\d+\s+more\s+lines?\s'),

    # 78. Task list summary
    re.compile(r'^\d+\s+tasks?\s*\(\d+\s+done'),

    # 79-80. Ultra-garbled thought fragments
    re.compile(r'^[\s*·✶✻✽✢]*\s*\w{0,5}\s*…\s*ought\s+for\s+\d+'),
    re.compile(r'^[a-z\s]{1,10}\d+\s+\d*\s*thought\s+for\s+\d+'),

    # 81. Playwright "No open tabs"
    re.compile(r'No\s*open\s*tabs\s*\.?\s*Navigate\s*to', re.IGNORECASE),
    re.compile(r'Noopentabs'),

    # 82-83. Garbled timing/tool fragments
    re.compile(r'^[A-Z]\s+\d+m?\s*\d*s?\s*·\s*[↑↓]'),
    re.compile(r'^[a-z]{1,6}(?:ing|ching)\s+\d+\s+(?:files?|patterns?)'),

    # 84-86. Garbled search/timing fragments
    re.compile(r'^S\s*\w*rching\s+\w+\s+\d+\s+pattern'),
    re.compile(r'^\d+\s+to[lo]*\s+uses?\s*·'),
    re.compile(r'^\d+\s+s[,·]\s*(?:reading|searching)'),

    # 87. CLI help — garbled command listings
    re.compile(r'^(?:status|statusline|fronend|passes|conext|sage|ext\s+-usage)\s{2,}'),
    re.compile(r'^(?:status|statusline|fronend|passes|conext)\s+\w'),

    # 88-89. "+N more" variants
    re.compile(r'^\s*\+\d+\s+more\s+tool\s+use\w*'),
    re.compile(r'^\s*\+\d+\s+more\s+lines?\s*\('),

    # 90. Wrangler deploy stats
    re.compile(r'^Total\s*Upload:\s*\d'),

    # 91. Broad … + (Ns · ↓) pattern
    re.compile(r'…\s*\(\d+m?\s*\d*s?\s*·\s*[↑↓]'),

    # 92. Truncated spinner word fragments
    re.compile(r'^[*·✶✻✽✢]*[A-Z][a-z]{1,6}$'),

    # 93. Spinner verb + … + bare timing
    re.compile(r"^[A-Z][a-zéèêë'-]+(?:ing|ed|ion|ting|in')…?\s+\d+\s"),

    # 94. Lines that are only Unicode whitespace
    re.compile(r'^[\s\xa0\u200b\u2000-\u200a\u2028\u2029\u3000]+$'),

    # 95. Garbled "Hatch g…" truncated spinner
    re.compile(r'^[A-Z][a-z]+\s+[a-z]?…'),
]


# Lines containing these strings are ALWAYS kept (compaction markers)
COMPACTION_KEEP = [
    'compacting conversation',
    'conversation compacted',
    'compactingconversation',
    'conversationcompacted',
]


def is_garbage(line: str) -> bool:
    """Return True if line is TUI garbage that should be removed."""
    stripped = line.strip()
    if not stripped:
        return True  # blank lines (we'll re-add spacing intelligently later)

    # Preserve compaction markers — these track context lobotomy events
    lower = stripped.lower()
    for marker in COMPACTION_KEEP:
        if marker in lower:
            return False

    for pattern in GARBAGE_PATTERNS:
        if pattern.search(stripped):
            return True
    return False


def normalize_for_dedup(line: str) -> str:
    """Normalize a line for deduplication comparison."""
    s = line.strip()
    s = re.sub(r'^[\s*·✶✻✽✢●◼◻❯⏵⎿]+', '', s)
    s = re.sub(r'\s+', '', s)
    return s.lower()
