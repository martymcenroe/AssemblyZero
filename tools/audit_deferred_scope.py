#!/usr/bin/env python3
"""Audit deferred-scope language across all closed AssemblyZero issues.

Three phases:
1. Fetch + cache: enumerate closed issues + their comments via gh CLI;
   persist as JSON so subsequent runs are cheap.
2. Regex first pass: scan body+comments for deferral keywords; build
   candidate list.
3. LLM refinement: per candidate, ask `claude --print` (no API key — uses
   Max subscription via the user's CLI) to classify true-deferral,
   summarize, cross-reference follow-ups, and judge obsolescence.
4. Write reports: full audit and new-repo subset.

Issue #930. ADR-0217 (force-free git ops) and root CLAUDE.md (no-API-key
rule) constraints respected.

Usage:
    poetry run python tools/audit_deferred_scope.py            # full pipeline
    poetry run python tools/audit_deferred_scope.py --no-llm   # phases A+B only
    poetry run python tools/audit_deferred_scope.py --refresh  # force re-fetch corpus

Cached at:
    data/closed-issues-snapshot-{date}.json
    data/deferred-scope-llm-cache.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

REPO = "martymcenroe/AssemblyZero"
TODAY = datetime.now().strftime("%Y-%m-%d")
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DOCS_DIR = Path(__file__).resolve().parent.parent / "docs" / "audits"

CORPUS_CACHE = DATA_DIR / f"closed-issues-snapshot-{TODAY}.json"
LLM_CACHE = DATA_DIR / "deferred-scope-llm-cache.json"

REPORT_FULL = DOCS_DIR / f"0845-deferred-scope-audit-{TODAY}.md"
REPORT_NEW_REPO = DOCS_DIR / f"0846-deferred-scope-new-repo-{TODAY}.md"

# Regex patterns flagging potential deferred scope. Case-insensitive.
DEFERRAL_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("deferred", re.compile(r"\bdeferr(?:ed|al)(?:\s+(?:scope|to|for|until))?\b", re.I)),
    ("out_of_scope", re.compile(r"\bout[- ]of[- ]scope\b", re.I)),
    ("follow_up", re.compile(r"\bfollow[- ]?up(?:\s+(?:issue|PR|work|ticket))?\b", re.I)),
    ("future_work", re.compile(r"\bfuture work\b", re.I)),
    ("not_in_this", re.compile(r"\bnot in this (?:PR|issue|change|scope|pass)\b", re.I)),
    ("good_enough", re.compile(r"\bgood enough for now\b", re.I)),
    ("phase_n", re.compile(r"\bphase [2-9]\b", re.I)),
    ("next_iter", re.compile(r"\bnext (?:iteration|sprint|round|phase|session)\b", re.I)),
    ("tracked_separately", re.compile(r"\btracked separately\b", re.I)),
    ("separate_issue", re.compile(r"\b(?:separate|new) (?:issue|PR|ticket)\b", re.I)),
    ("todo_in_close", re.compile(r"\bTODO\b", re.I)),
    ("will_file_followup", re.compile(
        r"\bwill (?:file|track|cover|land) (?:as|in|via|with)?\s*"
        r"(?:a |an )?(?:separate|follow[- ]?up|new)\b", re.I)),
]

# Window of context to grab around each match.
CONTEXT_RADIUS = 250

# Sleep between Claude CLI calls to be polite.
LLM_INTER_CALL_SLEEP_S = 2.0
LLM_TIMEOUT_S = 180

# gh CLI rate-limit handling (mirrors backfill_issue_audit pattern).
GH_INITIAL_BACKOFF = 1.0
GH_MAX_BACKOFF = 60.0
GH_MAX_RETRIES = 3
GH_INTER_CALL_DELAY = 0.3


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class IssueRecord:
    number: int
    title: str
    state: str
    closedAt: Optional[str]
    body: str
    labels: list[str]
    comments: list[dict] = field(default_factory=list)


@dataclass
class Candidate:
    issue_number: int
    issue_title: str
    closed_at: Optional[str]
    labels: list[str]
    keyword: str
    location: str  # "body" | "comment:<author>"
    context: str

    def cache_key(self) -> str:
        h = hashlib.sha1(
            f"{self.issue_number}|{self.keyword}|{self.location}|{self.context}".encode("utf-8")
        ).hexdigest()
        return h


@dataclass
class Classification:
    is_deferral: bool
    summary: str
    addressed_in: Optional[str]
    addressed_status: Optional[str]
    new_repo_related: bool
    still_relevant: Optional[bool]
    rationale: str
    raw_response: str = ""
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Subprocess wrapper
# ---------------------------------------------------------------------------

def _run(cmd: list[str], timeout: int = 60, env: Optional[dict] = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        env=env,
    )


def gh_with_backoff(cmd: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
    """gh CLI wrapper with rate-limit backoff."""
    backoff = GH_INITIAL_BACKOFF
    for attempt in range(GH_MAX_RETRIES + 1):
        r = _run(cmd, timeout=timeout)
        if r.returncode == 0:
            return r
        msg = (r.stderr + r.stdout).lower()
        if "rate limit" in msg or "429" in msg or "abuse" in msg:
            if attempt < GH_MAX_RETRIES:
                wait = min(backoff, GH_MAX_BACKOFF)
                print(f"  gh rate-limited; sleeping {wait}s")
                time.sleep(wait)
                backoff *= 2
                continue
        return r
    return r


# ---------------------------------------------------------------------------
# Phase A: fetch corpus
# ---------------------------------------------------------------------------

def fetch_corpus(refresh: bool = False) -> list[IssueRecord]:
    if CORPUS_CACHE.exists() and not refresh:
        print(f"Using cached corpus: {CORPUS_CACHE}")
        with CORPUS_CACHE.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        return [IssueRecord(**rec) for rec in raw]

    print(f"Fetching closed issues for {REPO}...")
    r = gh_with_backoff([
        "gh", "issue", "list",
        "--repo", REPO,
        "--state", "closed",
        "--limit", "2000",
        "--json", "number,title,state,closedAt,body,labels",
    ], timeout=120)
    if r.returncode != 0:
        print(f"ERROR: gh issue list failed: {r.stderr.strip()}")
        sys.exit(1)
    issues_raw = json.loads(r.stdout)
    print(f"  {len(issues_raw)} closed issues found")

    records: list[IssueRecord] = []
    for i, raw in enumerate(issues_raw, 1):
        if i % 50 == 0:
            print(f"  fetching comments {i}/{len(issues_raw)}...")
        labels = [lbl["name"] for lbl in raw.get("labels", [])]
        rec = IssueRecord(
            number=raw["number"],
            title=raw["title"],
            state=raw["state"],
            closedAt=raw.get("closedAt"),
            body=raw.get("body") or "",
            labels=labels,
            comments=[],
        )
        # Fetch comments only if body is non-trivial — saves API calls
        # Actually fetch all so the regex scan can hit closing comments.
        cr = gh_with_backoff([
            "gh", "api", "--paginate",
            f"repos/{REPO}/issues/{rec.number}/comments",
        ], timeout=60)
        if cr.returncode == 0:
            try:
                comments = json.loads(cr.stdout) if cr.stdout.strip() else []
                if isinstance(comments, list):
                    rec.comments = [
                        {"author": (c.get("user") or {}).get("login", "?"),
                         "createdAt": c.get("created_at"),
                         "body": c.get("body") or ""}
                        for c in comments
                    ]
            except json.JSONDecodeError:
                pass
        records.append(rec)
        time.sleep(GH_INTER_CALL_DELAY)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with CORPUS_CACHE.open("w", encoding="utf-8") as f:
        json.dump([asdict(r) for r in records], f, indent=2)
    print(f"  cached to {CORPUS_CACHE}")
    return records


# ---------------------------------------------------------------------------
# Phase B: regex first pass
# ---------------------------------------------------------------------------

def extract_context(text: str, span: tuple[int, int]) -> str:
    start = max(0, span[0] - CONTEXT_RADIUS)
    end = min(len(text), span[1] + CONTEXT_RADIUS)
    snippet = text[start:end].replace("\r\n", "\n").replace("\n", " ")
    return snippet.strip()


def find_candidates(corpus: list[IssueRecord]) -> list[Candidate]:
    candidates: list[Candidate] = []
    for rec in corpus:
        # Body
        for keyword, pattern in DEFERRAL_PATTERNS:
            for m in pattern.finditer(rec.body):
                candidates.append(Candidate(
                    issue_number=rec.number,
                    issue_title=rec.title,
                    closed_at=rec.closedAt,
                    labels=rec.labels,
                    keyword=keyword,
                    location="body",
                    context=extract_context(rec.body, m.span()),
                ))
                break  # one hit per keyword per body — avoid spam
        # Comments
        for c in rec.comments:
            for keyword, pattern in DEFERRAL_PATTERNS:
                for m in pattern.finditer(c.get("body", "")):
                    candidates.append(Candidate(
                        issue_number=rec.number,
                        issue_title=rec.title,
                        closed_at=rec.closedAt,
                        labels=rec.labels,
                        keyword=keyword,
                        location=f"comment:{c.get('author', '?')}",
                        context=extract_context(c.get("body", ""), m.span()),
                    ))
                    break
    # Deduplicate by (issue, keyword, location)
    seen = set()
    deduped = []
    for c in candidates:
        k = (c.issue_number, c.keyword, c.location)
        if k in seen:
            continue
        seen.add(k)
        deduped.append(c)
    return deduped


# ---------------------------------------------------------------------------
# Cross-reference index
# ---------------------------------------------------------------------------

def build_xref_index(corpus: list[IssueRecord]) -> dict[int, list[int]]:
    """Map: issue_number -> list of OTHER issue_numbers that reference it.

    A reference is `#N` appearing in a body or comment.
    """
    ref_pattern = re.compile(r"#(\d{1,5})\b")
    refs: dict[int, list[int]] = {}
    for rec in corpus:
        text = rec.body + " " + " ".join(c.get("body", "") for c in rec.comments)
        for m in ref_pattern.finditer(text):
            target = int(m.group(1))
            if target == rec.number:
                continue
            refs.setdefault(target, []).append(rec.number)
    # Dedupe each list
    for k, v in refs.items():
        refs[k] = sorted(set(v))
    return refs


# ---------------------------------------------------------------------------
# Phase C: LLM classification via `claude --print`
# ---------------------------------------------------------------------------

def load_llm_cache() -> dict[str, dict]:
    if not LLM_CACHE.exists():
        return {}
    try:
        return json.loads(LLM_CACHE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_llm_cache(cache: dict[str, dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LLM_CACHE.write_text(json.dumps(cache, indent=2), encoding="utf-8")


def build_prompt(c: Candidate, xref: list[int]) -> str:
    xref_text = ", ".join(f"#{n}" for n in xref) if xref else "(none found)"
    return (
        "You are auditing a closed GitHub issue for deferred-scope language. "
        "Answer ONLY with a strict JSON object — no prose before or after.\n\n"
        f"Issue #{c.issue_number}: \"{c.issue_title}\"\n"
        f"Closed: {c.closed_at}\n"
        f"Labels: {', '.join(c.labels) if c.labels else '(none)'}\n"
        f"Match keyword: {c.keyword}\n"
        f"Location: {c.location}\n\n"
        "Match context (text around the keyword):\n"
        "---\n"
        f"{c.context}\n"
        "---\n\n"
        f"Other issues that reference #{c.issue_number} (cross-references): {xref_text}\n\n"
        "Today's date: 2026-05-07.\n\n"
        "Respond JSON exactly in this shape (no markdown fences):\n"
        "{\n"
        '  "is_deferral": true|false,\n'
        '  "summary": "<≤25 words: what was deferred>",\n'
        '  "addressed_in": "<#NNN or null>",\n'
        '  "addressed_status": "open|closed|null",\n'
        '  "new_repo_related": true|false,\n'
        '  "still_relevant": true|false|null,\n'
        '  "rationale": "<≤30 words: why obsolete or still relevant>"\n'
        "}\n\n"
        "Rules:\n"
        "- is_deferral=false if the keyword match is a false positive (e.g., \"out of scope of v2\" where v2 already shipped).\n"
        "- new_repo_related=true if the deferred work concerns: tools/new_repo_setup.py, "
        "tools/deploy_cerberus_secrets.py, tools/_pat_session.py, runbook 0927, runbook 0930, "
        "Cerberus app, classic PAT flow, branch protection setup, fleet `delete_branch_on_merge`, "
        "or any first-time-creation step.\n"
        "- addressed_in: pick the single most likely follow-up issue number from the cross-references "
        "if any directly addresses what was deferred; null otherwise.\n"
        "- still_relevant=false if the deferred concern is now moot (technology replaced, "
        "process changed, problem solved out-of-band)."
    )


def parse_json_response(text: str) -> Optional[dict]:
    text = text.strip()
    # Strip markdown fences
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
    # Try direct
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Extract first {...} balanced block
    depth = 0
    start = -1
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    pass
                start = -1
    return None


def classify_candidate(c: Candidate, xref: list[int], cache: dict[str, dict]) -> Classification:
    key = c.cache_key()
    if key in cache:
        cached = cache[key]
        return Classification(**cached)

    prompt = build_prompt(c, xref)
    env = {**os.environ, "CLAUDECODE": ""}
    r = _run(["claude", "--print", "-p", prompt], timeout=LLM_TIMEOUT_S, env=env)
    if r.returncode != 0:
        cls = Classification(
            is_deferral=False, summary="", addressed_in=None,
            addressed_status=None, new_repo_related=False,
            still_relevant=None, rationale="", raw_response=r.stderr[:500],
            error=f"claude exit {r.returncode}",
        )
    else:
        parsed = parse_json_response(r.stdout)
        if not parsed:
            cls = Classification(
                is_deferral=False, summary="", addressed_in=None,
                addressed_status=None, new_repo_related=False,
                still_relevant=None, rationale="", raw_response=r.stdout[:500],
                error="json parse failed",
            )
        else:
            cls = Classification(
                is_deferral=bool(parsed.get("is_deferral", False)),
                summary=str(parsed.get("summary", ""))[:300],
                addressed_in=(parsed.get("addressed_in") or None),
                addressed_status=(parsed.get("addressed_status") or None),
                new_repo_related=bool(parsed.get("new_repo_related", False)),
                still_relevant=parsed.get("still_relevant"),
                rationale=str(parsed.get("rationale", ""))[:400],
                raw_response="",
                error=None,
            )
    cache[key] = asdict(cls)
    save_llm_cache(cache)
    time.sleep(LLM_INTER_CALL_SLEEP_S)
    return cls


# ---------------------------------------------------------------------------
# Phase D: write reports
# ---------------------------------------------------------------------------

def category_for(cls: Classification) -> str:
    if not cls.is_deferral:
        return "FALSE_POSITIVE"
    if cls.error:
        return "ERROR"
    if cls.addressed_in:
        return "CAUGHT" if cls.addressed_status == "closed" else "ADDRESSED_OPEN"
    if cls.still_relevant is False:
        return "OBSOLETE"
    if cls.still_relevant is True:
        return "ORPHANED"
    return "UNCLASSIFIED"


def render_table_row(c: Candidate, cls: Classification) -> str:
    addr = cls.addressed_in or "—"
    if cls.addressed_in and cls.addressed_status:
        addr = f"{cls.addressed_in} ({cls.addressed_status})"
    rel = {True: "yes", False: "no", None: "?"}.get(cls.still_relevant, "?")
    summary = (cls.summary or "—").replace("|", "\\|")
    rationale = (cls.rationale or "").replace("|", "\\|")
    return f"| #{c.issue_number} | {c.issue_title.replace('|', '\\|')} | {summary} | {addr} | {rel} | {rationale} |"


def render_report(
    candidates_with_class: list[tuple[Candidate, Classification]],
    title: str,
    audit_id: str,
    only_new_repo: bool,
) -> str:
    rows = [
        (c, cls) for c, cls in candidates_with_class
        if cls.is_deferral and (not only_new_repo or cls.new_repo_related)
    ]
    by_category: dict[str, list[tuple[Candidate, Classification]]] = {}
    for c, cls in rows:
        by_category.setdefault(category_for(cls), []).append((c, cls))

    lines: list[str] = []
    lines.append(f"# {audit_id} - {title}\n")
    lines.append(f"**Auditor:** Claude Opus 4.7 (1M context) via `tools/audit_deferred_scope.py`")
    lines.append(f"**Date:** {TODAY}")
    lines.append(f"**Corpus:** all closed AssemblyZero issues (snapshot {CORPUS_CACHE.name})")
    lines.append(f"**Method:** regex first-pass + LLM (`claude --print`) classification per candidate")
    lines.append(f"**Issue:** [#930](https://github.com/martymcenroe/AssemblyZero/issues/930)\n")
    lines.append("## Summary\n")
    lines.append("| Category | Meaning | Count |")
    lines.append("|---|---|---|")
    for cat in ("CAUGHT", "ADDRESSED_OPEN", "ORPHANED", "OBSOLETE", "UNCLASSIFIED", "ERROR"):
        meaning = {
            "CAUGHT": "follow-up issue was filed and is closed",
            "ADDRESSED_OPEN": "follow-up filed, still open",
            "ORPHANED": "still relevant; no follow-up filed",
            "OBSOLETE": "no longer applies (tech/process changed)",
            "UNCLASSIFIED": "still-relevant judgment unclear",
            "ERROR": "LLM call failed; needs human review",
        }[cat]
        lines.append(f"| **{cat}** | {meaning} | {len(by_category.get(cat, []))} |")
    lines.append("")

    for cat in ("ORPHANED", "ADDRESSED_OPEN", "CAUGHT", "OBSOLETE", "UNCLASSIFIED", "ERROR"):
        items = by_category.get(cat, [])
        if not items:
            continue
        lines.append(f"## {cat} — {len(items)} item(s)\n")
        lines.append("| Issue | Title | Deferred summary | Follow-up | Still relevant? | Rationale |")
        lines.append("|---|---|---|---|---|---|")
        for c, cls in sorted(items, key=lambda p: p[0].issue_number):
            lines.append(render_table_row(c, cls))
        lines.append("")

    lines.append("## Audit Record\n")
    lines.append("| Date | Auditor | Findings | Issues Created |")
    lines.append("|------|---------|----------|----------------|")
    counts = " ".join(f"{k}:{len(v)}" for k, v in sorted(by_category.items()))
    lines.append(f"| {TODAY} | Claude Opus 4.7 | {counts} | (filed manually after review) |")
    lines.append("")

    lines.append("## Notes\n")
    lines.append("- ORPHANED items in this report are candidates for the user to file as new issues.")
    lines.append("- OBSOLETE items should be acknowledged (e.g., a comment on the original issue noting the deferred work is moot).")
    lines.append("- The closing-discipline rule in root `CLAUDE.md` was added 2026-04-21 (issue #998 / PR #999) to prevent future ORPHANED items.")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    # Force UTF-8 stdout so we can print issue content with non-ASCII (em-dashes,
    # arrows, smart quotes) on Windows where the default codec is cp1252.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass  # Older Python or non-TTY; tolerate.

    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--no-llm", action="store_true",
                        help="Run phases A+B only; skip LLM classification")
    parser.add_argument("--refresh", action="store_true",
                        help="Force re-fetch the issue corpus instead of using cache")
    parser.add_argument("--limit", type=int, default=0,
                        help="If >0, only classify the first N candidates (for testing)")
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    print("Phase A: fetch corpus")
    corpus = fetch_corpus(refresh=args.refresh)
    print(f"  {len(corpus)} issues in corpus")

    print("\nPhase B: regex first pass")
    candidates = find_candidates(corpus)
    print(f"  {len(candidates)} candidate matches")

    print("\nBuilding cross-reference index")
    xref = build_xref_index(corpus)
    print(f"  {len(xref)} issues are referenced by others")

    if args.no_llm:
        print("\n--no-llm set; printing first 20 candidates and exiting")
        for c in candidates[:20]:
            print(f"  #{c.issue_number} [{c.keyword}@{c.location}] {c.issue_title}")
            print(f"    {c.context[:160]}...")
        return 0

    print("\nPhase C: LLM classification")
    cache = load_llm_cache()
    print(f"  {len(cache)} cached responses")
    classified: list[tuple[Candidate, Classification]] = []
    work = candidates if args.limit == 0 else candidates[:args.limit]
    for i, c in enumerate(work, 1):
        if i % 10 == 0 or i == 1:
            print(f"  classifying {i}/{len(work)} (#{c.issue_number}/{c.keyword})")
        xrefs = xref.get(c.issue_number, [])
        cls = classify_candidate(c, xrefs, cache)
        classified.append((c, cls))

    print(f"\n  classified {len(classified)} (errors: {sum(1 for _, cls in classified if cls.error)})")

    print("\nPhase D: writing reports")
    full = render_report(classified, "Deferred-Scope Audit (Full)", "0845", only_new_repo=False)
    REPORT_FULL.write_text(full, encoding="utf-8")
    print(f"  wrote {REPORT_FULL.relative_to(DATA_DIR.parent)}")

    new_repo = render_report(classified, "Deferred-Scope Audit — New Repo Creation Subset", "0846", only_new_repo=True)
    REPORT_NEW_REPO.write_text(new_repo, encoding="utf-8")
    print(f"  wrote {REPORT_NEW_REPO.relative_to(DATA_DIR.parent)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
