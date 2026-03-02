```python
"""Claim extractors — parse Markdown documents to identify verifiable factual claims.

Issue #534: Spelunking Audits
"""

from __future__ import annotations

import re
from pathlib import Path

from assemblyzero.spelunking.models import Claim, ClaimType


# Compiled regex patterns for claim extraction
_FILE_COUNT_PATTERN = re.compile(
    r"(\d+)\s+(files?|tools?|ADRs?|standards?|probes?|workflows?)"
    r"(?:\s+in\s+)?[`\s]*([a-zA-Z0-9_/.:-]+/?)[`]?",
    re.IGNORECASE,
)

_FILE_REF_BACKTICK_PATTERN = re.compile(
    r"`([a-zA-Z0-9_/.:-]+\.[a-zA-Z0-9]+)`"
)

_FILE_REF_LINK_PATTERN = re.compile(
    r"\[(?:[^\]]*)\]\(([a-zA-Z0-9_/.:-]+\.[a-zA-Z0-9]+)\)"
)

_TIMESTAMP_PATTERN = re.compile(
    r"[Ll]ast\s+[Uu]pdated:?\s*(\d{4}-\d{2}-\d{2})"
)

_DATE_PATTERN = re.compile(
    r"[Dd]ate:?\s*(\d{4}-\d{2}-\d{2})"
)

_NEGATION_PATTERN = re.compile(
    r"(?:not|without|no)\s+([a-zA-Z][a-zA-Z0-9_ ]{2,})",
    re.IGNORECASE,
)

# Word sets for cleaning captured negation phrases into core technology terms.
# Leading words that are verbs/articles to strip before the real term.
_LEADING_SKIP = frozenset({
    "use", "using", "used", "have", "has", "had", "need", "needs",
    "require", "requires", "include", "includes", "support", "supports",
    "rely", "relying", "a", "an", "the", "any", "some",
})

# Words that signal the end of the technology term (prepositions, fillers).
_STOP_BEFORE = frozenset({
    "for", "in", "on", "to", "of", "with", "from", "by", "at",
    "or", "and", "here", "there", "that", "this", "it", "its",
    "but", "so", "as", "if", "when", "where", "how", "why",
})


def _clean_negated_term(raw: str) -> str:
    """Extract the core technology/concept term from a captured negation phrase.

    Strips leading verbs/articles and truncates at prepositions/fillers so that
    'use chromadb for storage' becomes 'chromadb' and 'vector embeddings'
    stays as 'vector embeddings'.
    """
    words = raw.strip().split()
    # Strip leading filler words (verbs, articles)
    while words and words[0].lower() in _LEADING_SKIP:
        words = words[1:]
    # Truncate at first stop/filler word
    cleaned: list[str] = []
    for w in words:
        if w.lower() in _STOP_BEFORE:
            break
        cleaned.append(w)
    return " ".join(cleaned).lower()


def extract_claims_from_markdown(
    file_path: Path,
    claim_types: list[ClaimType] | None = None,
) -> list[Claim]:
    """Parse a Markdown file and extract verifiable factual claims."""
    if not file_path.exists():
        return []

    content = file_path.read_text(encoding="utf-8")
    claims: list[Claim] = []

    extractors = {
        ClaimType.FILE_COUNT: extract_file_count_claims,
        ClaimType.FILE_EXISTS: extract_file_reference_claims,
        ClaimType.TIMESTAMP: extract_timestamp_claims,
        ClaimType.TECHNICAL_FACT: extract_technical_claims,
    }

    active_types = claim_types if claim_types else list(extractors.keys())

    for claim_type in active_types:
        if claim_type in extractors:
            claims.extend(extractors[claim_type](content, file_path))

    return claims


def extract_file_count_claims(
    content: str,
    source_file: Path,
) -> list[Claim]:
    """Extract claims about file/directory counts from document content."""
    claims: list[Claim] = []
    for line_num, line in enumerate(content.splitlines(), start=1):
        for match in _FILE_COUNT_PATTERN.finditer(line):
            count_str = match.group(1)
            item_type = match.group(2)
            directory = match.group(3).rstrip("/")
            claim_text = match.group(0).strip()

            # Determine glob pattern based on item type
            item_lower = item_type.lower().rstrip("s")
            if item_lower in ("adr",):
                glob_pat = "*.md"
            else:
                glob_pat = "*.py"

            claims.append(
                Claim(
                    claim_type=ClaimType.FILE_COUNT,
                    source_file=source_file,
                    source_line=line_num,
                    claim_text=claim_text,
                    expected_value=count_str,
                    verification_command=f"glob {directory}/{glob_pat} | count",
                )
            )
    return claims


def extract_file_reference_claims(
    content: str,
    source_file: Path,
) -> list[Claim]:
    """Extract file path references that can be verified for existence."""
    claims: list[Claim] = []
    seen_paths: set[str] = set()

    for line_num, line in enumerate(content.splitlines(), start=1):
        # Backtick references
        for match in _FILE_REF_BACKTICK_PATTERN.finditer(line):
            path_str = match.group(1)
            if path_str not in seen_paths and not path_str.startswith(
                ("http://", "https://")
            ):
                seen_paths.add(path_str)
                claims.append(
                    Claim(
                        claim_type=ClaimType.FILE_EXISTS,
                        source_file=source_file,
                        source_line=line_num,
                        claim_text=path_str,
                        expected_value=path_str,
                        verification_command=f"path_exists {path_str}",
                    )
                )

        # Markdown link references
        for match in _FILE_REF_LINK_PATTERN.finditer(line):
            path_str = match.group(1)
            if path_str not in seen_paths and not path_str.startswith(
                ("http://", "https://", "#")
            ):
                seen_paths.add(path_str)
                claims.append(
                    Claim(
                        claim_type=ClaimType.FILE_EXISTS,
                        source_file=source_file,
                        source_line=line_num,
                        claim_text=path_str,
                        expected_value=path_str,
                        verification_command=f"path_exists {path_str}",
                    )
                )
    return claims


def extract_timestamp_claims(
    content: str,
    source_file: Path,
) -> list[Claim]:
    """Extract 'Last Updated' or date-stamped claims."""
    claims: list[Claim] = []
    for line_num, line in enumerate(content.splitlines(), start=1):
        for pattern in (_TIMESTAMP_PATTERN, _DATE_PATTERN):
            match = pattern.search(line)
            if match:
                date_str = match.group(1)
                claims.append(
                    Claim(
                        claim_type=ClaimType.TIMESTAMP,
                        source_file=source_file,
                        source_line=line_num,
                        claim_text=match.group(0).strip(),
                        expected_value=date_str,
                        verification_command=f"check_freshness {date_str}",
                    )
                )
    return claims


def extract_technical_claims(
    content: str,
    source_file: Path,
    negation_patterns: list[str] | None = None,
) -> list[Claim]:
    """Extract technical assertions that can be grep-verified. Focuses on negations."""
    claims: list[Claim] = []
    patterns = [_NEGATION_PATTERN]

    if negation_patterns:
        for pat in negation_patterns:
            patterns.append(re.compile(pat, re.IGNORECASE))

    seen_terms: set[str] = set()

    for line_num, line in enumerate(content.splitlines(), start=1):
        for pattern in patterns:
            for match in pattern.finditer(line):
                raw = match.group(1).strip()
                term = _clean_negated_term(raw)
                if len(term) >= 3 and term not in seen_terms:
                    seen_terms.add(term)
                    claims.append(
                        Claim(
                            claim_type=ClaimType.TECHNICAL_FACT,
                            source_file=source_file,
                            source_line=line_num,
                            claim_text=match.group(0).strip(),
                            expected_value=term,
                            verification_command=f"grep_absent {term}",
                        )
                    )
    return claims
```
