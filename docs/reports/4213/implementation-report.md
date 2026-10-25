# Implementation Report: #4213

`CLAUDE.md` carried two sections that the root CLAUDE.md already holds, and every session that loads the AssemblyZero layer reads both files at onboard.

- `## Standing Orders` is removed. Its three paragraphs are in the root CLAUDE.md's "Standing Orders" section word for word; the only differences are a colon where the root has a dash before the list of onboarding texts, and the root's added note on where the rule was earned.
- `## Cascade Prevention` is one rule line: close with an open-ended question, never offer numbered or yes/no options or suggest the next issue, except while a standing order is live. It names the root CLAUDE.md's "Communication", "Hard Rules" and "Standing Orders" sections as the full rule. Its old pointer to "Standing Orders immediately below" went with the removed section. The heading, the open-ended wording and the ban on numbered options stay, because `tests/integration/test_cascade_hook_integration.py` (T260 to T280) reads them here, and the standing-order exception stays beside the rule so the file states no halt without its exception.
- Running Workflows, Common Gotchas, Key Files, Merging PRs and Banned Practices are unchanged.
- `.agents/rules/repo-claude-md.md` is regenerated from the new `CLAUDE.md` with the fleet's agy rules generator (`--apply`), so agy loads the same text.

Size of `CLAUDE.md`: 5,085 bytes before, 3,546 after, 1,539 bytes removed.

Authorization: the operator ruled "trim" on this change on 2026-10-24 at 11:17 PM Central; the issue records the ruling and its scope.
