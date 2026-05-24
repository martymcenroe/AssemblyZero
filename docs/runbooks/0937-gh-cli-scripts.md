# Runbook 0937 — gh CLI Scripts

**Purpose:** document the Python tools that back the operator's `gh` CLI aliases — what they do, what data sources they pull from, and the math discipline required to keep their output matching what GitHub actually displays. Companion to [`0936-gh-cli-aliases.md`](0936-gh-cli-aliases.md), which covers the alias mechanism itself.

## The pattern

Each `gh` CLI alias points at a Python tool in `automation-scripts/tools/`:

```bash
gh alias set <name> '!cd ~/Projects/automation-scripts && poetry run python tools/<file>.py'
```

The tool is stdlib + the `gh` CLI only — no third-party deps. Tools shell out to `gh api` or `gh api graphql` for data, then format for terminal reading. See 0936 for the alias-mechanism details.

## Inventory

| Tool | Invoked as | What it reports |
|---|---|---|
| `tools/gh_daily_contributions.py` | `gh gh-count` | Today's contribution breakdown (commits, issues, PRs, reviews, repos) |
| `tools/gh_review_projection.py` | `gh reviews` | All-time review count, 12-month state, current pace, projection to 1% graph spoke |

When adding a new sibling tool: update this table, update the alias inventory in 0936, then `gh alias set <name> '!...'`.

## Data sources

| Source | What it returns | Used for |
|---|---|---|
| `gh api graphql` → `contributionsCollection` | Per-category counts (commits/issues/PRs/reviews/repos), restricted count, calendar total — over an arbitrary window | Activity-overview style breakdowns |
| `gh api search/issues?q=reviewed-by:USER+type:pr` | Unique PRs reviewed all-time (no time bound) | All-time stats |
| `gh api user -q .login` | The authenticated username | Auto-determining who the report is for |
| Rendered HTML fragment at `/USER?action=show&controller=profiles&tab=contributions` (header: `X-Requested-With: XMLHttpRequest`) | The widget's actual displayed percentages via `data-percentages` attribute | Cross-checking computed values vs what GitHub shows |

The HTML fragment is authoritative for "what the operator actually sees." Use it as a verification gate, not a primary data source.

## The math

### Denominator selection (the trap)

The activity-overview widget normalizes contribution percentages across four spokes (commits, issues, pull requests, code review). **The denominator includes private contributions**. A naive sum of the four public spoke fields understates the denominator and overstates every percentage.

Concrete failure mode (automation-scripts#51, fixed 2026-05-24):

| Source | Code-review numerator | Denominator | Fraction | Rounds to |
|---|---|---|---|---|
| Naive (public spokes only) | 26 | 5,109 (commits + issues + PRs + reviews, public) | 0.51% | 1% |
| Correct (widget's actual) | 26 | 9,556 (public + 4,447 restricted) | 0.27% | 0% |

The widget displayed 0%. The naive tool reported 0.51% and claimed "already at threshold." Wrong number, wrong conclusion.

**Rule:** for any computation comparing against a graph percentage, the denominator is `contributionCalendar.totalContributions` (a single field on the GraphQL `contributionsCollection`), NOT a sum of the per-category public fields.

### Public + private accounting

GraphQL `contributionsCollection` returns `restrictedContributionsCount` as a single number — the count of private contributions NOT broken out by type. When the breakdown matters (rarely), back-solve from the widget's displayed percentages using the public spoke counts as the known floor:

```
implied_total_for_spoke = (widget_pct / 100) × widget_denominator
implied_private_for_spoke = implied_total_for_spoke - public_spoke_count
```

The implied private counts should sum to approximately `restrictedContributionsCount`; verify within ~1% as a sanity check. (Calendar-boundary timezone effects and small categories like repositories can produce off-by-N drift.)

### Rounding

The widget integer-rounds and **preserves sum-to-100**. Observable in the rendered HTML:

```html
<div class="js-activity-overview-graph-container"
     data-percentages='{"Commits":43,"Issues":35,"Pull requests":22,"Code review":0}'>
```

`43 + 35 + 22 + 0 = 100`. The behavior is consistent with largest-remainder method (Hamilton/Hare): floor each percentage, distribute the remaining points (100 − sum_of_floors) to entries with the largest fractional parts. GitHub's implementation is closed-source; this matches every observed case.

When a tool reports "% of total" for a single spoke, it should use simple half-up rounding via Python's `round()`. The widget's largest-remainder distribution can move ±1 from naive rounding when fractional parts are close to 0.5 across multiple spokes — accept that as the noise floor. Cross-check against the widget's `data-percentages` if exactness matters.

### Threshold projection

For projecting "when does spoke X tip from N% to (N+1)%":

The threshold is the rounding boundary, `(N + 0.5) / 100`. For 0%→1%: 0.005.

Solve for the smallest `d` such that:

```
(R + r·d) / (T + t·d) ≥ threshold
```

Where:
- `R` = current numerator for spoke X (e.g., review count over the window)
- `T` = current denominator (widget total)
- `r` = recent daily rate of spoke X (typically last-30-day average)
- `t` = recent daily rate of total contributions

Closed form:
```
d ≥ (threshold·T − R) / (r − threshold·t)
```

If the right side is ≤ 0, the spoke is already at or above threshold. If the denominator (`r − threshold·t`) is ≤ 0, the recent rate is moving the fraction in the wrong direction; the spoke will never tip at this pace.

**Caveat — sliding window.** The 12-month denominator is not strictly additive. As the window slides forward, the OLDEST day's contributions drop off. The closed-form above treats `T` as additive (`T + t·d`), which is optimistic when the trailing year was as busy as the recent 30 days. Real falloff math requires per-day contribution history; rarely worth the complexity for a back-of-envelope projection.

Report both the optimistic days-to-threshold and the steady-state fraction (`r / t`) so the operator can see whether the current pace is even moving in the right direction. If steady-state is below threshold, the optimistic count is meaningless — say so.

## Verification recipe

Every metric-reporting `gh` CLI script that touches the activity-overview widget should cross-check its output against the live widget:

1. Fetch the rendered HTML fragment (URL pattern above; the `X-Requested-With: XMLHttpRequest` header is what makes GitHub return the include-fragment content rather than the host page)
2. Grep the response for `data-percentages="..."`
3. HTML-decode (`&quot;` → `"`) and JSON-parse the value
4. Compare to the tool's computed percentage; flag drift

Reference implementation: `fetch_widget_percentages()` in `automation-scripts/tools/gh_review_projection.py`. Best-effort — never fatal. A failed cross-check is informational, not a script abort.

This recipe catches:
- Denominator bugs (the failure mode that produced automation-scripts#51)
- Future GitHub-side widget changes (e.g., if rounding rule changes or new spokes are added)
- Auth/scope mismatches (the tool sees different totals than the unauthenticated widget request)

## Adding a new gh CLI script

1. Write the Python tool in `automation-scripts/tools/<name>.py`. Stdlib + `gh` CLI only. Use existing tools as templates.
2. If the tool reports any percentage tied to a GitHub UI element, include the verification recipe.
3. Set the alias: `gh alias set <invocation> '!cd ~/Projects/automation-scripts && poetry run python tools/<name>.py'`
4. Verify: `gh alias list | grep <invocation>` and run the alias end-to-end.
5. Update the inventory tables in both 0936 and this runbook.
6. Commit + PR in `automation-scripts` (gates: the repo's own pr-sentinel + auto-reviewer).

## References

- [`0936-gh-cli-aliases.md`](0936-gh-cli-aliases.md) — alias mechanism, inventory, dotfiles divergence trap
- AZ#1247 — work that produced this runbook
- AZ#1244 — parent (gh reviews + projection tool ship)
- `automation-scripts#49` — original tool ship
- `automation-scripts#51` — denominator-fix issue + analysis
- `automation-scripts/tools/gh_review_projection.py` — reference implementation of the math + verification recipe
- `automation-scripts/tools/gh_daily_contributions.py` — sibling tool, simpler shape
