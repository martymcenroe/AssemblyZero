# Innovation Workflow: The Scout (External Intelligence)

**Context:** We have successfully implemented internal governance (Issue/LLD/Implementation workflows). However, our current "Audit" system (`08xx`) is purely reactive and insular—it only checks what we have *already written*. It fails to bring in new knowledge from the outside world.

## Problem

**The "Not Invented Here" Failure Mode:**
We often solve complex problems (e.g., "How to persist agent state") from first principles, unaware that a highly-starred GitHub repository solved it better six months ago.

* *Result:* We maintain inferior, custom implementations of solved problems.
* *Missing Capability:* We have no automated way to say, "Look at the world, find the best pattern for X, and tell me how we fall short."

## Goal

Create `tools/run_scout_workflow.py`, a proactive research agent that acts as an **External Intelligence Gatherer**.

**Core Function:**

1. **Hunt:** Search GitHub/Web for solutions to a specific problem.
2. **Analyze:** Download and read the architecture of top solutions.
3. **Compare:** Diff the external best practice against our internal implementation.
4. **Report:** File an "Innovation Brief" detailing the gap.

## Proposed Architecture

### 1. The State Graph (`assemblyzero/workflows/scout/graph.py`)

* **Input:** `research_topic` (e.g., "LangGraph persistence patterns"), `internal_target` (optional file path, e.g., `assemblyzero/core/state.py`).
* **Nodes:**
* **N0_Explorer:**
* Tools: `Google Search`, `github_search` (Search for "python langgraph persistence stars:>500").
* Action: Identifies Top-3 relevant repositories/articles.


* **N1_Extractor:**
* Action: Scrapes `README.md`, `architecture.md`, or key code files from the target URLs.
* Context: Summarizes the "External Standard" (how the world does it).


* **N2_Gap_Analyst:**
* Input: "External Standard" + `internal_target` (our code).
* Prompt: "Compare the External Standard to our `assemblyzero/core/state.py`. Identify 3 specific ways we are deficient (Complexity, Performance, Reliability)."


* **N3_Innovation_Scribe:**
* Action: Formats the findings into a standard **Brief Template**.
* Output: Creates `ideas/active/innovation-{topic}.md`.





### 2. The Innovation Brief Template

The workflow does *not* change code. It produces a decision artifact:

```markdown
# Innovation Opportunity: {Topic}

## External Standard
Top Solution: {Repo Name} ({Stars} stars)
Key Pattern: Uses `sqlite-vss` for vector check-pointing.

## Internal Gap
Our Approach: JSON dumps to disk.
Deficiency:
1. No semantic search capability.
2. Race conditions on file write (Solved by SQLite WAL in external pattern).

## Recommendation
[ ] Adopt `sqlite-vss` pattern (Est: 4 hours)
[ ] Ignore (Complexity cost too high)

```

### 3. The CLI Runner (`tools/run_scout_workflow.py`)

* **Usage:**
```bash
python tools/run_scout_workflow.py \
  --topic "secure api key rotation python" \
  --internal assemblyzero/core/gemini_client.py

```



## Success Criteria

* [ ] The workflow can find a relevant GitHub repo given a topic.
* [ ] It successfully reads the external code/docs without hallucinating features.
* [ ] It produces a Markdown brief that accurately identifies a deficiency in our current code.
* [ ] **Metric:** The user learns something new about their own stack from the report.

