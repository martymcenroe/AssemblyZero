"""The paths a unified diff's file headers name (#4555).

A spec writes a change to an existing file as a git-style diff, and that
diff's file headers carry git's `a/` and `b/` prefixes. Read as words of the
text, `--- a/web/tests/x.test.ts` names `a/web/tests/x.test.ts`, a path no
project has: the implementation workflow's first node took it for a planned
test file and halted looking for its runner in a directory named `a`. This
module is the one reader of those headers for anything that reads planned
file paths out of a spec or an LLD.

The grammar is closed. A file header is a line, at column 0 as git writes
it, of exactly one of three forms:

    --- <name>
    +++ <name>
    diff --git <name> <name>

and in a text, a `---` line is a header only when the next line is a `+++`
header, and a `+++` line only when the line before is a `---` header: a
unified diff names its old file and its new one on two adjacent lines. A
`diff --git` line stands alone.

A <name> is `/dev/null`, which names no file, or a path. git writes a path
with one prefix, `a/` on the old side and `b/` on the new, and exactly one
leading `a/` or `b/` comes off. A path written without one (`--no-prefix`)
is kept as written. git C-quotes a name it will not print bare, and after
`---` and `+++` ends a name with a tab when it holds a space; a `diff -u`
header ends it with a tab and a timestamp. So after `---` or `+++` the name
runs to the first tab, and a name that holds a space with no tab after it is
not a header's.

Nothing else is a file header. Any other line, including a path under a
directory named `a` written anywhere but a header, is never altered.
"""

from __future__ import annotations

#: The three header forms, as the text that opens the line. Closed.
OLD_HEADER = "--- "
NEW_HEADER = "+++ "
GIT_HEADER = "diff --git "

#: The name a header gives for the side of a diff that has no file.
NO_FILE = "/dev/null"

#: git's side prefixes. Closed: exactly one of these comes off a path.
SIDE_PREFIXES = ("a/", "b/")


def git_unquoted(name: str) -> str:
    """A name as git printed it: `"..."` with C escapes when it holds a
    character git will not print bare, else the name itself."""
    if not (len(name) >= 2 and name.startswith('"') and name.endswith('"')):
        return name
    return (
        name[1:-1].encode("utf-8").decode("unicode_escape").encode("latin-1").decode("utf-8")
    )


def header_path(name: str) -> str | None:
    """The path a header's <name> names: one leading `a/` or `b/` off, or
    None for `/dev/null`, which names no file."""
    name = git_unquoted(name)
    if name == NO_FILE:
        return None
    for prefix in SIDE_PREFIXES:
        if name.startswith(prefix):
            return name[len(prefix):]
    return name


def _side_name(field: str) -> str | None:
    """The <name> of a `---` or `+++` header from what follows the marker,
    or None when the field is not one."""
    name, tab, _ = field.partition("\t")
    name = name.rstrip(" ")
    if not name or name.startswith(" "):
        return None
    if " " in name and not tab and not name.startswith('"'):
        return None
    return name


def _quoted_end(text: str) -> int:
    """The index just past the closing quote of the C-quoted name `text`
    opens with, or -1 when it has none."""
    index = 1
    while index < len(text):
        if text[index] == "\\":
            index += 2
            continue
        if text[index] == '"':
            return index + 1
        index += 1
    return -1


def _git_names(rest: str) -> tuple[str, str] | None:
    """The two <name>s of a `diff --git` header from what follows the marker,
    or None when they cannot be told apart.

    A quoted name ends at its closing quote. Two unquoted names are split
    where the line holds the same path twice (`a/P b/P`, or `P P` without
    prefixes), which is every header but a rename's; a rename's is split at
    its one ` b/`. A rename whose paths hold ` b/` themselves is ambiguous
    to git as well, and is not read.
    """
    if rest.startswith('"'):
        end = _quoted_end(rest)
        if end < 0 or rest[end:end + 1] != " ":
            return None
        return rest[:end], rest[end + 1:]
    if rest.endswith('"'):
        start = rest.rfind(' "')
        if start < 0:
            return None
        return rest[:start], rest[start + 1:]
    if len(rest) % 2 == 1:
        half = len(rest) // 2
        old, gap, new = rest[:half], rest[half], rest[half + 1:]
        if gap == " " and old and header_path(old) == header_path(new):
            return old, new
    if rest.startswith("a/") and rest.count(" b/") == 1:
        old, _, new = rest.partition(" b/")
        return old, "b/" + new
    return None


def header_paths(line: str) -> tuple[str, ...] | None:
    """The paths one diff file-header line names, or None when the line is
    not one. `--- /dev/null` is a header that names no path: ().

    This reads one line. Whether a `---` or `+++` line is a header in a text
    depends on its neighbour as well, which `with_header_paths` checks.
    """
    line = line.rstrip("\r")
    if line.startswith((OLD_HEADER, NEW_HEADER)):
        name = _side_name(line[len(OLD_HEADER):])
        if name is None:
            return None
        path = header_path(name)
        return () if path is None else (path,)
    if line.startswith(GIT_HEADER):
        names = _git_names(line[len(GIT_HEADER):])
        if names is None:
            return None
        paths: list[str] = []
        for name in names:
            path = header_path(name)
            if path is not None and path not in paths:
                paths.append(path)
        return tuple(paths)
    return None


def _paired(lines: list[str], index: int) -> bool:
    """Whether the `---` or `+++` line at `index` has its other half beside
    it: a `---` header above a `+++` header."""
    line = lines[index]
    if line.startswith(OLD_HEADER):
        other = index + 1
        wanted = NEW_HEADER
    else:
        other = index - 1
        wanted = OLD_HEADER
    if not 0 <= other < len(lines) or not lines[other].startswith(wanted):
        return False
    return header_paths(lines[other]) is not None


def with_header_paths(text: str) -> str:
    """`text` with each diff file-header line replaced by the paths it names,
    one per line, and every other line as it was.

    A reader of the text's words then sees `web/x.test.ts` where the header
    said `a/web/x.test.ts` or `b/web/x.test.ts`, and nothing where it said
    `/dev/null`.
    """
    lines = (text or "").split("\n")
    out: list[str] = []
    for index, line in enumerate(lines):
        paths = header_paths(line)
        if paths is not None and not line.startswith(GIT_HEADER) and not _paired(lines, index):
            paths = None
        if paths is None:
            out.append(line)
        else:
            out.extend(paths)
    return "\n".join(out)
