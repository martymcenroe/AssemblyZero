# 0850 — Dashboard Interactive Element Audit

**Type:** Reusable audit procedure
**Scope:** Any project with a web dashboard (React, Vue, vanilla JS)
**Purpose:** Systematically discover, catalog, and cross-reference every interactive UI element against test coverage

---

## When to Run This Audit

- Before a major test-writing sprint
- After adding a new dashboard page or admin section
- When test coverage feels "good enough" but hasn't been verified
- Quarterly, as part of code health reviews

---

## Step 1: Define Scope

Before starting, identify:

| Item | Example |
|------|---------|
| Dashboard root directory | `dashboard/src/` or `src/dashboard/` |
| Component directories | `components/`, `pages/`, `components/admin/`, `components/shared/` |
| Test directories | `src/**/*.test.tsx`, `tests/e2e/**/*.spec.ts` |
| Shared/reusable components | `ConfirmDialog`, `LabelChips`, `Toast`, etc. |

---

## Step 2: Discovery — Find All Interactive Elements

### 2a. Pattern Search

Search the component directories for interactive element indicators:

```
onClick, onSubmit, onChange, onKeyDown, onBlur, onFocus
useMutation, mutate, mutateAsync
<Button, <Input, <Select, <Checkbox, <Textarea, <Switch
<a href=, <Link to=
navigate(, router.push(
```

### 2b. Element Classification

For each discovered element, record:

| Field | Description |
|-------|-------------|
| **ID** | Component prefix + sequential number (e.g., `CD-01`) |
| **Element** | HTML/component type + visible label |
| **Handler** | Function or mutation invoked on interaction |
| **Disabled condition** | When the element cannot be interacted with |
| **Visibility condition** | When the element is/isn't rendered |
| **Conditional behavior** | Dynamic labels, colors, states, etc. |
| **Test file:test name** | Specific test covering this element, or `UNTESTED` |

### 2c. What Counts as Interactive

**Include:**
- Buttons (submit, action, toggle)
- Form inputs (text, number, file, textarea)
- Selects/dropdowns
- Checkboxes and switches
- Clickable table rows
- Clickable badges/chips
- Links with navigation handlers
- Accordion/collapsible triggers
- Sortable column headers

**Exclude:**
- Display-only badges (no handler)
- Static text/labels
- Tooltip triggers (unless they contain actions)
- Loading spinners
- Status indicators

---

## Step 3: Component-by-Component Catalog

For each page/component, create a section with:

1. **File path** and line count
2. **Existing test files** that reference this component
3. **Table of all interactive elements** (using format from Step 2b)
4. **Mutation count** (for components with `useMutation`)
5. **Inline sub-component count** (functions defined inside the main component)

### ID Prefix Convention

| Prefix | Component |
|--------|-----------|
| LP | LoginPage |
| NT | NavTabs |
| CL | ConversationsPage (list) |
| CD | ConversationDetail |
| AP | AdminPage |
| AQ | AttentionQueueSection |
| AU | AuditQueueSection |
| BA | BulkActionsSection |
| SG | StargazersSection |
| SS | SettingsSection |
| VT | ViewerTokensSection |
| KP | KnowledgePage |
| OP | ObservabilityPage |
| SC | Shared Components |

Adapt prefixes to the target project's component names.

---

## Step 4: Cross-Reference Against Tests

For each cataloged element, search:

1. **Unit tests** (`*.test.tsx`, `*.test.ts`) — component-level renders and interactions
2. **E2E tests** (`*.spec.ts`) — full browser automation
3. **API client tests** — verify the underlying API call exists
4. **Integration tests** — if any

### Coverage Quality Levels

| Level | Description | Example |
|-------|-------------|---------|
| **Behavioral** | Test clicks/types the element AND verifies the outcome | "clicking Delete removes conversation from list" |
| **Visibility** | Test confirms the element renders in correct conditions | "delete button is visible for owner" |
| **None** | No test references this element | UNTESTED |

Mark each element with its coverage level. Visibility-only coverage is better than nothing but should be upgraded.

---

## Step 5: Generate the Issue

Create a GitHub issue with:

**Title:** `test: ~{N} untested dashboard interactive elements need component tests`

**Body structure:**

```markdown
## Context

Dashboard interactive element audit identified {N} elements with no test coverage
across {M} components. See `docs/standards/NNNNN-dashboard-button-spec.md` for
the full specification.

## Untested Elements by Component

### ComponentName ({count} elements)
- `ID-01` Description of element
- `ID-02` Description of element
...

### NextComponent ({count} elements)
...

## Coverage Quality Gaps

Elements with visibility-only coverage (no behavioral assertions):
- `ID-XX` Description — has E2E visibility test but no click/interaction test
...

## Acceptance Criteria

- [ ] Every UNTESTED element has at least one behavioral test
- [ ] Every visibility-only element is upgraded to behavioral
- [ ] Tests use component-level testing (not just E2E) where practical
- [ ] No mocking to pass — real behavior or skip
```

---

## Step 6: Refactor Assessment

Flag components that need structural work before testing is practical:

### God Component Criteria

A component is a "god component" if it has:
- **>500 lines** of source code
- **>5 useMutation hooks** in one file
- **>3 inline sub-components** (functions defined inside the main component)
- **Mixed concerns** (e.g., action bar + form + message history in one file)

### What to Document

For each god component:
1. Current line count
2. Number of mutations
3. Number of inline sub-components
4. Proposed extraction plan (new files + shared hooks)
5. Estimated line count after extraction

Include the refactor plan as an appendix to the spec document, not as part of the test gap issue. Refactoring and testing are separate efforts.

---

## Output Checklist

| Deliverable | Location | Description |
|-------------|----------|-------------|
| Spec document | `docs/standards/` in target repo | Full catalog of every interactive element |
| GitHub issue | Target repo issues | List of untested elements with acceptance criteria |
| Refactor appendix | Appended to spec document | God component extraction plan (if applicable) |

---

## Tips

- **Count carefully.** Off-by-one errors in element counts erode trust in the audit.
- **Verify against code.** Don't catalog from memory — read every component file.
- **Distinguish visibility from behavior.** "Button renders" is not "button works."
- **Don't prioritize.** If it's untested, it's a gap. Priority comes when writing the tests, not during the audit.
- **Run the audit from a clean main branch.** In-progress feature branches may have elements that don't exist yet.
