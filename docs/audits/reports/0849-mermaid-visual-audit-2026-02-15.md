# 0849 Mermaid Visual Audit — 2026-02-15

**Auditor:** Claude Opus 4.6
**Scope:** All repos with mermaid diagrams (wiki + README + docs)
**Method:** Playwright screenshots (dark + light mode) + source review
**Standards:** 0004 Mermaid Diagram Standards (§4, §5, §7, §8)

---

## Summary

| Metric | Count |
|--------|-------|
| Repos with mermaid | 14 (excl. worktree duplicate) |
| Wiki pages inspected (Playwright) | 10 |
| README pages inspected (Playwright) | 2 |
| Diagrams with violations | 3 |
| Diagrams with potential issues | 2 |
| Diagrams passing all checks | All others |

---

## Scope

~94 diagrams across 50 files in 14 repos (excluding AssemblyZero-325 worktree duplicate).

---

## Violations

### V1: Aletheia.wiki / Architecture.md — Diagram 1

**Violation:** `flowchart LR` with backward edges (§4, §7.1, §7.3)

| Check | Light | Dark | Notes |
|-------|-------|------|-------|
| Arrows visible | PASS | PASS | |
| No overlapping | PASS | PASS | |
| Labels readable | PASS | PASS | |
| Edge labels legible | — | PASS | |
| Fill colors visible | N/A | N/A | No custom fills |
| No crossing backward edges | **FAIL** | **FAIL** | D→C, C→B, B→A all backward |
| Flow direction clear | **FAIL** | **FAIL** | LR with bidirectional confuses flow |
| Subgraph boundaries clean | PASS | PASS | |
| Renders correctly | PASS | PASS | |
| TD layout compliance | **FAIL** | **FAIL** | Uses `flowchart LR` with backward edges |

**Source (line 10):**
```
flowchart LR
    D --> C    (Bedrock → Lambda — backward)
    C --> B    (Lambda → CloudFront — backward)
    B --> A    (CloudFront → Extension — backward)
```

**Fix:** Convert to `flowchart TD` with dashed response arrows per §7.2:
```
flowchart TD
    A[Browser Extension] -->|HTTPS| B[CloudFront + WAF]
    B --> C[Lambda<br/>Python 3.12]
    C --> D[Bedrock<br/>Nova Micro]
    C -.-> E[(DynamoDB)]
    D -.-> C
    C -.-> B
    B -.-> A
```

**Repo:** martymcenroe/Aletheia (wiki)
**Action:** Auto-fix (straightforward conversion)

---

### V2: AssemblyZero.wiki / How-the-AgentOS-Learns.md — Diagram 1 (line 24)

**Violation:** `flowchart LR` with backward cycle (§7.3, §7.4)

| Check | Result | Notes |
|-------|--------|-------|
| TD layout compliance | **FAIL** | `flowchart LR` with `UPDATE -.-> LLD` backward edge |
| No crossing backward edges | **FAIL** | Feedback loop goes right-to-left |

**Source:** `UPDATE -.->|Next LLD uses improved template| LLD` — cycle from end back to start.

**Mitigating factor:** Uses dashed arrow (partial §7.4 compliance, solution 3). The diagram conceptually represents a cycle, which is hard to avoid.

**Fix options:**
1. Convert to TD layout (preferred)
2. Replace backward edge with label annotation per §7.4 solution 1:
   `UPDATE["Update Templates<br/>(feeds next LLD cycle)"]`

---

### V3: AssemblyZero.wiki / How-the-AgentOS-Learns.md — Diagram 2 (line 147)

**Violation:** `flowchart LR` with backward cycle in "Before" subgraph (§7.3, §7.4)

**Source:** `G1 -->|BLOCK: wrong format| D1` — Gemini blocks back to Draft (backward edge within subgraph)

**Fix:** Convert to TD or use §7.4 solution 1 (label annotation instead of backward edge).

---

### V4: AssemblyZero.wiki / Implementation-Workflow.md — Diagram 2 (line 105)

**Violation:** `graph LR` with backward cycle (§7.3, §7.4)

**Source:** `N["Next Test"] --> T["Write Test"]` — TDD cycle goes right-to-left in LR layout.

**Fix:** Convert to TD.

---

### V5: unleashed-wiki / Security-Model.md — Trust Boundaries Diagram

**Violation:** Pastel fills with reduced dark mode contrast (§8.6)

**Source fills:**
- `#fee2e2` (light red pastel) — visible but low contrast on dark background
- `#fef3c7` (light yellow pastel) — borderline visibility on dark background
- `#dcfce7` (light green pastel) — borderline visibility on dark background

**Visual inspection:** Dark mode screenshot confirms fills are visible but with notably reduced contrast compared to the saturated mid-tones used in other unleashed wiki diagrams. Per §8.6: "Avoid low-contrast fills" and "saturated mid-tones work best in both modes."

**Fix:** Replace pastel fills with saturated mid-tones:
- `#fee2e2` → `#ef4444` (red) with `color:#fff`
- `#fef3c7` → `#fbbf24` (yellow) with `color:#000`
- `#dcfce7` → `#4ade80` (green) with `color:#000`

---

## Potential Issues (Not Violations)

### P1: unleashed / README.md — Diagram 1

**Issue:** Mermaid diagram renders with excessive whitespace below the content. Large blank canvas area between "The Solution" diagram and "Key Features" section.

**Source review:** Diagram source is clean (TD, all labels quoted, good custom fills). This appears to be a GitHub mermaid rendering/viewbox sizing issue, not a source problem.

**Action:** Monitor. May resolve with GitHub mermaid renderer updates. Consider filing GitHub community issue if persistent.

---

### P2: unleashed-wiki / Architecture.md — Three-Thread Design (Diagram 1)

**Issue:** Complex diagram with multiple subgraphs and crossing arrows. At full-page zoom, some arrows from "terminal" appear to route near/through subgraph boxes. Possible §8.3 (lines behind boxes).

**Action:** Needs closer inspection at higher zoom. May require structural simplification if confirmed.

---

## Passing — Highlights

### unleashed-wiki / Home.md — Architecture Diagram

| Check | Light | Dark | Notes |
|-------|-------|------|-------|
| Arrows visible | PASS | PASS | Clear solid and dashed arrows |
| No overlapping | PASS | PASS | |
| Labels readable | PASS | PASS | |
| Edge labels legible | PASS | PASS | "raw PTY bytes", "Yes", "No", "ALLOW", "BLOCK" |
| Fill colors visible | PASS | PASS | Green, blue, yellow all high-contrast both modes |
| No crossing backward edges | PASS | PASS | |
| Flow direction clear | PASS | PASS | TD layout, natural top-down reading |
| Subgraph boundaries clean | PASS | PASS | "Unleashed PTY Wrapper" boundary clear |
| Renders correctly | PASS | PASS | |
| TD layout compliance | PASS | PASS | `flowchart TD` |

### unleashed-wiki / Sentinel-Safety-Gate.md — Three-Tier Architecture

| Check | Light | Dark | Notes |
|-------|-------|------|-------|
| Fill colors visible | PASS | PASS | Blue diamonds, green/red/yellow boxes — all high-contrast |
| TD layout compliance | PASS | PASS | |
| All other checks | PASS | PASS | |

### unleashed / README.md — Source Review

| Check | Result | Notes |
|-------|--------|-------|
| TD layout | PASS | `flowchart TD` |
| All labels quoted | PASS | Every label in double quotes |
| Custom fills | PASS | #4ade80 green, #ef4444 red, #fbbf24 yellow, #60a5fa blue, #a78bfa purple |
| Dark mode fills | PASS | All colors are saturated mid-tones per §8.6 guidance |

---

## LR Layout Audit (Source Review)

All `flowchart LR` / `graph LR` diagrams checked for backward edges:

| File | Line | Backward Edges? | Verdict |
|------|------|----------------|---------|
| Aletheia.wiki/Architecture.md | 10 | YES (D→C, C→B, B→A) | **VIOLATION** |
| AZ.wiki/How-the-AgentOS-Learns.md | 24 | YES (UPDATE→LLD) | **VIOLATION** |
| AZ.wiki/How-the-AgentOS-Learns.md | 147 | YES (G1→D1) | **VIOLATION** |
| AZ.wiki/Ponder-Stibbons.md | 80 | No | OK — unidirectional |
| AZ.wiki/Multi-Agent-Orchestration.md | 136,180,187,194 | No | OK — simple horizontal |
| AZ.wiki/Implementation-Workflow.md | 105 | No | OK — unidirectional |
| AZ.wiki/History-Monks.md | 128, 146 | No | OK — unidirectional |
| AZ.wiki/Hex-Codebase-Intelligence.md | 113 | No | OK — unidirectional |
| HermesWiki/Deployment.md | 173 | No | OK — unidirectional |
| HermesWiki/Architecture.md | 255 | No | OK — unidirectional |
| Hermes.wiki/Knowledge-Base.md | 116 | No | OK — unidirectional |
| RCA-wiki/Architecture.md | 15, 34, 107 | No | OK — data pipeline |
| Aletheia/ADR-defense-funnel.md | 94 | No | OK — unidirectional with shared sink |
| Aletheia/10137-lambda-latency.md | 51 | No | OK — pipeline |
| Aletheia/10132-support-email.md | 54 | No | OK — pipeline |
| Aletheia/10113-naked-python.md | 76 | No | OK — pipeline |
| Aletheia/10007-observability.md | 203 | No | OK — pipeline |
| Aletheia/10100-firefox-compat.md | 66 | No | OK — pipeline |
| Aletheia/1080-wire-agent.md | 86 | No | OK — pipeline |
| Aletheia/10001f-deployment.md | 62 | No | OK — pipeline |

---

## Not Inspectable

| Repo | Reason |
|------|--------|
| martymcenroe/Hermes wiki | 404 — wiki not published on GitHub |
| Talos, career, dispatch, maintenance | Private repos — not authenticated in Playwright |
| GentlePersuader, CS512_link_predictor | Private repos — not authenticated |
| Aletheia docs/ (65 files) | Source-audited only (too many for individual Playwright screenshots) |
| AssemblyZero docs/ (621 files) | Source-audited only (sampling approach) |
| RCA-PDF docs/ (121 files) | Source-audited only |

---

## Custom Fill Colors Audit (§8.6)

Files with custom `style ... fill:` directives checked for dark mode compatibility:

| File | Colors Used | Light Mode | Dark Mode |
|------|------------|------------|-----------|
| unleashed/README.md | #4ade80, #ef4444, #fbbf24, #60a5fa, #a78bfa | PASS | PASS |
| unleashed-wiki/Home.md | Green, blue, yellow, purple | PASS | PASS |
| unleashed-wiki/Sentinel-Safety-Gate.md | Blue, green, red, yellow | PASS | PASS |
| unleashed-wiki/Architecture.md | Green, yellow | PASS | PASS |
| unleashed-wiki/Security-Model.md | Has custom fills | Source only | Source only |
| unleashed-wiki/Session-Mirror.md | Has custom fills | Source only | Source only |
| unleashed-wiki/Version-History.md | Has custom fills | Source only | Source only |

All unleashed wiki custom fills use saturated mid-tones per §8.6 guidance. No §8.6 violations found.

---

## Actions

| # | Action | Repo | Priority |
|---|--------|------|----------|
| 1 | Fix Aletheia wiki Architecture.md — convert LR→TD | Aletheia wiki | P1 (public-facing) |
| 2 | Fix unleashed-wiki Security-Model.md — replace pastel fills with saturated mid-tones | unleashed wiki | P1 (§8.6) |
| 3 | Fix AZ wiki How-the-AgentOS-Learns.md — 2 diagrams with backward LR edges | AssemblyZero wiki | P2 |
| 4 | Fix AZ wiki Implementation-Workflow.md diagram 2 — backward LR edge | AssemblyZero wiki | P2 |
| 5 | Investigate unleashed README oversized canvas | unleashed | P3 |
| 6 | Closer inspection of unleashed wiki Architecture three-thread diagram | unleashed wiki | P3 |
| 7 | Publish Hermes wiki or document as intentionally unpublished | martymcenroe/Hermes | P3 |

---

## Source Audit — Full Scope (from background agent)

~94 diagrams audited across all repos. Additional findings from comprehensive source review:

- **16 total `graph/flowchart LR` diagrams** across all repos
- **13 unidirectional LR** (acceptable per §7.3 for pipelines)
- **3 LR with backward edges** (violations V2, V3, V4)
- **22 custom style fill directives** — all in unleashed-wiki
- **3 files with unquoted labels** (Governance-Gates.md, How-the-AgentOS-Learns.md, Talos architecture) — low severity, renders correctly but inconsistent with §5.1
- **hermes-docs is a full duplicate of HermesWiki-wiki** — maintenance concern, not a mermaid issue
