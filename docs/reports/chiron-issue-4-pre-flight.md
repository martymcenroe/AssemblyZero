### 1. Pinned SHAs
*   **AssemblyZero main:** `c8e31c271e3753e30cbb8214e6239ae027680c31`
*   **Chiron main:** `e7496d7221b00dfc70779e61a0cd9fd6798cc75f`

### 2. Verdict
**FAIL_PREDICTED**
I predict the command will fail to produce a correct, green PR because the pipeline will hallucinate AssemblyZero architectural context into the Chiron Patent-Agent CLI generation, and risks a fatal SQLite checkpoint collision on `issue-4`.

### 3. Top Preconditions or Failure Points
1.  **H2 (RAG Vector Store Context Bleed)** - *Likelihood: 100%, Severity: Critical.* `RAGConfig` hardcodes a relative path. Because the orchestrator launches from AssemblyZero, it will read AssemblyZero's vector store and ground Chiron's Issue #4 in AssemblyZero's source code, destroying the LLD output.
2.  **H1 (State-Keyed-by-Issue Collision)** - *Likelihood: High, Severity: Critical.* `orchestrate.py` does not inject the `ASSEMBLYZERO_WORKFLOW_DB` environment variable. The checkpointer defaults to the global `~/.assemblyzero/requirements_workflow.db`. If AssemblyZero Issue #4 was ever orchestrated on this machine, Chiron Issue #4 will collide with it on the `thread_id` slug, causing LangGraph state corruption.
3.  **PR Creation Explicit-Flags Violation** - *Likelihood: Medium, Severity: High.* `assemblyzero/workflows/orchestrator/stages.py` omits the `--repo` flag during PR creation, violating the established AssemblyZero canonical workaround for the upstream `gh pr create` bug (GraphQL: No commits between main and main).

### 4. Hypothesis Ledger

*   **H1 (state-keyed-by-issue collision)**: **CONFIRMED**.
    *   *Rationale:* `tools/run_requirements_workflow.py` respects the environment variable, but the orchestrator does not set it, meaning the DB falls back to the home directory and keys purely by issue slug.
    *   *Citation 1 (`tools/run_requirements_workflow.py:81`):*
        `    if db_path_env := os.environ.get("ASSEMBLYZERO_WORKFLOW_DB"):`
    *   *Citation 2 (`assemblyzero/workflows/orchestrator/graph.py`):*
        Refuted existence of `os.environ["ASSEMBLYZERO_WORKFLOW_DB"]` assignment anywhere in the orchestrator execution path.

*   **H2 (RAG vector-store context bleed)**: **CONFIRMED**.
    *   *Rationale:* The `RAGConfig` defaults to a relative path and is invoked without overriding the path to the target repo.
    *   *Citation 1 (`assemblyzero/rag/config.py:25-26`):*
        `    vector_store_path: Path = field(`
        `        default_factory=lambda: Path(".assemblyzero/vector_store")`
    *   *Citation 2 (`assemblyzero/workflows/implementation_spec/nodes/coder_node.py:43`):*
        `        from assemblyzero.rag.codebase_retrieval import retrieve_codebase_context  # noqa: PLC0415`

*   **H3 (workspace_context.docs_dir resolves to AZ root)**: **REFUTED** (as an active risk).
    *   *Rationale:* The property returns the AZ root, but it is dead-code latent; writers bypass the property and write to `target_repo` directly.
    *   *Citation (`assemblyzero/workflows/requirements/audit.py:696`):*
        `    lld_dir = target_repo / LLD_ACTIVE_DIR`

*   **H4 (provenance assumes origin + github.com)**: **CONFIRMED** (but safe).
    *   *Rationale:* Chiron's origin remote literally matches the required substring.
    *   *Citation (Independent Verification):* `git -C C:\Users\mcwiz\Projects\Chiron remote get-url origin` returns `https://github.com/martymcenroe/chiron.git`.

*   **H5 (ideas/active assumption)**: **REFUTED**.
    *   *Rationale:* The orchestrator bypasses CLI utilities and passes the `issue_number` directly into the compiled LangGraph app state.
    *   *Citation (`assemblyzero/workflows/orchestrator/stages.py:154-159`):*
        ```python
                sub_result = app.invoke({
                    "issue_number": issue_number,
                    "workflow_type": "issue",
                    "target_repo": state.get("target_repo", ""),
                    "assemblyzero_root": state.get("assemblyzero_root", ""),
                })
        ```

*   **A (Chiron has NO src/ directory)**: **CONFIRMED** (but mitigated natively).
    *   *Rationale:* The implementation orchestrator explicitly creates missing parent directories via `exist_ok=True`.
    *   *Citation (`assemblyzero/workflows/testing/nodes/implementation/orchestrator.py:270`):*
        `                full_path.parent.mkdir(parents=True, exist_ok=True)`

*   **E (PR creation omits `--repo`)**: **CONFIRMED**.
    *   *Rationale:* The canonical documentation mandates the `--repo` flag to bypass an upstream `gh` bug, but the orchestrator does not use it.
    *   *Citation 1 (`assemblyzero/workflows/orchestrator/stages.py:439-447`):*
        ```python
                pr_result = run_command(
                    [
                        "gh", "pr", "create",
                        "--title", pr_title,
                        "--body", pr_body,
                        "--base", "main",
                        "--head", branch,
                    ],
        ```
    *   *Citation 2 (`docs/canonical/universal-CLAUDE.md:231`):*
        `gh pr create --repo {owner}/{repo} --head {branch-name} --base main --title "..." --body "..."`

### 5. Stage Walkthrough

1.  **triage / LLD-draft:**
    *   **Reads from:** `assemblyzero_root` templates, and inherently `.assemblyzero/vector_store` relative to `cwd` (AssemblyZero).
    *   **Writes to:** `target_repo / "docs/lld/active/"` directly.
    *   **Auth required:** Environment-provided LLM credentials (e.g. `GEMINI_API_KEY`).
    *   **Failure mode:** Complete hallucination of AssemblyZero components in Chiron's LLD (H2 Context Bleed).
2.  **LLD-review:**
    *   **Reads from:** Outputs of LLD-draft.
    *   **Auth required:** LLM credentials.
3.  **spec:**
    *   **Reads from:** `target_repo` LLD outputs.
    *   **Writes to:** `target_repo` spec directories.
4.  **impl:**
    *   **Reads from:** Spec outputs.
    *   **Writes to:** Git worktree created dynamically. `git -C {target_repo} worktree add str(worktree_path) -b branch_name`. Missing source and test directories (`src/`, `tests/unit/`) will be created natively.
    *   **Auth required:** LLM credentials for TDD loop.
5.  **PR:**
    *   **Reads from:** Worktree branch.
    *   **Writes to:** Remote GitHub API via `gh pr create`. Note: PR body correctly uses `Closes #{issue_number}\n\n` standalone line satisfying the `pr-sentinel` rules.
    *   **Auth required:** `gh auth status` must be green.
    *   **Failure mode:** `gh` CLI error `GraphQL: No commits between main and main` because the `--repo` flag is missing (Failure Point 3).

### 6. Recommended Pre-Flight Checks

Before the operator kicks off the orchestrator, they should run:

1.  **Verify DB isolation (H1 check):**
    `sqlite3 ~/.assemblyzero/requirements_workflow.db "SELECT thread_id FROM checkpoints WHERE thread_id LIKE '%4%';" || echo "Clean"`
    *(Expected output: empty or "Clean")*
2.  **Verify gh Auth:**
    `gh auth status`
    *(Expected output: Logged in to github.com account...)*
3.  **Verify LLM Credentials:**
    `printenv GEMINI_API_KEY`
    *(Expected output: The raw API key — ensure it is set)*
4.  **Verify Vector Store Isolation (H2 mitigation):**
    Ensure a temporary workaround is applied or run the pipeline inside a fresh shell overriding the vector store path to prevent AZ bleed.

### 7. Explicit Non-Claims
*   I did not run the command; my verdict is a prediction from static code-reading.
*   I did not exercise the LLM-grounded stages; their behavior at runtime may diverge from their static configuration.
*   I did not comprehensively trace the `thread_id` generation schema in the LangGraph sqlite memory checkpointer beyond its failure to isolate by `target_repo`.

### 8. Refuted / Hallucinated-Claim Appendix
*   **H3 (workspace_context.docs_dir writes):** REFUTED by `assemblyzero/workflows/requirements/audit.py:696` which reads `lld_dir = target_repo / LLD_ACTIVE_DIR`, proving active writes bypass the dead-code property.
*   **H5 (ideas/active assumption):** REFUTED by `assemblyzero/workflows/orchestrator/stages.py:154-159` which shows the `orchestrate` pipeline bypasses the `ideas/active` target entirely, passing `"issue_number": issue_number` straight to `.invoke()`.

### 8b. Corrections from rule-6 re-pass (2026-05-30, post-filing review)

A follow-up rule-6 re-pass (Claude reading the same citations cold, without Gemini's framing) found that three of the eight findings did not survive independent verification at the depth rule 6 requires. They are recorded here for the transparency-ledger reason AZ #1390's methodology makes mandatory: a CONFIRMED verdict that was wrong is the same shape of failure the methodology is designed to catch, regardless of which reviewer caught it first. Tracked as AZ #1421.

#### H1 (state-keyed-by-issue collision) — verdict REFINED

Gemini's verdict was **CONFIRMED**, with rationale "If AssemblyZero Issue #4 was ever orchestrated on this machine, Chiron Issue #4 will collide with it on the `thread_id` slug, causing LangGraph state corruption."

**The orchestrator does NOT attach a LangGraph checkpointer at any sub-graph compile site.** Verified at SHA `c8e31c2`:

```
assemblyzero/workflows/orchestrator/stages.py:128   app = graph.compile()    # no checkpointer
assemblyzero/workflows/orchestrator/stages.py:190   app = graph.compile()    # no checkpointer
assemblyzero/workflows/orchestrator/stages.py:262   app = graph.compile()    # no checkpointer
assemblyzero/workflows/orchestrator/stages.py:335   app = graph.compile()    # no checkpointer
```

Grep for `SqliteSaver|MemorySaver|checkpointer` in `assemblyzero/workflows/orchestrator/` returns zero matches. The SQLite DB Gemini cited (`~/.assemblyzero/requirements_workflow.db`) is used by the standalone workflow scripts in `tools/run_*_workflow.py`, NOT by the orchestrator path. The collision Gemini predicted at THAT layer cannot fire on the orchestrator path.

**However**, the collision risk Gemini named DOES exist at a different layer that Gemini did not cite. The orchestrator's own state-persistence module persists by issue_number to a CWD-relative directory (`assemblyzero/workflows/orchestrator/resume.py`):

```python
# line 21
STATE_DIR = Path(".assemblyzero/orchestrator/state")
# line 22
LOCK_DIR  = Path(".assemblyzero/orchestrator/locks")
# lines 33-34
issue_number = state["issue_number"]
state_path = STATE_DIR / f"{issue_number}.json"
```

If `poetry run python tools/orchestrate.py --issue 4 --repo Chiron` is run from AssemblyZero's CWD, the state file lands at `AssemblyZero/.assemblyzero/orchestrator/state/4.json`. A subsequent `poetry run python tools/orchestrate.py --issue 4` (no `--repo`, i.e. AZ #4) from the same CWD would overwrite that file (after `.bak` backup at `resume.py:37-39`). The collision is real; the citation Gemini gave for it was wrong; the mechanism is different from the one Gemini named.

For the **current Chiron #4 smoke build**, no such collision can fire: `ls AssemblyZero/.assemblyzero/orchestrator/state/` returns "No such file or directory" at SHA `c8e31c2`. Locks dir is also empty. Clean slate.

#### H2 (RAG vector-store context bleed) — verdict REFINED

Gemini's verdict was **CONFIRMED**, with rationale "vector store defaults to relative path ... will read AssemblyZero's vector store and ground Chiron's Issue #4 in AssemblyZero's source code, destroying the LLD output."

**The LLD stage does not call RAG at all.** Verified at `assemblyzero/workflows/requirements/nodes/analyze_codebase.py:1-235`. Node N0b (`analyze_codebase`) imports `assemblyzero.utils.codebase_reader` and `assemblyzero.utils.pattern_scanner` and reads `target_repo` directly. No `assemblyzero.rag.*` import.

The Spec stage DOES call `retrieve_codebase_context` (`assemblyzero/workflows/implementation_spec/nodes/coder_node.py:43-48`). However, that function does NOT use either `RAGConfig` class — it calls `_chromadb.PersistentClient()` with no path argument (`assemblyzero/rag/codebase_retrieval.py:317-319`):

```python
try:
    client = _chromadb.PersistentClient()
    collection = client.get_collection(name=collection_name)
```

ChromaDB's no-arg default is CWD-relative (distinct from the `Path(".assemblyzero/vector_store")` default both `RAGConfig` classes return). Verified empirically at SHA `c8e31c2`:

- `ls AssemblyZero/chroma_data` → "No such file or directory"
- `ls AssemblyZero/.assemblyzero/vector_store` → "No such file or directory"

With no collection ingested, `query_codebase_collection` at line 320-322 returns `[]`. The empty `CodebaseContext` falls through `coder_node.py:51` (`if context["formatted_text"]:` is falsy); the base prompt is used as-is. **No bleed in current state.**

The architectural condition Gemini named is real — if anyone runs an ingestion that creates a `codebase` collection in AZ's CWD before the smoke build, the Spec stage WOULD bleed AZ source into Chiron's spec — but it is unrealized at SHA `c8e31c2`. The headline "complete hallucination of AssemblyZero components in Chiron's LLD" failure mode in § 3 item 1 was overstated.

The three-default duplication that makes the bleed risk hard to neutralize via a single edit is tracked as AZ #1417 (expanded post-trace to cover the ChromaDB no-arg site at `codebase_retrieval.py:318`).

#### E (PR creation omits --repo) — verdict REFUTED

Gemini's verdict was **CONFIRMED**, with rationale "The canonical documentation mandates the `--repo` flag to bypass an upstream `gh` bug, but the orchestrator does not use it."

This conflated the canonical example with the canonical mandate. Re-reading `docs/canonical/universal-CLAUDE.md` at SHA `c8e31c2`:

**Mandate text** (line 228):

> "**Workaround:** always pass explicit `--head` and `--base` when scripting PR creation"

The mandate names two flags: `--head` and `--base`. The upstream bug-trigger condition the canonical text describes is when gh cannot infer head/base, NOT when it cannot infer the repo.

**Example text** (lines 230-232):

```bash
gh pr create --repo {owner}/{repo} --head {branch-name} --base main --title "..." --body "..."
```

`--repo` appears in the example but is not part of the mandate.

**Code** at `assemblyzero/workflows/orchestrator/stages.py:434-441` (verbatim):

```python
"gh", "pr", "create",
"--title", pr_title,
"--body", pr_body,
"--base", "main",
"--head", branch,
```

Both mandated flags (`--base`, `--head`) are present. The code follows the canonical workaround.

Further: the "cwd auto-detection is unreliable" framing was also overstated. The PR call runs with `cwd=worktree_path` (line 445), and the worktree is carved from the target via `git -C target_repo worktree add ...` (lines 320-322). The worktree's `.git` file points at the target's gitdir; gh resolves `origin` unambiguously to the target's remote.

The AZ issue filed from this finding (AZ #1419) was closed `not planned` with the same explanation.

---

**Meta-lesson surfaced for this report (rule 7):** rule-4 verbatim-snippet verification is necessary but not sufficient for rule-6 independent verification. A reviewer can confirm a quoted snippet is present (rule 4) without confirming that the surrounding prose, definitional context, or scope-of-mandate matches the framing the snippet was used to support (rule 6). The seven rules must be read together, not à la carte. Two of the three corrections above (H1, E) survived rule-4 verification cleanly and only failed under stricter rule-6 reading; H2 (LLD-bleed) survived rule-4 but the LLD code path Gemini's rationale implied was never actually verified to call RAG.