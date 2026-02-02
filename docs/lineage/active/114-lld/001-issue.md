# Issue #114: DEATH: Documentation Reconciliation (Post-Implementation Cleanup)

# DEATH: Documentation Reconciliation

**Persona:** DEATH (*The entire Discworld series*)
> *"THERE IS NO JUSTICE. THERE IS JUST ME."*

## Philosophy
DEATH comes at the end. He is inevitable. He is thorough. Nothing escapes him.

In AgentOS, DEATH arrives after implementation is complete to ensure all documentation is reconciled, all loose ends are tied, and nothing is forgotten.

> *"I COULD KILL YOU. BUT THEN THE UNIVERSE WOULD NEVER KNOW WHY YOU DIED. AND I FIND THAT... INTERESTING."*

---

## Context
We are implementing a family of Discworld-themed autonomous workflows:

| Issue | Persona | Function |
|-------|---------|----------|
| #113 | Brutha | Vector database infrastructure |
| #88 | The Librarian | Documentation retrieval |
| #91 | History Monks | Past context checking |
| #92 | Hex | Codebase RAG |
| #93 | Captain Angua | External intelligence (Scout) ✓ |
| #94 | Lu-Tze | Repository hygiene (Janitor) |
| Brief | Commander Vimes | Regression guardian (Watch) |

## Objective
AFTER IMPLEMENTING THESE WORKFLOWS, CONSOLIDATE AND UPDATE ALL ARCHITECTURE DOCUMENTATION.

## Tasks

### ARCHITECTURE DIAGRAMS
- [ ] Create/update system architecture diagram showing all personas
- [ ] Create data flow diagram showing how Brutha serves Librarian and Hex
- [ ] Create workflow interaction diagram

### ADRS
- [ ] ADR for Discworld persona naming convention
- [ ] ADR for RAG architecture (Brutha as foundation)
- [ ] ADR for local-only embeddings (no data egress)
- [ ] Review existing ADRs for alignment

### WIKI UPDATES
- [ ] Verify Workflow-Personas.md stays current
- [ ] Update architecture pages with new diagrams
- [ ] Cross-link all workflow documentation
- [ ] Update Home.md with workflow overview

### FILE INVENTORY
- [ ] Update `docs/0003-file-inventory.md` with all new files

### README
- [ ] Update main README with workflow family overview

## Timing
THIS IS A POST-IMPLEMENTATION TASK. DO NOT START UNTIL THE CORE WORKFLOW ISSUES ARE COMPLETE.

DEATH IS PATIENT. DEATH CAN WAIT.

> *"HUMANS NEED FANTASY TO BE HUMAN. TO BE THE PLACE WHERE THE FALLING ANGEL MEETS THE RISING APE."*

---

*What can the harvest hope for, if not for the care of the Reaper Man?*