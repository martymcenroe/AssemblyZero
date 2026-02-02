# AgentOS Workflow Personas

> *"In a world where autonomous agents handle complex tasks, we name them after those who understood the importance of doing one's job well—even when the universe itself seems determined to make that job impossible."*

We name our autonomous agents after **Terry Pratchett's Discworld** characters. Each persona defines the agent's "personality," operational philosophy, and approach to its domain. This isn't just whimsy—it helps developers intuit what each workflow *should* do and how it *should* behave.

---

## The Orchestration Layer

### The Great God Om
**Source:** *Small Gods*

**Function:** The Orchestrator (The Human User)

**Philosophy:** Pure Intent. The agents exist to serve the Will, not the other way around. Without the User, the system is just a shell.

> *"I. Am. The. Great. God. Om!"* (said while being a small tortoise)

In *Small Gods*, Om discovers that his vast church has become an autonomous bureaucracy—going through the motions of worship while ignoring the actual god. He spends most of the book as a tortoise, shouting at the sky, frustrated that his "system" doesn't listen to him anymore.

This is **exactly** what Human-in-the-Loop feels like. You are the source of all power (Intent), but your agents (The Quisition/The System) have their own momentum. AgentOS exists to ensure the system *actually listens* to Om.

**The Relationship:**
- **Om (You)** provides Intent
- **Brutha (Memory)** carries Om, remembers everything
- **The Agents** execute the Will

Without Om, the agents are just a bureaucracy performing empty rituals. With Om, they have purpose.

**Note:** Avoiding eagles is generally good policy for software managers.

---

## The Visibility Layer

### Lord Vetinari (The Patrician)
**Source:** The entire City Watch series, *Going Postal*, *Making Money*

**Function:** Work Organization & Project Management (GitHub Projects, Stage Tracking)

**Philosophy:** Information is power. Know where every piece is on the board.

> *"Down there are people who will follow any dragon, worship any god, ignore any iniquity. All out of a conditions called 'not wanting to be noticed.'"*

Lord Havelock Vetinari is the Patrician of Ankh-Morpork—the tyrant who makes the trains run on time. In his office, he maintains a wall map of the city with little markers showing where everyone is and what they're doing. He doesn't control everything directly; he *organizes* it so the pieces work together. He sees patterns others miss and moves pieces before problems arise.

In AgentOS, The Patrician manages work visibility across all projects. He maintains the board, tracks what stage each piece of work is in, and ensures nothing falls through the cracks. He doesn't do the work—he ensures you can *see* the work.

**Responsibilities:**
- GitHub Projects board management
- Stage transitions (Backlog → Ready → In Progress → Done)
- Cross-project visibility and reporting
- Work-in-progress tracking
- "Who is doing what" status queries
- Automated stage updates when workflows complete

**The Wall Map:**
```
┌──────────┐    ┌─────────┐    ┌─────────────┐    ┌──────┐
│ Backlog  │ -> │  Ready  │ -> │ In Progress │ -> │ Done │
└──────────┘    └─────────┘    └─────────────┘    └──────┘
```

**Runbook:** [0912 - GitHub Projects](../docs/runbooks/0912-github-projects.md)

**Brief:** [GitHub Project Stage Automation](../ideas/active/github-project-stage-automation.md)

> *"Taxation, gentlemen, is very much like dairy farming. The task is to extract the maximum amount of milk with the minimum amount of moo."*

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

## The Deletion Layer

### Lord Downey
**Source:** *Men at Arms*, *Pyramids*

**Function:** The Inhumer (Safe Deletion of Code & Tests)

**Philosophy:** Precision. Remove the target, remove the evidence (tests), leave the system cleaner than you found it.

> *"We prefer the word 'inhumed'. 'Deleted' implies a lack of style."*

Lord Downey is the head of the Ankh-Morpork Assassins' Guild—the most refined, well-educated, and *professional* organization in the city. They don't "kill"; they "inhume." Every contract is executed with precision, leaving no witnesses and no evidence.

In AgentOS, Lord Downey handles the safe deletion of deprecated code. When you `rm` a file, that's thuggery. When you *inhume* it, you remove the target, its tests, and all references—leaving the codebase cleaner than you found it.

**Responsibilities:**
- Identify all tests that guard a target file
- Find all files that import/reference the target
- Remove target and related tests atomically
- Clean import statements from referencing files
- Verify build stability post-deletion
- Rollback if witnesses remain (tests fail)

**Brief:** [The Inhumer - Safe Deletion Workflow](../ideas/active/inhumer-deletion-workflow.md)

**Guild Motto:** *Nil Mortifi Sine Lucre* — No killing without profit

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
