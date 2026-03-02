---
repo: martymcenroe/AssemblyZero
issue: 534
url: https://github.com/martymcenroe/AssemblyZero/issues/534
fetched: 2026-03-01T22:18:27.536919Z
---

# Issue #534: feat: Spelunking Audits — deep verification that reality matches claims

## The Problem

Current audits (08xx series) have two failure modes:

### 1. Trust Without Verify
Audits read documentation and check boxes but never compare claims against source code reality.

**Example caught during #114 (DEATH):** The README stated _"AssemblyZero uses deterministic RAG-like techniques — not vector embeddings"_ while the codebase contained a full 14-file RAG subsystem (`assemblyzero/rag/`) with ChromaDB, vector embeddings, and `all-MiniLM-L6-v2`. The README was **lying** and no audit caught it.

### 2. Shallow Coverage
Audits confirm existence (file exists, section present) but don't assess accuracy or completeness.

**Example caught during #114:** The file inventory (`0003-file-inventory.md`) listed 11 tools and 6 ADRs. Reality: 36 tools and 14 ADRs. The inventory was 41 days stale. The wiki referenced `tools/death.py` which doesn't exist. ADR numbers 0204 and 0205 each had two files (collision). No audit caught any of this.

### What Good Looks Like

During the DEATH documentation reconciliation, the agent:
- **Globbed** directories to count actual files vs. claimed counts
- **Grepped** source code to verify documented behavior against implementation
- **Read** actual module code to understand what the system really does
- **Cross-referenced** wiki claims against filesystem reality
- **Found** that 5 of the 12 personas had no implementation status markers despite being merged

This is **spelunking** — going underground, shining a light into the actual codebase, and comparing what you find to what the surface claims.

---

## Proposal: Two-Layer Spelunking System

### Layer 1: Automated Probes (Janitor-style)

Concrete, repeatable checks that run automatically and catch obvious drift:

| Probe | What It Checks |
|-------|----------------|
| **Inventory Drift** | Count files in `tools/`, `docs/adrs/`, `docs/standards/` and compare to `0003-file-inventory.md` claimed counts |
| **Dead References** | Grep docs/wiki for file paths (e.g., `tools/death.py`) and verify each path exists on disk |
| **README-vs-Reality** | Extract technical claims from README (e.g., "not vector embeddings") and grep codebase for contradictions |
| **ADR Collision** | Scan `docs/adrs/` for duplicate number prefixes |
| **Persona Status** | Cross-reference Dramatis-Personae.md implementation markers against actual merged PRs/code |
| **Stale Timestamps** | Flag any doc with "Last Updated" more than 30 days old |

These could be new janitor probes or a dedicated spelunking probe category.

### Layer 2: Agent-Guided Deep Dives

Scheduled or triggered investigations where an agent spelunks a specific domain:

| Trigger | What the Agent Does |
|---------|---------------------|
| **Post-implementation** | DEATH-style reconciliation: read the code that was merged, verify docs match |
| **Quarterly architecture review** | Agent reads every architecture doc, compares to actual module structure |
| **Pre-release** | Deep verification that README, wiki, and ADRs accurately describe the shipping system |
| **On suspicion** | When a shallow audit flags something "off," escalate to spelunking depth |

The agent uses the same techniques that worked during #114: Glob for file discovery, Grep for claim verification, Read for deep understanding, and cross-referencing between docs and code.

---

## Proposed Standard: 0015-spelunking-audit-standard.md

A new standard (not a new audit series) that defines the spelunking protocol and provides hooks for existing 08xx audits to opt in:

### Core Principle: "Open the Box"
> An audit that reads the label without opening the box is not an audit. It's a inventory check.

### Spelunking Protocol
1. **Claim Extraction** — Identify specific factual claims in the document under audit
2. **Source Verification** — For each claim, identify the source of truth (code, filesystem, API)
3. **Reality Check** — Compare claim to source. Record match/mismatch/stale
4. **Drift Score** — Percentage of claims that match reality. Target: >90%

### Audit Integration
Each existing 08xx audit can declare spelunking checkpoints:
```yaml
spelunking:
  - claim: "11 tools in tools/"
    verify: "glob tools/*.py | wc -l"
  - claim: "6 ADR files"
    verify: "glob docs/adrs/*.md | wc -l"
```

---

## Deliverables

- [ ] Standard `0015-spelunking-audit-standard.md` — defines the protocol
- [ ] At least 3 automated spelunking probes (Inventory Drift, Dead References, ADR Collision)
- [ ] Integration hooks for existing audits (opt-in spelunking checkpoints)
- [ ] Retrofitted spelunking layer on 0837 (README compliance) and 0838 (broken references)
- [ ] Agent-guided spelunking skill or audit mode (e.g., `/audit --deep`)

## Dependencies

- #114 (DEATH) — provides the methodology and examples
- #94 (Janitor) — automated probes may extend the janitor probe registry

## References

- Issue #114 — where spelunking was performed manually and found 6+ documentation lies
- ADR-0201 — Adversarial Audit Philosophy ("audits exist to find violations, not confirm compliance")
- The current 08xx audit series
- Lu-Tze's janitor probes (ADR-0204)

---

> *"The first step to wisdom is to call things by their right names. The second step is to verify they still deserve those names."*