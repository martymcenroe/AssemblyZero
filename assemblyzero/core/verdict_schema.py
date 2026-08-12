"""Structured verdict schema for Gemini reviewer responses.

Issue #492: Structured output for verdicts.
Issue #503: Structured two-strike stagnation detection.
Issue #775: Add 5 schemas, 5 TypedDicts, 6 parse helpers, regex fallbacks.

Provides a JSON schema that Gemini's response_schema parameter can enforce,
replacing fragile regex-based verdict parsing with structured JSON output.
"""

from difflib import SequenceMatcher

import json
import logging
import re
from typing import TypedDict

logger = logging.getLogger(__name__)

VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {
            "type": "string",
            "enum": ["APPROVED", "REVISE", "BLOCKED"],
        },
        "rationale": {
            "type": "string",
        },
        "blocking_issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "section": {"type": "string"},
                    "issue": {"type": "string"},
                    "severity": {
                        "type": "string",
                        "enum": ["BLOCKING", "HIGH", "SUGGESTION"],
                    },
                },
                "required": ["section", "issue", "severity"],
            },
        },
        "suggestions": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["verdict", "rationale"],
}

# --- New schemas for #775 ---

FEEDBACK_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["APPROVED", "REVISE", "DISCUSS"]},
        "rationale": {"type": "string"},
        "feedback_items": {
            "type": "array",
            "items": {"type": "string"},
        },
        "open_questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "resolved": {"type": "boolean"},
                },
                "required": ["text", "resolved"],
            },
        },
        "resolved_issues": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["verdict", "rationale", "feedback_items", "open_questions"],
}

REVIEW_SPEC_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["APPROVED", "REVISE", "BLOCKED"]},
        "rationale": {"type": "string"},
        "feedback_items": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["verdict", "rationale", "feedback_items"],
}

DRAFT_QUESTIONS_SCHEMA = {
    "type": "object",
    "properties": {
        "open_questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "resolved": {"type": "boolean"},
                },
                "required": ["text", "resolved"],
            },
        },
    },
    "required": ["open_questions"],
}

FINALIZE_QUESTIONS_SCHEMA = {
    "type": "object",
    "properties": {
        "has_open_questions": {"type": "boolean"},
        "question_count": {"type": "integer"},
        "questions": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["has_open_questions", "question_count", "questions"],
}

# Enum allow-lists per schema — used by fallback to clamp verdicts.
# Issue #775: Prevents _regex_fallback_verdict returning BLOCKED
# in a FEEDBACK_SCHEMA context where only APPROVED/REVISE/DISCUSS are valid.
_FEEDBACK_VERDICTS = {"APPROVED", "REVISE", "DISCUSS"}
_REVIEW_SPEC_VERDICTS = {"APPROVED", "REVISE", "BLOCKED"}


class VerdictResult(TypedDict):
    """Parse result for verdict extraction. Issue #775."""
    verdict: str
    rationale: str
    source: str


class FeedbackResult(TypedDict):
    """Parse result for full feedback extraction. Issue #775."""
    verdict: str
    rationale: str
    feedback_items: list[str]
    open_questions: list[dict]
    resolved_issues: list[str]
    source: str


class ReviewSpecResult(TypedDict):
    """Parse result for spec review extraction. Issue #775."""
    verdict: str
    rationale: str
    feedback_items: list[str]
    source: str


class DraftQuestionsResult(TypedDict):
    """Parse result for draft open questions. Issue #775."""
    open_questions: list[dict]
    source: str


class FinalizeQuestionsResult(TypedDict):
    """Parse result for finalize question detection. Issue #775."""
    has_open_questions: bool
    question_count: int
    questions: list[str]
    source: str


def parse_structured_verdict(response_text: str) -> dict | None:
    """Parse a structured JSON verdict from reviewer response.

    Attempts to parse the response as JSON matching VERDICT_SCHEMA.
    Returns None if parsing fails (caller should fall back to regex).

    Args:
        response_text: Raw response text from the reviewer.

    Returns:
        Parsed verdict dict with keys: verdict, summary, blocking_issues,
        suggestions. Returns None if response is not valid JSON or
        doesn't contain required fields.
    """
    if not response_text or not response_text.strip():
        return None

    text = response_text.strip()

    # Try direct JSON parse
    try:
        data = json.loads(text)
        if isinstance(data, dict) and "verdict" in data:
            if "rationale" not in data:
                data["rationale"] = ""
            return data
    except json.JSONDecodeError:
        pass

    # Try extracting JSON from markdown code fences
    json_match = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            if isinstance(data, dict) and "verdict" in data:
                if "rationale" not in data:
                    data["rationale"] = ""
                return data
        except json.JSONDecodeError:
            pass

    return None


class StructuredContractError(RuntimeError):
    """A structured ask returned output that does not honor its schema.

    Standard 0028 (operator ruling 2026-08-10): ask structured, get
    structured, or reject. Raised by the strict parsers in place of the
    retired regex fallbacks. Carries what a halt banner needs (#2197
    legibility): the parser's name, the reason, and a bounded excerpt.
    The caller surfaces it as an error; the stage retry machinery is the
    bounded re-ask.
    """

    def __init__(self, parser: str, reason: str, raw: str = ""):
        excerpt = (raw or "").strip().replace("\n", " ")[:160]
        self.parser = parser
        self.reason = reason
        self.excerpt = excerpt
        detail = f" | response begins: {excerpt!r}" if excerpt else " | response empty"
        super().__init__(
            f"structured contract violated in {parser}: {reason}{detail}"
        )


def _loads_lenient(raw: str) -> dict:
    """json.loads that tolerates a fenced or prose-wrapped JSON object.

    Issue #1843: a model told to emit JSON very often wraps it in ```json
    fences or adds a sentence around it. A bare json.loads then fails at
    char 0, the caller silently drops to its regex fallback, and a
    "structured" contract degrades to 100% fallback with nobody the wiser.

    Raises:
        json.JSONDecodeError: when no JSON object can be recovered, so
            callers' existing except clauses behave exactly as before.
    """
    text = (raw or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fenced = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
    if fenced:
        return json.loads(fenced.group(1))

    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        return json.loads(text[start : end + 1])

    raise json.JSONDecodeError("no JSON object found in response", text or "", 0)


def _validate_required_keys(data: dict, required: list[str]) -> bool:
    """Check that all required keys are present in parsed data.

    Issue #775: Manual key validation instead of jsonschema dependency.
    """
    return all(key in data for key in required)


def _validate_enum(value: str, allowed: list[str] | set[str]) -> bool:
    """Check that a value is in the allowed enum list."""
    return value in allowed


def parse_structured_feedback(raw: str) -> FeedbackResult:
    """Parse structured JSON feedback response into FeedbackResult.

    Standard 0028: strict. The response either parses and validates against
    FEEDBACK_SCHEMA or this raises StructuredContractError — there is no
    degraded parse. The caller surfaces the rejection; the stage retry
    machinery re-asks.
    """
    try:
        data = _loads_lenient(raw)
        if not _validate_required_keys(data, ["verdict", "rationale", "feedback_items", "open_questions"]):
            raise ValueError("Missing required keys")
        if not _validate_enum(data["verdict"], _FEEDBACK_VERDICTS):
            raise ValueError(f"Invalid verdict: {data['verdict']}")
        return FeedbackResult(
            verdict=data["verdict"],
            rationale=data["rationale"],
            feedback_items=data.get("feedback_items", []),
            open_questions=data.get("open_questions", []),
            resolved_issues=data.get("resolved_issues", []),
            source="structured",
        )
    except (json.JSONDecodeError, ValueError, TypeError, KeyError) as e:
        raise StructuredContractError("feedback", str(e), raw) from e


def parse_structured_review_spec(raw: str) -> ReviewSpecResult:
    """Parse structured JSON review-spec response into ReviewSpecResult.

    Standard 0028: strict. Parses and validates against REVIEW_SPEC_SCHEMA
    or raises StructuredContractError — no degraded parse.
    """
    try:
        data = _loads_lenient(raw)
        if not _validate_required_keys(data, ["verdict", "rationale", "feedback_items"]):
            raise ValueError("Missing required keys")
        if not _validate_enum(data["verdict"], _REVIEW_SPEC_VERDICTS):
            raise ValueError(f"Invalid verdict: {data['verdict']}")
        return ReviewSpecResult(
            verdict=data["verdict"],
            rationale=data["rationale"],
            feedback_items=data.get("feedback_items", []),
            source="structured",
        )
    except (json.JSONDecodeError, ValueError, TypeError, KeyError) as e:
        raise StructuredContractError("review_spec", str(e), raw) from e


def _iter_section_lines(text: str, *titles: str):
    """Yield the stripped body lines of the first heading matching a title.

    A deterministic walk of OUR OWN markdown format — headings the templates
    define — implemented with string operations. Not a parser of model
    output and not a fallback (standard 0028 §3). Heading match is
    case-insensitive and tolerates parenthetical suffixes like
    "## Open Questions (3 remaining)".
    """
    wanted = tuple(t.casefold() for t in titles)
    in_section = False
    for line in (text or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            heading = stripped.lstrip("#").strip().rstrip(":").casefold()
            in_section = heading.startswith(wanted)
            continue
        if in_section:
            yield stripped


#: What a drafter writes in the Open Questions section to mean "there are
#: none". The template scaffolds that section as an unchecked checkbox, so a
#: drafter with nothing to ask fills the scaffold rather than deleting it
#: (#2232: four drafts out of four in one run wrote "- [ ] None").
_NONE_PLACEHOLDERS = frozenset({"none", "n/a", "na", "none at this time", "nothing"})


def is_none_placeholder(text: str) -> bool:
    """True when an Open Questions entry means "there are none".

    One predicate, imported by every caller, because the alternative is what
    #2232 measured: ``review.py`` filtered "- [ ] None" and read the draft as
    having no questions, ``finalize.py`` read the same line as an unresolved
    question and blocked, and an APPROVED draft died between them. Two
    detectors over one document must not disagree, so there is one detector.

    Matching ignores case, surrounding whitespace, trailing punctuation and
    markdown emphasis, and it accepts a placeholder carrying an aside, since
    "None - scope is well-defined" is how drafters actually write it.

    What it must NOT swallow is a real sentence that merely begins with the
    word: "None of the thresholds are specified" is a question. The rule that
    separates them is the character after the token -- a dash, colon, comma or
    bracket introduces an aside, whereas a space followed by more sentence
    does not.
    """
    cleaned = (text or "").strip().strip("*_`").strip()
    cleaned = cleaned.rstrip(".!?,;:").strip().casefold()
    if cleaned in _NONE_PLACEHOLDERS:
        return True
    for separator in ("—", "–", " - ", ":", ";", ",", "("):
        if separator in cleaned:
            head = cleaned.split(separator, 1)[0].strip().rstrip(".!?,;:").strip()
            if head in _NONE_PLACEHOLDERS:
                return True
    return False


def scan_open_questions_section(text: str) -> DraftQuestionsResult:
    """Deterministic checkbox scan of a document's ``## Open Questions``.

    Replaces parse_structured_draft_questions (standard 0028): the inputs
    here were never model JSON — they are the pipeline's own markdown
    documents (the drafter's document response; the rendered verdict), so
    "structured parse with fallback" was a fiction and the section scan was
    always the real mechanism. Now it is the named mechanism.
    """
    open_questions: list[dict] = []
    for line in _iter_section_lines(text, "open questions"):
        if line.startswith("- [ ]"):
            question = line[len("- [ ]"):].strip()
            if question:
                open_questions.append({"text": question, "resolved": False})
        elif line[: len("- [x]")].casefold() == "- [x]":
            question = line[len("- [x]"):].strip()
            if question:
                open_questions.append({"text": question, "resolved": True})
    return DraftQuestionsResult(open_questions=open_questions, source="document_scan")


def scan_residual_questions(text: str) -> FinalizeQuestionsResult:
    """Deterministic residual question/TODO scan of generated content.

    Replaces parse_structured_finalize_questions (standard 0028): the input
    is already-generated document content, not a model response — finalize
    validates its own artifact, a scan, not a parse. Lines ending with '?'
    must be > 5 chars to filter bare punctuation and headings like "Why?";
    any line carrying a TODO marker counts.
    """
    if not text:
        return FinalizeQuestionsResult(
            has_open_questions=False, question_count=0, questions=[],
            source="document_scan",
        )
    questions: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.endswith("?") and len(stripped) > 5:
            questions.append(stripped)
    for line in text.splitlines():
        stripped = line.strip()
        words = {w.strip(":,.;!?()[]").casefold() for w in stripped.split()}
        if "todo" in words:
            questions.append(stripped)
    return FinalizeQuestionsResult(
        has_open_questions=len(questions) > 0,
        question_count=len(questions),
        questions=questions,
        source="document_scan",
    )


# The _regex_fallback_* scrapers and their _extract_section_from_markdown
# helper were retired by standard 0028 (operator ruling 2026-08-10): a
# structured ask that returns unstructured output is rejected and re-asked,
# never scraped. The #2199 incident is the case study — the fallback masked
# a rendering defect for eight days and converted twelve approvals into
# dead rolls.


def same_blocking_issues(
    current_feedback: str,
    previous_feedback: str,
    similarity_threshold: float = 0.8,
) -> bool:
    """Check if two verdicts raise the same blocking issues.

    Issue #503: Structured two-strike stagnation detection.

    Strategy:
    1. Try structured JSON comparison first (section + issue identity)
    2. Fall back to line-overlap heuristic if either verdict is unstructured

    Args:
        current_feedback: Current verdict text (may be JSON or markdown).
        previous_feedback: Previous verdict text (may be JSON or markdown).
        similarity_threshold: SequenceMatcher ratio for fuzzy match (default 0.8).

    Returns:
        True if the same blocking issues appear in both verdicts (stagnation).
    """
    if not current_feedback or not previous_feedback:
        return False

    current_parsed = parse_structured_verdict(current_feedback)
    previous_parsed = parse_structured_verdict(previous_feedback)

    # Both structured: use section+issue identity comparison
    if current_parsed and previous_parsed:
        return _structured_stagnation(
            current_parsed, previous_parsed, similarity_threshold
        )

    # Fallback: line-overlap heuristic (legacy)
    return _line_overlap_stagnation(current_feedback, previous_feedback)


def _structured_stagnation(
    current: dict, previous: dict, threshold: float
) -> bool:
    """Compare blocking issues structurally.

    Two verdicts are stagnant if >50% of current blocking issues
    match a previous issue by section + fuzzy issue text similarity.
    """
    current_issues = current.get("blocking_issues", [])
    previous_issues = previous.get("blocking_issues", [])

    if not current_issues:
        return False

    matched = 0
    for c_issue in current_issues:
        c_section = c_issue.get("section", "").lower().strip()
        c_text = c_issue.get("issue", "").lower().strip()

        for p_issue in previous_issues:
            p_section = p_issue.get("section", "").lower().strip()
            p_text = p_issue.get("issue", "").lower().strip()

            section_match = (
                c_section == p_section
                or SequenceMatcher(None, c_section, p_section).ratio() >= threshold
            )
            text_match = SequenceMatcher(None, c_text, p_text).ratio() >= threshold

            if section_match and text_match:
                matched += 1
                break

    return matched / len(current_issues) > 0.5


def _line_overlap_stagnation(current: str, previous: str) -> bool:
    """Legacy line-overlap heuristic for unstructured verdicts.

    Issue #486: Original two-strike detection.
    """
    current_lines = {
        line.strip().lower()
        for line in current.splitlines()
        if line.strip() and len(line.strip()) > 10
    }
    previous_lines = {
        line.strip().lower()
        for line in previous.splitlines()
        if line.strip() and len(line.strip()) > 10
    }

    if not current_lines:
        return False

    overlap = current_lines & previous_lines
    return len(overlap) / len(current_lines) > 0.5