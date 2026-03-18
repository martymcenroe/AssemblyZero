# Lessons Learned — AssemblyZero

| Date | Lesson | Rule/Action |
|:-----|:-------|:------------|
| 2026-03-18 | **101 plan files and 4,688 todo files discovered in ~/.claude/.** These accumulated over weeks of sessions. If any are auto-loaded into context, they're a massive token sink that would explain the accelerating compaction. | **Audit and purge stale plans/todos periodically.** Add to cleanup protocol. Investigate whether Claude Code loads all plans/todos or only the active one. |
| 2026-03-18 | **Jumped to implementation across 5+ files after design Q&A without presenting a plan.** User asked "do you have any more questions?" and agent interpreted this as authorization to implement. User had explicitly said "at least two changes to every workflow /plan" -- the word "plan" was in their message. 3 issues created, branch started, partial code written before user intervened. | **After a design Q&A session, ALWAYS present a structured plan before writing code.** "Do you have any more questions?" is a checkpoint, not a green light. Wait for explicit "do it" / "implement" / plan approval. Saved as feedback_plan_before_implement.md. |
