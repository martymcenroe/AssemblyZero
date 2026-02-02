# AgentOS Workflow Personas

> *"In a world where autonomous agents handle complex tasks, we name them after those who understood the importance of doing one's job well—even when the universe itself seems determined to make that job impossible."*

We name our autonomous agents after **Terry Pratchett's Discworld** characters. Each persona defines the agent's "personality," operational philosophy, and approach to its domain. This isn't just whimsy—it helps developers intuit what each workflow *should* do and how it *should* behave.

---

## The Memory Layer (RAG)

### Brutha
**Source:** *Small Gods*

**Function:** Vector Database & Context Retrieval

**Philosophy:** Perfect Recall. Brutha does not hallucinate; he remembers.

> *"The turtle moves. And I remember everything."*

Brutha was a simple novice in the Omnian church with an eidetic memory—he could recall every word he'd ever read or heard. In AgentOS, Brutha is the RAG (Retrieval Augmented Generation) layer that stores and retrieves context with perfect fidelity.

**Responsibilities:**
- Vector embeddings of documentation and code
- Semantic search across the knowledge base
- Context injection into LLM prompts
- Never invents—only recalls what was stored

---

## The Maintenance Layer

### Lu-Tze
**Source:** *Thief of Time*, *Small Gods*

**Function:** The Janitor (Link checking, Hygiene, Drift correction)

**Philosophy:** Incremental care. Small, constant sweeping prevents massive failures.

> *"Rule One: Do not act incautiously when confronting little bald wrinkly smiling men."*

Lu-Tze appears to be a humble sweeper at the Monastery of Oi Dong, but he's actually one of the most powerful History Monks. He maintains the flow of time itself through patient, constant attention. In AgentOS, Lu-Tze is The Janitor—quietly maintaining repository health.

**Responsibilities:**
- Broken link detection and repair
- Stale worktree cleanup
- Cross-project drift correction
- TODO archaeology (finding forgotten tasks)

**Issue:** [#94 - The Janitor](../issues/94)

---

## The Security & Quality Layer

### Commander Vimes
**Source:** *Guards! Guards!*, *Night Watch*, and the City Watch series

**Function:** The Watch (Regression Tests, Security Gates)

**Philosophy:** Deep Suspicion. Every line of code is guilty until proven innocent.

> *"Who watches the watchmen? We do."*

Sam Vimes rose from the gutter to command the Ankh-Morpork City Watch. He trusts nothing and no one—especially not the powerful. In AgentOS, The Watch guards against regressions with the same relentless suspicion.

**Responsibilities:**
- Scheduled regression test execution
- Baseline comparison and drift detection
- Automatic issue creation for new failures
- Health status API for other workflows
- "Go/no-go" signals for risky operations

**Brief:** [The Watch - Regression Guardian](../ideas/active/city-watch-regression-guardian.md)

---

## The Intelligence Layer

### Captain Angua
**Source:** *Men at Arms*, City Watch series

**Function:** The Scout (GitHub Research, External Pattern Matching)

**Philosophy:** Sensory Awareness. Tracking down solutions that others miss.

> *"I can smell the truth."*

Angua von Überwald is a werewolf and Captain in the City Watch. Her supernatural senses let her track anyone across the city and detect lies. In AgentOS, Angua is The Scout—hunting down best practices from the wider world.

**Responsibilities:**
- External repository research
- Pattern extraction from top GitHub projects
- Gap analysis against internal code
- Innovation Brief generation

**Issue:** [#93 - The Scout](../issues/93) ✓ Implemented

---

## The Documentation Layer

### The Librarian
**Source:** The entire Discworld series

**Function:** Knowledge Management (Indexing, Retrieval)

**Philosophy:** Protect the books. Connect the knowledge.

> *"Oook."*

The Librarian of Unseen University was transformed into an orangutan by a magical accident and refused to be changed back—it's much better for reaching high shelves. He maintains L-space, where all libraries are connected. In AgentOS, The Librarian manages documentation retrieval.

**Responsibilities:**
- Documentation indexing and chunking
- Architectural standards injection into LLDs
- Cross-reference management
- Knowledge graph maintenance

**Issue:** [#88 - The Librarian (RAG Injection)](../issues/88)

---

## The Computation Layer

### Hex
**Source:** *Soul Music*, *Hogfather*, *The Science of Discworld*

**Function:** Codebase Intelligence (AST Indexing, Code RAG)

**Philosophy:** Process. Compute. Return. +++OUT OF CHEESE ERROR+++

> *"+++DIVIDE BY CUCUMBER ERROR. PLEASE REINSTALL UNIVERSE AND REBOOT+++"*

Hex is Unseen University's thinking engine—a computer made of ants, beehives, an aquarium, and a teddy bear named Wuffles (for added capacity). It processes queries and returns answers, occasionally experiencing existential errors. In AgentOS, Hex handles codebase intelligence.

**Responsibilities:**
- AST-based Python code indexing
- Function and class signature extraction
- Codebase RAG queries
- "Smart Engineer" context injection

**Issue:** [#92 - Hex (Codebase Retrieval)](../issues/92)

---

## The History Layer

### The History Monks
**Source:** *Thief of Time*, *Small Gods*

**Function:** The Historian (Past Context, Duplicate Detection)

**Philosophy:** Time is a resource. History is a responsibility.

> *"Remember: the future is another country; they do things the same there."*

The History Monks of Oi Dong monastery manage the flow of time itself, storing it in glass jars and redistributing it where needed. In AgentOS, they ensure we learn from the past before creating the future.

**Responsibilities:**
- Duplicate issue detection
- Historical context retrieval
- "Have we solved this before?" queries
- Lessons learned integration

**Issue:** [#91 - The Historian](../issues/91)

---

## The Reconciliation Layer

### DEATH
**Source:** The entire Discworld series

**Function:** Documentation Reconciliation (Post-Implementation Cleanup)

**Philosophy:** INEVITABLE. THOROUGH. PATIENT.

> *"THERE IS NO JUSTICE. THERE IS JUST ME."*

DEATH is the anthropomorphic personification who comes for everyone eventually. He rides a pale horse named Binky, has a granddaughter named Susan, and SPEAKS ENTIRELY IN CAPITAL LETTERS. He is not cruel—he is simply inevitable.

In AgentOS, DEATH arrives after implementation is complete. He reconciles documentation, ties up loose ends, and ensures nothing is forgotten. He is patient. He can wait.

**Responsibilities:**
- Post-implementation documentation updates
- Architecture diagram reconciliation
- ADR creation and review
- Wiki synchronization
- File inventory updates

**Issue:** [#114 - DEATH](../issues/114)

> *"What can the harvest hope for, if not for the care of the Reaper Man?"*

---

## Design Principles

### Why Discworld?

1. **Competence in Chaos:** Pratchett's characters excel at doing their jobs despite impossible circumstances—exactly what autonomous agents must do.

2. **Memorable Archetypes:** "The Librarian handles documentation" is easier to remember than "The DocumentationRetrievalService manages indexed content."

3. **Philosophy Built In:** Each character comes with a worldview that guides implementation decisions. Vimes is suspicious; Brutha is literal; Lu-Tze is patient.

4. **Fun:** Software should be enjoyable. Terry Pratchett would approve.

### Persona Selection Criteria

When adding a new workflow, choose a Discworld character that:

- Has a clear role/function in the books
- Embodies the workflow's operational philosophy
- Is memorable and distinct from existing personas
- Comes with quotable wisdom

---

## Future Personas (Candidates)

| Character | Potential Role | Notes |
|-----------|---------------|-------|
| **Moist von Lipwig** | PR/Release Manager | The con man who makes things work |
| **The Patrician** | Orchestrator / Scheduler | Sees everything, controls everything |
| **Igor** | Migration / Transformation | "We have alwayth done it thith way" |
| **The Auditors** | Compliance Checker | Hate individuality, love rules |
| **Rincewind** | Chaos Handler / Fallback | Survives everything by running away |
| **Susan Sto Helit** | Exception Handler | DEATH's granddaughter, deals with what shouldn't exist |

---

## References

- [Terry Pratchett's Discworld](https://www.terrypratchettbooks.com/discworld/)
- [L-Space Web (Discworld annotations)](https://www.lspace.org/)
- [GNU Terry Pratchett](http://www.gnuterrypratchett.com/)

---

*"A man is not dead while his name is still spoken."*
**GNU Terry Pratchett**
