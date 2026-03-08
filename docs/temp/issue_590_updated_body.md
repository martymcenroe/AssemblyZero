## Objective
Align Claude's babysitting and autonomous work instructions with the new "Perdita" standards established in AssemblyZero.

## Scope
Update `CLAUDE.md` to reflect the transition from manual babysitting to mechanical, evidence-based safety gates and strict permission boundaries.

## Key Changes
1. **From Manual to Mechanical:** Move away from instructions requiring human monitoring toward instructions for using the File Size Safety Gate and Two-Strike Rule.
2. **Two-Strike Rule:** Instruct Claude to adopt a maximum of 2 retries per file before halting.
3. **Context Management:** Mandate context pruning for retries (exclude previously successful files) to manage the $200/month Pro Max token budget.
4. **Command Prohibitions (New Scope):** Explicitly forbid the use of dangerous flags that bypass safety gates:
    - `gh pr merge --admin`
    - `git push --force`
    - `git branch -D` (must use `-d`)
    - `git reset --hard`
5. **Halt-and-Plan:** Formalize that "Hitting a wall" means saving state and stopping, not "trying one more time."

## Acceptance Criteria
- [ ] `CLAUDE.md` updated with "Perdita Protocol" alignment.
- [ ] Explicit prohibitions added for `--admin`, `--force`, and `-D`.
- [ ] Two-strike rule replaces the previous three-strike default.

## Related
- #171 (Final Gate)
- #588 (Systemic Guard)
- #589 (Gemini Instructions)
- #595 (Restricted Auth)