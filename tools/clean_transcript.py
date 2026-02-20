#!/usr/bin/env python3
"""
clean_transcript.py — Clean PTY session transcripts.

Removes TUI garbage (spinners, status bars, permission UI, thinking fragments,
logo chrome, etc.) while preserving actual conversation content.

Origin: unleashed/src/clean_transcript.py (propagated via Issue #361)

Usage:
    poetry run python tools/clean_transcript.py transcripts/session.raw
    poetry run python tools/clean_transcript.py --fix-spaces transcripts/session.raw

Options:
    --fix-spaces    Reinsert spaces into word-merged text using dictionary lookup
                    (requires: poetry add wordninja)

Writes cleaned output to <filename>.clean — NEVER modifies the original.
Also writes <filename>.user — extracted user input only.
"""
import argparse
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

# Add tools directory to path for sibling imports
sys.path.insert(0, str(Path(__file__).parent))

from transcript_filters import is_garbage, normalize_for_dedup


def dedup_consecutive(lines: list[str]) -> tuple[list[str], int]:
    """Remove consecutive duplicate lines (TUI repaint artifacts)."""
    if not lines:
        return lines, 0

    result = [lines[0]]
    removed = 0
    prev_norm = normalize_for_dedup(lines[0])

    for line in lines[1:]:
        norm = normalize_for_dedup(line)
        if not norm:
            result.append(line)
            prev_norm = norm
            continue
        if norm == prev_norm:
            removed += 1
            continue
        result.append(line)
        prev_norm = norm

    return result, removed


def dedup_blocks(lines: list[str], window: int = 5, min_block: int = 8) -> tuple[list[str], int]:
    """Remove duplicate blocks that appear far apart in the transcript."""
    norms = []
    for i, line in enumerate(lines):
        n = normalize_for_dedup(line)
        if n:
            norms.append((i, n))

    if len(norms) < window * 2:
        return lines, 0

    seen_windows = {}
    duplicate_line_indices = set()

    for wi in range(len(norms) - window + 1):
        window_hash = hash(tuple(norms[wi + j][1] for j in range(window)))

        if window_hash in seen_windows:
            first_wi = seen_windows[window_hash]
            match = all(norms[first_wi + j][1] == norms[wi + j][1] for j in range(window))
            if not match:
                continue

            block_end = window
            while (wi + block_end < len(norms)
                   and first_wi + block_end < len(norms)
                   and first_wi + block_end < wi
                   and norms[first_wi + block_end][1] == norms[wi + block_end][1]):
                block_end += 1

            if block_end >= min_block:
                for j in range(block_end):
                    duplicate_line_indices.add(norms[wi + j][0])
        else:
            seen_windows[window_hash] = wi

    if not duplicate_line_indices:
        return lines, 0

    result = []
    removed = 0
    for i, line in enumerate(lines):
        if i in duplicate_line_indices:
            removed += 1
        elif not line.strip() and removed > 0:
            next_content = None
            for j in range(i + 1, min(i + 3, len(lines))):
                if lines[j].strip():
                    next_content = j
                    break
            if next_content and next_content in duplicate_line_indices:
                removed += 1
            else:
                result.append(line)
        else:
            result.append(line)

    return result, removed


def extract_user_input(lines: list[str]) -> list[str]:
    """Extract only user input lines from cleaned transcript."""
    user_lines = []
    in_user_block = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith('❯'):
            if user_lines and user_lines[-1] != '':
                user_lines.append('')
            content = stripped[1:].strip()
            if content:
                user_lines.append(content)
            in_user_block = True
        elif in_user_block and stripped and not stripped.startswith('●'):
            if any(stripped.startswith(p) for p in ('●', 'Bash(', 'Read(', 'Write(',
                    'Edit(', 'Search(', 'Grep(', 'Glob(', 'Explore(', '⎿', '┌', '├',
                    '│', '└', 'plugin:', 'Error:')):
                in_user_block = False
            else:
                user_lines.append(stripped)
        else:
            in_user_block = False

    while user_lines and user_lines[-1] == '':
        user_lines.pop()

    user_lines, _ = dedup_typing_repaints(user_lines)
    return user_lines


def dedup_typing_repaints(lines: list[str]) -> tuple[list[str], int]:
    """Remove progressive typing repaints and duplicate blocks from user input."""
    blocks = []
    current_block = []
    current_start = 0

    for i, line in enumerate(lines):
        if line.strip() == '':
            if current_block:
                blocks.append((current_start, current_block[:]))
                current_block = []
            current_start = i + 1
        else:
            if not current_block:
                current_start = i
            current_block.append(line)
    if current_block:
        blocks.append((current_start, current_block[:]))

    if len(blocks) < 2:
        return lines, 0

    def normalize_block(block_lines):
        text = ''.join(block_lines).lower()
        text = re.sub(r'[\s,.:;]+', '', text)
        return text

    block_norms = [normalize_block(b[1]) for b in blocks]

    MIN_LEN = 15
    MATCH_RATIO = 0.75
    remove_indices = set()

    def is_fuzzy_prefix(shorter, longer):
        if len(shorter) < MIN_LEN:
            return False
        target = longer[:len(shorter) + max(5, len(shorter) // 5)]
        return SequenceMatcher(None, shorter, target).ratio() >= MATCH_RATIO

    for i in range(len(blocks)):
        if i in remove_indices:
            continue
        norm_i = block_norms[i]
        if len(norm_i) < MIN_LEN:
            continue

        for j in range(i + 1, len(blocks)):
            if j in remove_indices:
                continue
            norm_j = block_norms[j]
            if len(norm_j) < MIN_LEN:
                continue

            if len(norm_i) <= len(norm_j) and is_fuzzy_prefix(norm_i, norm_j):
                remove_indices.add(i)
                break

            if len(norm_j) < len(norm_i) and is_fuzzy_prefix(norm_j, norm_i):
                remove_indices.add(j)

    if not remove_indices:
        return lines, 0

    result = []
    removed = 0
    for bi, (start, block_lines) in enumerate(blocks):
        if bi in remove_indices:
            removed += len(block_lines)
            continue
        if result and result[-1] != '':
            result.append('')
        result.extend(block_lines)

    while result and result[-1] == '':
        result.pop()

    return result, removed


def fix_merged_spaces(line: str) -> str:
    """Reinsert spaces into word-merged text segments.

    Requires wordninja package: poetry add wordninja
    """
    try:
        import wordninja
    except ImportError:
        return line

    stripped = line.strip()
    if not stripped:
        return line

    skip_indicators = [
        stripped.startswith(('/', 'C:\\', 'http', '#', '//', '/*', '```', '|', '+')),
        stripped.startswith(('-', '>')) and len(stripped) < 5,
        re.match(r'^\s*(?:def |class |import |from |if |for |while |return )', stripped),
        re.match(r'^\s*[\{\}\[\]<>]', stripped),
        '.py:' in stripped or '.js:' in stripped or '.sql' in stripped,
    ]
    if any(skip_indicators):
        return line

    def split_merged(match):
        segment = match.group(0)
        if any(c in segment for c in ['/', '\\', '::', '://', '_', '.']):
            return segment
        if segment.islower() or segment.isupper():
            return segment
        if len(segment) < 15:
            return segment
        words = wordninja.split(segment)
        if len(words) <= 1:
            return segment
        return ' '.join(words)

    return re.sub(r'\S{15,}', split_merged, line)


def replace_nbsp(text: str) -> str:
    """Replace non-breaking spaces (U+00A0) with regular ASCII spaces."""
    return text.replace('\xa0', ' ')


def clean_transcript(input_path: Path, fix_spaces: bool = False) -> tuple[Path, dict]:
    """Clean a transcript file. Returns (output_path, stats)."""
    raw = input_path.read_text(encoding='utf-8', errors='replace')
    raw = replace_nbsp(raw)

    lines = raw.splitlines()
    total = len(lines)

    # Pass 1: Remove garbage lines
    kept = []
    removed_garbage = 0
    prev_blank = False

    for line in lines:
        if is_garbage(line):
            removed_garbage += 1
            if kept and not prev_blank:
                prev_blank = True
        else:
            if prev_blank and kept:
                kept.append('')
            kept.append(line)
            prev_blank = False

    # Pass 2: Deduplicate consecutive lines
    kept, removed_dedup = dedup_consecutive(kept)

    # Pass 3: Remove duplicate blocks
    kept, removed_blocks = dedup_blocks(kept)

    # Pass 4: Fix word-merged text (optional)
    spaces_fixed = 0
    if fix_spaces:
        fixed = []
        for line in kept:
            new_line = fix_merged_spaces(line)
            if new_line != line:
                spaces_fixed += 1
            fixed.append(new_line)
        kept = fixed

    total_removed = removed_garbage + removed_dedup + removed_blocks

    output_path = input_path.with_suffix('.clean')
    output_path.write_text('\n'.join(kept) + '\n', encoding='utf-8')

    user_lines = extract_user_input(kept)
    user_path = input_path.with_suffix('.user')
    user_path.write_text('\n'.join(user_lines) + '\n', encoding='utf-8')

    stats = {
        'total_lines': total,
        'removed_garbage': removed_garbage,
        'removed_dedup': removed_dedup,
        'removed_blocks': removed_blocks,
        'total_removed': total_removed,
        'kept': len(kept),
        'user_lines': len(user_lines),
        'pct_removed': round(total_removed / total * 100, 1) if total else 0,
        'spaces_fixed': spaces_fixed,
    }
    return output_path, stats


def main():
    parser = argparse.ArgumentParser(
        description='Clean PTY session transcripts — remove TUI garbage, preserve content.'
    )
    parser.add_argument('file', type=Path, help='Transcript file to clean')
    parser.add_argument('--fix-spaces', action='store_true',
                        help='Reinsert spaces into word-merged text (requires wordninja)')
    args = parser.parse_args()

    if not args.file.exists():
        print(f"File not found: {args.file}")
        sys.exit(1)

    output_path, stats = clean_transcript(args.file, fix_spaces=args.fix_spaces)

    print(f"Input:    {args.file} ({stats['total_lines']} lines)")
    print(f"Output:   {output_path} ({stats['kept']} lines)")
    print(f"Garbage:  {stats['removed_garbage']} lines")
    print(f"Dedup:    {stats['removed_dedup']} lines")
    print(f"Blocks:   {stats['removed_blocks']} lines (duplicate sections)")
    print(f"Total:    {stats['total_removed']} lines removed ({stats['pct_removed']}%)")
    print(f"User:     {stats['user_lines']} user input lines -> {args.file.with_suffix('.user')}")
    if stats['spaces_fixed']:
        print(f"Spaces:   {stats['spaces_fixed']} lines had word-merged text fixed")


if __name__ == '__main__':
    main()
