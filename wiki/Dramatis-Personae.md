# Dramatis Personae

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

This is **exactly** what Human-in-the-Loop feels like. You are the source of all power (Intent), but your agents (The Quisition/The System) have their own momentum. AssemblyZero exists to ensure the system *actually listens* to Om.

**The Relationship:**
- **Om (You)** provides Intent
- **Brutha (Memory)** carries Om, remembers everything
- **The Agents** execute the Will

Without Om, the agents are just a bureaucracy performing empty rituals. With Om, they have purpose.

**Note:** Avoiding eagles is generally good policy for software managers.

---

## The Pipeline Layer

### Moist von Lipwig
**Source:** *Going Postal*, *Making Money*, *Raising Steam*

**Function:** The Postmaster (End-to-End Pipeline Orchestration)

**Philosophy:** Keep the messages moving. A message delayed is a message betrayed.

> *"Do you not know that a man is not dead while his name is still spoken?"*

Moist von Lipwig was a con man sentenced to hang—until Lord Vetinari offered him a choice: take over the failing Post Office, or take the door marked "certain death." Moist chose the Post Office. He didn't understand mail. He didn't care about stamps. But he understood *systems*, and he understood that the Post Office wasn't about letters—it was about **promises kept**.

The Grand Trunk (the Clacks) was faster. It was modern. It was also *broken*—cutting corners, losing messages, letting the infrastructure rot while the quarterly numbers looked good. Moist made the Post Office work not by being faster, but by being *reliable*. Every message delivered. Every promise kept.

In AssemblyZero, Moist orchestrates the end-to-end pipeline:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          THE GRAND TRUNK                                │
│                                                                         │
│   ┌───────┐    ┌───────┐    ┌───────┐    ┌───────┐    ┌───────┐       │
│   │ Issue │───►│  LLD  │───►│ Spec  │───►│ Build │───►│  PR   │       │
│   │ Tower │    │ Tower │    │ Tower │    │ Tower │    │ Tower │       │
│   └───────┘    └───────┘    └───────┘    └───────┘    └───────┘       │
│       ▼            ▼            ▼            ▼            ▼           │
│    Brief        Design       Concrete      Code         Ship          │
│                              Details                                   │
└─────────────────────────────────────────────────────────────────────────┘
```

Each tower receives a message and passes it on. The message changes form—issue becomes LLD, LLD becomes spec, spec becomes code—but the *promise* remains: this issue will become working software.

**Responsibilities:**
- End-to-end workflow orchestration (Issue → LLD → Spec → Implementation → PR)
- Stage handoff management
- Failure recovery and retry logic
- Progress tracking across the pipeline
- "Where is my message?" status queries
- Ensuring no work is lost in transit

**The Clacks Protocol:**
```
GNU = "send the message on"
G = "pass it on even if you're not the target"
N = "do not log it"
U = "when it reaches the end, send it back"
```

In AssemblyZero: messages (work items) flow through the pipeline, and like the names in the Clacks overhead, they are never forgotten until delivered.

**Issue:** [#305 - End-to-End Orchestration Workflow](https://github.com/martymcenroe/AssemblyZero/issues/305)

> *"The post was about a thing that was so simple that it didn't need a name. It was about the ordinary, everyday people who worked in the Post Office. It was about keeping the mail moving."*

---

## The Visibility Layer

### Lord Vetinari (The Patrician)
**Source:** The entire City Watch series, *Going Postal*, *Making Money*

**Function:** Work Organization & Project Management (GitHub Projects, Stage Tracking)

**Philosophy:** Information is power. Know where every piece is on the board.

> *"Down there are people who will follow any dragon, worship any god, ignore any iniquity. All out of a conditions called 'not wanting to be noticed.'"*

Lord Havelock Vetinari is the Patrician of Ankh-Morpork—the tyrant who makes the trains run on time. In his office, he maintains a wall map of the city with little markers showing where everyone is and what they're doing. He doesn't control everything directly; he *organizes* it so the pieces work together. He sees patterns others miss and moves pieces before problems arise.

In AssemblyZero, The Patrician manages work visibility across all projects. He maintains the board, tracks what stage each piece of work is in, and ensures nothing falls through the cracks. He doesn't do the work—he ensures you can *see* the work.

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

**Assistant: Drumknott**

Every Patrician needs a Drumknott. Rufus Drumknott is Vetinari's personal secretary—the man who maintains the card index, knows where every document is filed, and can retrieve any piece of information in seconds. He doesn't make decisions; he ensures the Patrician has everything needed *to* make decisions.

> *"Drumknott was not a man who showed emotion, but if he had been, he might have looked slightly pained at this point."*

In AssemblyZero, Drumknott is the indexing and retrieval subsystem that powers Vetinari's visibility. He maintains the cross-references, updates the tracking cards, and ensures no piece of work is ever truly lost in the filing system.

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

Brutha was a simple novice in the Omnian church with an eidetic memory—he could recall every word he'd ever read or heard. In AssemblyZero, Brutha is the RAG (Retrieval Augmented Generation) layer that stores and retrieves context with perfect fidelity.

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

Lu-Tze appears to be a humble sweeper at the Monastery of Oi Dong, but he's actually one of the most powerful History Monks. He maintains the flow of time itself through patient, constant attention. In AssemblyZero, Lu-Tze is The Janitor—quietly maintaining repository health.

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

Sam Vimes rose from the gutter to command the Ankh-Morpork City Watch. He trusts nothing and no one—especially not the powerful. In AssemblyZero, The Watch guards against regressions with the same relentless suspicion.

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

Angua von Überwald is a werewolf and Captain in the City Watch. Her supernatural senses let her track anyone across the city and detect lies. In AssemblyZero, Angua is The Scout—hunting down best practices from the wider world.

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

The Librarian of Unseen University was transformed into an orangutan by a magical accident and refused to be changed back—it's much better for reaching high shelves. He maintains L-space, where all libraries are connected. In AssemblyZero, The Librarian manages documentation retrieval.

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

Hex is Unseen University's thinking engine—a computer made of ants, beehives, an aquarium, and a teddy bear named Wuffles (for added capacity). It processes queries and returns answers, occasionally experiencing existential errors. In AssemblyZero, Hex handles codebase intelligence.

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

The History Monks of Oi Dong monastery manage the flow of time itself, storing it in glass jars and redistributing it where needed. In AssemblyZero, they ensure we learn from the past before creating the future.

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

In AssemblyZero, Lord Downey handles the safe deletion of deprecated code. When you `rm` a file, that's thuggery. When you *inhume* it, you remove the target, its tests, and all references—leaving the codebase cleaner than you found it.

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

In AssemblyZero, DEATH arrives after implementation is complete. He reconciles documentation, ties up loose ends, and ensures nothing is forgotten. He is patient. He can wait.

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

### Igor — The Transplant Surgeon
**Source:** *Carpe Jugulum*, *The Fifth Elephant*, *Monstrous Regiment*

**Potential Role:** Migration & Transformation

**Philosophy:** "We have alwayth done it thith way"—while quietly revolutionizing everything.

> *"A good Igor ith worth hith weight in thpare organth."*

The Igors are a clan of servants from Überwald, all named Igor, all speaking with a lisp, all practicing "spare parts surgery." By the time an Igor reaches maturity, most of their body parts have been swapped repeatedly within the clan. They pass down good organs and deft hands through generations like other families pass heirlooms.

When an Igor's master inevitably angers the mob with torches, the Igor is never there—they always know the hidden back door. Through experience with mad scientists, a good Igor feels danger in advance and knows when to pack up and find a new master.

**Why He Fits Migration:**
- Takes working parts from old systems and transplants them into new ones
- "Broken down for thpareth"—harvesting reusable components from deprecated code
- Always has a backup plan (literally—backup hearts and lightning rods down the spine)
- The [We-R-Igors](https://wiki.lspace.org/We-R-Igors) agency: "A Spare Hand When Needed"
- Knows when a system is doomed and how to preserve what matters

**Potential Responsibilities:**
- Database migrations
- API version transitions
- Legacy system decomposition
- "Transplanting" functionality between services
- Backup and recovery orchestration

---

### Mr. Shine — Him Diamond
**Source:** *Thud!*

**Potential Role:** Premium Processing / Crystal Clarity

**Philosophy:** Perfect clarity. Perfect reflection. Perfect thought.

> *"Mr Shine! Him diamond!"*

On rare occasions, a troll made of diamond is born. Diamond trolls are vastly more intelligent than other trolls—their reflective bodies ward off heat, and since troll brains are silicon-based, cold means fast. A diamond troll is the indisputable king of the trolls, whether it wants to be or not.

[Mr. Shine](https://wiki.lspace.org/Mr._Shine) spent most of his life undercover in Ankh-Morpork, wearing black velvet gloves and robes to hide his blinding brilliance. He helped avert war between trolls and dwarfs at Koom Valley. He is compassionate—he tried to help Brick, a drug addict, come clean.

**Why He Fits Premium/Clarity:**
- Thinks with perfect clarity where others are sluggish
- Operates best under pressure (literally—formed under immense pressure)
- Commands respect without demanding it
- Sees through problems that confuse others
- "Can be quite hard to see if that is his wish"

**Potential Responsibilities:**
- Priority queue processing
- Complex decision arbitration
- Cross-faction (cross-team) mediation
- High-stakes review escalation

---

### Captain Carrot Ironfoundersson
**Source:** *Guards! Guards!*, the City Watch series

**Potential Role:** Validation & Literal Interpretation

**Philosophy:** The law is the law. The rules are the rules. Simple.

> *"Personal isn't the same as important."*

[Carrot](https://wiki.lspace.org/Carrot_Ironfoundersson) is a 6'6" human who was raised by dwarfs in the mines. His dwarfish name, Kzad-bhat, means "Head Banger"—a logical nickname for a two-meter man in tunnels built for four-foot dwarfs. When his adoptive father grew worried that Carrot needed to be around his own kind, he sent him to join the Ankh-Morpork City Watch.

On his first day, Carrot arrested the head of the Thieves' Guild for thievery. He takes everything literally and believes in obeying rules. Despite this—or because of it—everyone likes him. His open honesty throws people off; they're certain he must be pulling a fast one.

Carrot is almost certainly the rightful heir to the throne of Ankh-Morpork. He has no interest in being king. He likes being a watchman.

**Why He Fits Validation:**
- Takes specifications literally—exactly as written
- Doesn't interpret, doesn't assume, doesn't "know what you meant"
- If the rules say X, he does X
- Finds bugs others miss because he doesn't skip steps
- Somehow makes rigid rule-following work through sheer goodwill

**Potential Responsibilities:**
- Schema validation
- Contract enforcement
- Literal spec compliance checking
- Input sanitization (no assumptions, ever)

---

### Granny Weatherwax
**Source:** The Witches series, *Lords and Ladies*, *Carpe Jugulum*

**Potential Role:** Root Cause Analysis / Headology

**Philosophy:** Don't fix symptoms. Fix *people*.

> *"I can't be having with this."*

[Esmerelda "Granny" Weatherwax](https://wiki.lspace.org/Granny_Weatherwax) is the most powerful witch on the Disc—and she knows it, which is her greatest weakness and her greatest strength. She practices "headology," the art of making people think they fixed themselves. Why use magic when you can use *psychology*?

The trolls call her "She Who Must Be Avoided." The dwarfs call her "Go Around the Other Side of the Mountain." The Nac Mac Feegle call her "The Hag O' Hags."

**Why She Fits Root Cause Analysis:**
- Never treats symptoms, always finds the real problem
- Makes the system fix *itself* through careful prodding
- "Headology"—debugging by making the code realize its own bugs
- Terrifyingly effective at finding what you're hiding
- Knows when NOT to intervene (the hardest part)

**Potential Responsibilities:**
- Post-mortem analysis
- Debugging orchestration
- "Why did this really fail?" investigation
- Performance bottleneck identification

---

### The Nac Mac Feegle
**Source:** *The Wee Free Men*, the Tiffany Aching series

**Potential Role:** Chaos Engineering / Aggressive Testing

**Philosophy:** "Nae king! Nae quin! Nae laird! We willna be fooled again!"

> *"Crivens!"*

The Nac Mac Feegle are six-inch-tall blue pictsies who fight everything, drink anything, and steal whatever isn't nailed down (and some things that are). They believe they died and went to heaven—this world is their afterlife, which explains why they fear nothing.

They fight in a style best described as "attack the biggest one first and don't stop until everything stops moving." A Feegle can headbutt through a door. A hundred Feegles can headbutt through *reality*.

**Why They Fit Chaos Engineering:**
- They WILL find your weakness
- No respect for boundaries, conventions, or "you can't do that"
- Aggressively test every assumption
- If your system can survive the Feegles, it can survive anything
- "We're gonna test it until it screams"

**Potential Responsibilities:**
- Chaos engineering
- Fuzz testing
- Boundary condition attacks
- "What if we just... hit it really hard?"

---

### The Luggage
**Source:** *The Colour of Magic*, the Rincewind series

**Potential Role:** Persistent Storage / Asset Protection

**Philosophy:** Follow. Protect. *Consume threats.*

> *(menacing silence, hundreds of tiny feet)*

The Luggage is a chest made of sapient pearwood, a magical tree that produces wood that is *alive* and *hostile*. It follows its owner across dimensions, through time, to the edge of the Disc and back. It has hundreds of tiny legs. It can outrun anything. It eats people who threaten its owner.

Open The Luggage and you'll find whatever you need—fresh clothes, weapons, snacks. Or you'll find teeth. It depends on The Luggage's mood.

**Why It Fits Persistent Storage:**
- Follows you *everywhere*, across any boundary
- Stores whatever you need, retrieves it when you need it
- Absolutely, violently loyal
- Cannot be destroyed, lost, or stolen
- Don't try to open it without permission

**Potential Responsibilities:**
- Artifact storage and retrieval
- Cross-environment state persistence
- Asset protection (aggressively)
- "My stuff goes where I go"

---

### Ponder Stibbons — The Compositor
**Source:** *Moving Pictures*, *Lords and Ladies*, the Unseen University series

**Potential Role:** Mechanical Auto-Fix Layer

**Philosophy:** Someone has to do the actual work while the faculty argues about it.

> *"Ponder Stibbons was the only one who did any real work."*

[Ponder Stibbons](https://wiki.lspace.org/Ponder_Stibbons) is the Reader in Invisible Writings at Unseen University—he sees what's there but shouldn't be. While the Archchancellor and senior wizards debate philosophy over dinner, Ponder quietly manages Hex (the thinking engine), runs the actual experiments, and fixes things so the institution keeps functioning.

He's the youngest faculty member but the most senior in terms of actual knowledge. He's learned that the best way to get things done is to do them yourself and present the results as a fait accompli.

**Why He Fits Auto-Fix:**
- Does the real work while others argue about methodology
- Manages Hex—understands mechanical systems
- "Reader in Invisible Writings"—sees errors others miss
- Fixes things quietly so the system keeps running
- Presents corrected results, not complaints

**Potential Responsibilities:**
- Auto-fix title issue numbers
- Normalize section header formats
- Apply path corrections from validation suggestions
- Standardize formatting (whitespace, checkboxes, code fences)
- Clean drafts before they reach review

**Issue:** [#307 - Ponder Stibbons - The Compositor](https://github.com/martymcenroe/AssemblyZero/issues/307)

> *"The senior wizards had long since learned that the best way to get Ponder to do something was to tell him it was impossible."*

---

### Other Candidates

| Character | Potential Role | Notes |
|-----------|---------------|-------|
| **The Auditors** | Compliance Checker | Hate individuality, love rules |
| **Rincewind** | Chaos Handler / Fallback | Survives everything by running away |
| **Susan Sto Helit** | Exception Handler | DEATH's granddaughter, deals with what shouldn't exist |
| **Mr. Pump** | Task Enforcement | The golem who ensures Moist completes his tasks |
| **Adora Belle Dearheart** | Workforce Management | Runs the Golem Trust, manages autonomous workers |
| **Nobby Nobbs** | Edge Case Handling | Carries papers proving he's human (technically qualifies) |
| **Gaspode** | Debug Logging | The cynical talking dog who comments on everything |
| **Cohen the Barbarian** | Legacy System Support | 90 years old, still deadly, "back in my day..." |
| **Igorina** | Precision Fixes | Female Igor at The Times, surgical precision on text |
| **The Compositors** | Print-Ready Formatting | Typesetters at The Times, make copy publish-ready |
| **Tiffany Aching** | Onboarding / Training | Young witch who learns by doing, trains the next generation |
| **Nanny Ogg** | User Experience | Makes everyone comfortable, knows what people *actually* want |

---

## References

- [Terry Pratchett's Discworld](https://www.terrypratchettbooks.com/discworld/)
- [L-Space Web (Discworld annotations)](https://www.lspace.org/)
- [GNU Terry Pratchett](http://www.gnuterrypratchett.com/)

---

*"A man is not dead while his name is still spoken."*
**GNU Terry Pratchett**
