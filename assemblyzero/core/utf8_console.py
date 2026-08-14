"""One process-wide default so a report never dies on the text it reports (#2367).

`tools/check_requirements_form.py` exists to judge a document. It read a
document containing a true minus sign -- U+2212, which the boostgauge aesthetic
doc's binding angle formula uses -- and died with `UnicodeEncodeError: 'charmap'
codec can't encode character '−'` before printing a word of its verdict.

The crash is not in the checking. It is in `print`. When stdout is a pipe rather
than a console -- which is every agent invocation, every `2>&1 > log`, every CI
step -- Python encodes it with the locale encoding, and on this fleet that is
cp1252. cp1252 has 256 code points. A checker whose input is arbitrary prose
will meet a character outside them, and the one it met was in the very document
it enforces.

So the failure mode is specific and worth naming: **the tool is most likely to
crash on exactly the documents it most needs to check.** A document quoting its
own binding standard is the normal case, not the exotic one.

The fix is the same shape as `no_console`: one default installed once at the
entry point, rather than an `encoding=` argument remembered at every print. A
report is printed from many places, new report tools get written, and any one
that forgets re-opens the hole.

Two tiers, because a checker must never be the thing that fails:

1. Re-encode as UTF-8, which can represent every string Python can hold. This
   is the real fix and it loses nothing.
2. If that is somehow refused, fall back to `errors="replace"` on whatever
   encoding is in force. The output degrades to `?` for unrepresentable
   characters, which is worse than UTF-8 and enormously better than a traceback
   where a verdict should be.

Unlike `no_console.install()`, this carries no already-installed guard. That
guard exists there because wrapping a constructor twice would stack; a stream
reconfigured twice is simply reconfigured. Acting every time is also what makes
it correct when something replaces `sys.stdout` after the entry point ran --
pytest's capture does exactly that between tests.
"""

from __future__ import annotations

import sys
from typing import Any

# Reconfiguring a stream fails narrowly and predictably: a detached or closed
# stream raises ValueError, an unknown codec LookupError, and a stream backed by
# a dead handle OSError. Anything else is a bug worth seeing, so it is not caught.
_RECONFIGURE_ERRORS = (ValueError, LookupError, OSError)


def install() -> None:
    """Make stdout and stderr able to carry any string this process can hold.

    Idempotent, and a no-op for any stream that cannot be reconfigured -- a
    `StringIO` under test, a pytest capture object, a stream someone replaced
    with a plain file-like. Those either handle text natively or are not ours
    to reach into.
    """
    for name in ("stdout", "stderr"):
        widen(getattr(sys, name, None))


def widen(stream: Any) -> bool:
    """Widen one stream. Returns whether it now carries arbitrary text safely.

    False means the stream had no `reconfigure` and was left untouched, not that
    anything failed -- callers use it for reporting, never for control flow.
    """
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is None:
        return False

    try:
        reconfigure(encoding="utf-8", errors="replace")
        return True
    except _RECONFIGURE_ERRORS:
        pass

    # Tier 2: keep the encoding, lose the crash.
    try:
        reconfigure(errors="replace")
        return True
    except _RECONFIGURE_ERRORS:
        return False
