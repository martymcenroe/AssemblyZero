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

    Issue #775: Primary structured parse with regex fallback.
    Clamps verdict to _FEEDBACK_VERDICTS; remaps out-of-enum to UNKNOWN.
    Emits counter metric on fallback (REQ-3, T150).
    """
    try:
        data = json.loads(raw)
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
        logger.warning("Structured feedback parse failed (%s); falling back to regex", e)
        logger.debug("verdict_schema.regex_fallback parser=feedback")
        result = _regex_fallback_feedback(raw)
        # Clamp verdict to FEEDBACK_SCHEMA enum
        if result["verdict"] not in _FEEDBACK_VERDICTS:
            result["verdict"] = "UNKNOWN"
        return result


def parse_structured_review_spec(raw: str) -> ReviewSpecResult:
    """Parse structured JSON review-spec response into ReviewSpecResult.

    Issue #775: Primary structured parse with regex fallback.
    Clamps verdict to _REVIEW_SPEC_VERDICTS; remaps out-of-enum to UNKNOWN.
    Emits counter metric on fallback (REQ-3, T150).
    """
    try:
        data = json.loads(raw)
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
        logger.warning("Structured review-spec parse failed (%s); falling back to regex", e)
        logger.debug("verdict_schema.regex_fallback parser=review_spec")
        result = _regex_fallback_verdict(raw)
        verdict = result["verdict"]
        # Clamp verdict to REVIEW_SPEC_SCHEMA enum
        if verdict not in _REVIEW_SPEC_VERDICTS:
            verdict = "UNKNOWN"
        # Attempt to extract feedback_items via regex for richer fallback
        feedback_items = []
        feedback_section = _extract_section_from_markdown(raw, "Feedback")
        if not feedback_section:
            feedback_section = _extract_section_from_markdown(raw, "Required Changes")
        if not feedback_section:
            feedback_section = _extract_section_from_markdown(raw, "Blocking Issues")
        if feedback_section:
            feedback_items = re.findall(r"^(?:[-*]|\d+\.)\s+(.+)$", feedback_section, re.MULTILINE)
        return ReviewSpecResult(
            verdict=verdict,
            rationale=result["rationale"],
            feedback_items=feedback_items,
            source="regex_fallback",
        )


def parse_structured_draft_questions(raw: str) -> DraftQuestionsResult:
    """Parse structured JSON open-questions response into DraftQuestionsResult.

    Issue #775: Primary structured parse with regex fallback.
    Emits counter metric on fallback (REQ-3, T150).
    """
    try:
        data = json.loads(raw)
        if not _validate_required_keys(data, ["open_questions"]):
            raise ValueError("Missing required key: open_questions")
        return DraftQuestionsResult(
            open_questions=data["open_questions"],
            source="structured",
        )
    except (json.JSONDecodeError, ValueError, TypeError, KeyError) as e:
        logger.warning("Structured draft-questions parse failed (%s); falling back to regex", e)
        logger.debug("verdict_schema.regex_fallback parser=draft_questions")
        return _regex_fallback_draft_questions(raw)


def parse_structured_finalize_questions(raw: str) -> FinalizeQuestionsResult:
    """Parse structured JSON question-detection response into FinalizeQuestionsResult.

    Issue #775: Primary structured parse with regex fallback.
    Emits counter metric on fallback (REQ-3, T150).
    """
    try:
        data = json.loads(raw)
        if not _validate_required_keys(data, ["has_open_questions", "question_count", "questions"]):
            raise ValueError("Missing required keys")
        return FinalizeQuestionsResult(
            has_open_questions=data["has_open_questions"],
            question_count=data["question_count"],
            questions=data["questions"],
            source="structured",
        )
    except (json.JSONDecodeError, ValueError, TypeError, KeyError) as e:
        logger.warning("Structured finalize-questions parse failed (%s); falling back to regex", e)
        logger.debug("verdict_schema.regex_fallback parser=finalize_questions")
        return _regex_fallback_finalize_questions(raw)


def _regex_fallback_verdict(raw: str) -> VerdictResult:
    """Last-resort regex extraction for verdict checkbox patterns.

    Issue #775: Logs WARNING when invoked. Never raises.
    Returns verdict='UNKNOWN' if all patterns fail.
    Note: Does NOT call emit_counter — callers are responsible for metrics.
    """
    logger.warning("Using regex fallback for verdict extraction")
    if not raw or not isinstance(raw, str):
        return VerdictResult(verdict="UNKNOWN", rationale="", source="regex_fallback")
    for pattern, verdict in [
        (r"\[X\]\s*\**APPROVED\**", "APPROVED"),
        (r"\[X\]\s*\**REVISE\**", "REVISE"),
        (r"\[X\]\s*\**DISCUSS\**", "DISCUSS"),
        (r"\[X\]\s*\**BLOCKED\**", "BLOCKED"),
    ]:
        if re.search(pattern, raw, re.IGNORECASE):
            # Try to extract rationale from next paragraph
            rationale = ""
            rationale_match = re.search(
                r"(?:Rationale|Reason|Summary)[:\s]*(.+?)(?:\n\n|\n##|\Z)",
                raw,
                re.DOTALL | re.IGNORECASE,
            )
            if rationale_match:
                rationale = rationale_match.group(1).strip()
            return VerdictResult(verdict=verdict, rationale=rationale, source="regex_fallback")

    # Secondary fallback: keyword patterns (e.g., "Verdict: APPROVED")
    for keyword in ["APPROVED", "REVISE", "BLOCKED", "DISCUSS"]:
        if re.search(rf"\b{keyword}\b", raw, re.IGNORECASE):
            return VerdictResult(verdict=keyword, rationale="", source="regex_fallback")

    logger.error("Regex fallback could not extract verdict from response")
    return VerdictResult(verdict="UNKNOWN", rationale="", source="regex_fallback")


def _regex_fallback_feedback(raw: str) -> FeedbackResult:
    """Last-resort regex extraction for feedback section patterns.

    Issue #775: Logs WARNING when invoked.
    Note: verdict is NOT clamped here — caller (parse_structured_feedback)
    is responsible for clamping to the appropriate enum.
    Does NOT call emit_counter — caller handles metrics.
    """
    logger.warning("Using regex fallback for feedback extraction")
    if not raw:
        return FeedbackResult(verdict="UNKNOWN", rationale="", feedback_items=[], open_questions=[], resolved_issues=[], source="regex_fallback")
    verdict_result = _regex_fallback_verdict(raw)

    # Extract feedback items from bullet lists under Feedback/Required Changes
    feedback_items = []
    feedback_section = _extract_section_from_markdown(raw, "Feedback")
    if not feedback_section:
        feedback_section = _extract_section_from_markdown(raw, "Required Changes")
    if feedback_section:
        feedback_items = re.findall(r"^[-*]\s+(.+)$", feedback_section, re.MULTILINE)

    # Extract open questions
    open_questions = []
    oq_section = _extract_section_from_markdown(raw, "Open Questions")
    if oq_section:
        unchecked = re.findall(r"^- \[ \] (.+)$", oq_section, re.MULTILINE)
        checked = re.findall(r"^- \[X\] (.+)$", oq_section, re.MULTILINE | re.IGNORECASE)
        for q in unchecked:
            open_questions.append({"text": q.strip(), "resolved": False})
        for q in checked:
            open_questions.append({"text": q.strip(), "resolved": True})

    # Extract resolved issues
    resolved_issues = []
    ri_section = _extract_section_from_markdown(raw, "Resolved Issues")
    if not ri_section:
        ri_section = _extract_section_from_markdown(raw, "Open Questions Resolved")
    if ri_section:
        resolved_issues = re.findall(r"^[-*]\s+(.+)$", ri_section, re.MULTILINE)

    return FeedbackResult(
        verdict=verdict_result["verdict"],
        rationale=verdict_result["rationale"],
        feedback_items=feedback_items,
        open_questions=open_questions,
        resolved_issues=resolved_issues,
        source="regex_fallback",
    )


def _regex_fallback_draft_questions(raw: str) -> DraftQuestionsResult:
    """Last-resort regex extraction for open questions from draft content.

    Issue #775: Logs WARNING when invoked.
    Does NOT call emit_counter — caller handles metrics.
    """
    logger.warning("Using regex fallback for draft questions extraction")
    if not raw:
        return DraftQuestionsResult(open_questions=[], source="regex_fallback")
    open_questions = []
    oq_match = re.search(r"## Open Questions.*?(?=\n## |\Z)", raw, re.DOTALL)
    if oq_match:
        section = oq_match.group(0)
        unchecked = re.findall(r"^- \[ \] (.+)$", section, re.MULTILINE)
        checked = re.findall(r"^- \[X\] (.+)$", section, re.MULTILINE | re.IGNORECASE)
        for q in unchecked:
            open_questions.append({"text": q.strip(), "resolved": False})
        for q in checked:
            open_questions.append({"text": q.strip(), "resolved": True})
    return DraftQuestionsResult(open_questions=open_questions, source="regex_fallback")


def _regex_fallback_finalize_questions(raw: str) -> FinalizeQuestionsResult:
    """Last-resort regex extraction for question/TODO detection.

    Issue #775: Logs WARNING when invoked.
    Does NOT call emit_counter — caller handles metrics.

    Note: Lines ending with '?' must be > 5 chars to filter out bare
    punctuation or headings like "Why?" that are section titles, not
    unresolved questions. The threshold catches "TODO?" but skips "?".
    """
    logger.warning("Using regex fallback for finalize questions detection")
    if not raw:
        return FinalizeQuestionsResult(has_open_questions=False, question_count=0, questions=[], source="regex_fallback")
    questions = []
    # Detect lines ending with ? (min 6 chars to filter noise)
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped.endswith("?") and len(stripped) > 5:
            questions.append(stripped)
    # Detect TODO markers
    todo_matches = re.findall(r"^.*\bTODO\b.*$", raw, re.MULTILINE | re.IGNORECASE)
    for match in todo_matches:
        questions.append(match.strip())
    return FinalizeQuestionsResult(
        has_open_questions=len(questions) > 0,
        question_count=len(questions),
        questions=questions,
        source="regex_fallback",
    )


def _extract_section_from_markdown(content: str, section_name: str) -> str:
    """Extract content from a named markdown section.

    Issue #775: Shared helper for regex fallback section extraction.
    Returns text between a ## heading matching section_name and the next ## heading or EOF.
    The pattern uses .* after the escaped name to handle parenthetical suffixes
    like "## Open Questions (3 remaining)".
    """
    if not content:
        return ""
    pattern = rf"##\s+{re.escape(section_name)}.*?\n(.*?)(?=\n## |\Z)"
    match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else ""


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