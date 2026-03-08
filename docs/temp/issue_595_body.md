## Objective
Establish a secure, restricted authentication model for AI agents (Gemini, Claude, etc.) that enforces repository gates while ensuring all contributions are attributed to the repository owner (Marty McEnroe).

## Problem
Currently, agents are authenticated via the owner's full-access GitHub account. This allows agents to bypass mandatory safety gates using flags like `--admin` or `--force`. Conversely, using a separate agent account would strip the owner of their contribution credit ("green squares"), which is unacceptable for career positioning.

## Proposed Solution: The Service Account Pattern
1. **Attribution (Git Identity):** Agents MUST keep `git config user.email` set to the owner's email. This ensures authorship credit remains with Marty.
2. **Authorization (API Identity):** Replace full-owner tokens with Fine-Grained Personal Access Tokens (PATs) for agent CLI tools (`gh` CLI, Claude Code).
3. **Restricted Scopes:**
    - **Allow:** Read/Write access to code, PRs, and Issues.
    - **Deny:** Admin, Maintainer, and Branch Protection bypass permissions.

## Key Restrictions (Permissible Command Schema)
The system should eventually programmatically (or via strict protocol) prohibit:
- `gh pr merge --admin`
- `git push --force`
- `git branch -D` (use `-d` only)
- `git reset --hard` (already in standards)

## Acceptance Criteria
- [ ] Documentation for creating restricted PATs for Gemini and Claude.
- [ ] Verification that Marty's attribution is preserved on agent commits.
- [ ] Verification that `--admin` fails when using the restricted token.
- [ ] Update to `docs/standards/0003-agent-prohibited-actions.md` with these specific flags.

## Related
- #589 (Perdita Protocol)
- #171 (Mandatory Gates)