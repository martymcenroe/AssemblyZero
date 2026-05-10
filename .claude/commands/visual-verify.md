---
description: Vision-API-driven UI/output verification — does the screenshot match the design intent?
argument-hint: "<screenshot-path> [<criteria-path> | --against <reference-image>]"
scope: project
---

# Visual Verify

**Purpose:** Verify that a rendered screenshot matches its design intent. Two modes:

1. **Criteria mode** — compare a screenshot against a markdown criteria file (text-based acceptance: "needle is centered horizontally", "background is solid black", etc.).
2. **Reference mode** — compare a screenshot against a reference image (pixel/layout/color drift detection).

Used when the testing workflow's pytest+coverage assertions can't say whether the rendered output looks right. For GUI features, the testing workflow can have 100% test coverage on pure logic and still ship something visually broken — `/visual-verify` closes that gap.

**Model hint:** Use **Sonnet** for verification. Multimodal vision is sufficient; reasoning over a single image doesn't need Opus.

**Cost:** ~$0.01–0.05 per verification (one image + ~500 words of context per call).

---

## Help

Usage:

| Form | Mode | Effect |
|---|---|---|
| `/visual-verify <png> <criteria.md>` | Criteria | Verifies the PNG against acceptance criteria in the markdown file. |
| `/visual-verify <png> --against <ref.png>` | Reference | Compares PNG against a reference image; reports drift. |
| `/visual-verify <png>` | Criteria (auto-detect) | Looks for `<png-stem>.criteria.md` in the same directory. Falls back to inline criteria from the user prompt if missing. |

**Examples:**

- `/visual-verify renders/gauge_demo.png renders/gauge_demo.criteria.md` — explicit criteria file.
- `/visual-verify out.png --against design/target_gauge.png` — reference-image diff.
- `/visual-verify out.png` — auto-resolve to `out.criteria.md` next to it.

**Argument validation:**
- Screenshot path: must exist; must be a `.png`, `.jpg`, `.jpeg`, or `.webp` file.
- Criteria path (mode 1): must exist; must be a `.md` file.
- Reference path (mode 2, after `--against`): must exist; must be an image file.

If validation fails, return a clear message and STOP.

---

## Execution

### Mode 1: Criteria Mode

#### Step 1: Read inputs

```
Read screenshot file (this loads the image visually)
Read criteria file (this loads acceptance text)
```

If the criteria file is missing AND the user hasn't provided inline criteria, return:

```
NO CRITERIA — provide either:
  - a path to a markdown criteria file (e.g., `out.criteria.md`)
  - inline text in the prompt naming acceptance dimensions

Cannot verify "looks right" without an acceptance reference.
```

#### Step 2: Apply visual reasoning

Look at the screenshot. For each acceptance criterion in the markdown:

1. Determine PASS / FAIL / UNCLEAR based on what's visible.
2. If FAIL or UNCLEAR, write one specific sentence: what's actually visible and why it doesn't match.
3. Do NOT speculate about pixel-precise measurements you can't see — say UNCLEAR instead.

#### Step 3: Output structured verdict

```markdown
## Visual Verification — Criteria Mode

**Screenshot:** {path}
**Criteria source:** {path or "inline"}
**Date:** {YYYY-MM-DD}

### Per-Criterion Results

| # | Criterion | Result | Notes |
|---|---|---|---|
| 1 | {criterion 1 short text} | PASS / FAIL / UNCLEAR | {sentence if not PASS} |
| 2 | ... | ... | ... |

### Overall Verdict

[ ] **PASS** — all criteria satisfied; ready to ship.
[ ] **NEEDS_REVIEW** — one or more UNCLEAR criteria; human gate.
[ ] **FAIL** — at least one criterion clearly fails.

Mark exactly one option with [x].

### Recommendations (if FAIL or NEEDS_REVIEW)

1. {Specific change the implementer should make}
2. {...}
```

### Mode 2: Reference Mode

#### Step 1: Read both images

```
Read screenshot file (the candidate)
Read reference file (the target)
```

#### Step 2: Apply visual comparison

For each of the following dimensions, judge whether the screenshot matches the reference:

| Dimension | What to look for |
|---|---|
| **Layout** | Position of major elements (window chrome, gauge body, controls). Misalignment beyond ~5% of canvas dimensions is FAIL. |
| **Composition** | Same elements present? Missing tick marks, missing telltale needles, missing labels? |
| **Color** | Hue/saturation match within visual tolerance. Hard cuts (e.g., black bg vs. dark gray) are FAIL. |
| **Typography** | Font style, weight, and approximate size match? |
| **Sizing/proportion** | Aspect ratios of major elements. Off by >10% is FAIL. |

You cannot do pixel-level diffing — you're a vision model, not ImageMagick. Judge perceptually.

#### Step 3: Output structured verdict

```markdown
## Visual Verification — Reference Mode

**Screenshot:** {path}
**Reference:** {path}
**Date:** {YYYY-MM-DD}

### Drift Analysis

| Dimension | Match | Notes |
|---|---|---|
| Layout | YES / NO / PARTIAL | {what differs, if anything} |
| Composition | YES / NO / PARTIAL | {missing or extra elements} |
| Color | YES / NO / PARTIAL | {color differences} |
| Typography | YES / NO / PARTIAL | {font differences} |
| Sizing/proportion | YES / NO / PARTIAL | {size/ratio differences} |

### Overall Verdict

[ ] **PASS** — visually equivalent to reference; minor perceptual differences only.
[ ] **NEEDS_REVIEW** — partial drift on 1-2 dimensions; human gate.
[ ] **FAIL** — at least one dimension has clear mismatch.

Mark exactly one option with [x].

### Recommendations (if FAIL or NEEDS_REVIEW)

1. {Specific change to bring the screenshot closer to the reference}
2. {...}
```

---

## Use in Tests (Important)

This skill is invoked manually by an operator. To use it AS PART OF the testing workflow (i.e., inside an executable assertion that runs in pytest), the test should call out to a vision-API helper that wraps the same prompt — NOT shell out to `/visual-verify`. The skill itself is for ad-hoc operator runs. A Python wrapper is a future enhancement (separate issue).

The right pattern for a test:

```python
from assemblyzero.utils.visual_verify import verify_against_criteria

def test_gauge_renders_correctly(tmp_path):
    out_png = tmp_path / "gauge.png"
    render_gauge(value=50, output=out_png)

    verdict = verify_against_criteria(
        out_png,
        criteria_path="tests/visual/criteria/gauge_at_50.md",
    )
    assert verdict.passed, verdict.failure_summary()
```

Until `verify_against_criteria` exists (out of scope for v1), tests that need visual gates either (a) defer to manual `/visual-verify` runs or (b) use a placeholder skip-marker until the wrapper lands.

**Anti-pattern:** writing `# manual: visually inspect` in a test plan. Standard 0020 §5.3 lists "manual inspection" in the human-delegation patterns the validator BLOCKs on. Use this skill (or its future Python wrapper) inside an executable assertion instead.

---

## Verdict Format Reference

The structured outputs above (criteria mode and reference mode) should be matched exactly so that downstream tooling can parse them. The fields and section headers must be stable across versions.

A future standard `0022-visual-verification.md` can capture this format formally if/when the skill gains scripted callers. Until then, the format defined here is the source of truth.

---

## Future Enhancements (out of scope for v1)

- **Python wrapper** that calls Anthropic / Gemini multimodal APIs directly so tests can `assert verify_against_criteria(...).passed`.
- **Reference-image generation** — given a textual description, generate a target image up-front (Nano Banana / Gemini 3 Image / similar), commit it as the test fixture, then `/visual-verify --against` that fixture during implementation. Closes the design ↔ delivery gap.
- **Batch mode** — verify multiple screenshots against a directory of criteria files in one call.
- **Diff visualization** — when reference mode reports FAIL on layout, produce an annotated diff PNG.

These are tracked as separate issues, not bundled here.

---

## Notes

- v1 is markdown-only — the agent uses its own multimodal vision when invoked.
- The skill outputs structured markdown for the operator to read; no JSON/machine output yet.
- For boostgauge specifically, criteria files for each phase of the speed-run go in `boostgauge/tests/visual/criteria/` (relative to that repo, not AZ).
- The criteria-mode `auto-detect` resolution for `<png-stem>.criteria.md` is a convenience for the speed-run; explicit paths are always safer.
