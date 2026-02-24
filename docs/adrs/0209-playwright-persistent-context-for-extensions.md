# ADR 0209: Playwright Persistent Context for Extension E2E Testing

**Status:** Implemented
**Date:** 2026-02-24
**Categories:** Process, Infrastructure

## 1. Context

Chrome MV3 extensions register a service worker and expose APIs (like `chrome.storage.session`) only in extension contexts (popup, service worker, content scripts). Playwright's standard test runner creates a `BrowserContext` via `browser.newContext()`, which loads extensions through `launchOptions.args` but does **not** expose:

1. Extension service workers via `context.serviceWorkers()`
2. Navigation to `chrome-extension://` URLs (fails with `net::ERR_BLOCKED_BY_CLIENT`)

This was discovered during Issue #403 (E2E Auth Flow Verification) when tests needed to:
- Read/write `chrome.storage.session` (JWT storage)
- Call `getAuthHeaders()` defined in the service worker
- Navigate to the popup page to call `mockLogin()`

The standard Playwright config (used by all other Aletheia E2E tests) works fine for testing extension behavior on web pages (overlay injection, age gate, XSS protection) but cannot test **extension-internal** APIs.

## 2. Decision

**We will use `chromium.launchPersistentContext()` with a custom test fixture for E2E tests that need service worker or popup page access.**

Tests that only interact with extension behavior on web pages (overlay, content scripts) continue using the standard Playwright config. Only tests requiring extension-internal access use the persistent context fixture.

## 3. Alternatives Considered

### Option A: Custom fixture with `launchPersistentContext` — SELECTED
**Description:** Create a test-local fixture that launches a persistent browser context with the extension loaded, providing access to service workers and extension pages.

```javascript
const test = base.extend({
    context: async ({}, use) => {
        const context = await chromium.launchPersistentContext('', {
            headless: false,
            args: [
                `--disable-extensions-except=${extensionPath}`,
                `--load-extension=${extensionPath}`,
                '--no-sandbox'
            ]
        });
        await use(context);
        await context.close();
    },
    extensionId: async ({ context }, use) => {
        let sw = context.serviceWorkers()[0];
        if (!sw)
            sw = await context.waitForEvent('serviceworker', { timeout: 10000 });
        const id = sw.url().split('/')[2];
        await use(id);
    },
    serviceWorker: async ({ context, extensionId }, use) => {
        const sw = context.serviceWorkers().find(w =>
            w.url().includes(extensionId)
        );
        await use(sw);
    }
});
```

**Pros:**
- Full access to service workers, popup pages, and all extension APIs
- Clean fixture pattern — isolated to tests that need it
- Follows Playwright's official extension testing recommendation
- No changes to existing test infrastructure

**Cons:**
- Each test file with this fixture manages its own browser lifecycle
- Persistent context uses an empty temp profile (no state carryover between test files)
- Slightly different setup than other E2E tests (two patterns in one project)

### Option B: Migrate all E2E tests to `launchPersistentContext` — Rejected
**Description:** Replace the standard Playwright config with persistent context for all tests.

**Pros:**
- Single pattern across all tests

**Cons:**
- Requires rewriting all 8 existing spec files
- Persistent context behaves differently (user data dir, profile isolation)
- Existing tests work fine with the standard config ← unnecessary churn

### Option C: Skip extension-internal testing — Rejected
**Description:** Only test extension behavior visible on web pages. Skip service worker and popup tests.

**Pros:**
- No infrastructure changes

**Cons:**
- Cannot test JWT storage, auth headers, or mockLogin
- The exact gap that caused the AUTH_ENABLED=true outage ← defeats the purpose

## 4. Rationale

Option A was selected because it adds the needed capability without disrupting existing tests. The persistent context fixture is self-contained in the test file that needs it. The two-pattern approach is documented (this ADR) and each pattern has a clear use case:

| Pattern | Use Case |
|---------|----------|
| Standard config (`playwright.config.js`) | Extension behavior on web pages |
| Persistent context (custom fixture) | Extension-internal APIs (service worker, popup, storage) |

## 5. Security Risk Analysis

| Risk | Impact | Likelihood | Severity | Mitigation |
|------|--------|------------|----------|------------|
| Temp profile may leak state between test runs | Low | Low | 1 | Empty string `''` user data dir creates fresh temp dir each run |
| Service worker `evaluate()` runs arbitrary code | Low | Low | 1 | Test-only code, not in production path |

**Residual Risk:** Minimal. This affects only test infrastructure.

## 6. Consequences

### Positive
- Can now test the full auth chain: storage → headers → network
- Caught the `mockLogin()` JWT bug that caused the AUTH_ENABLED outage
- Reusable pattern for any future extension-internal E2E tests
- Service worker access enables testing `getAuthHeaders()`, message handlers, etc.

### Negative
- Two Playwright patterns in one project (documented, acceptable)
- Persistent context tests cannot use `page` fixture from config — must create pages manually

### Neutral
- Existing tests unchanged; new pattern is additive

## 7. Implementation

- **Related Issues:** #403 (E2E Auth Flow Verification), #402 (JWT storage fix)
- **Related LLDs:** N/A (test infrastructure, no LLD required)
- **Status:** Complete
- **Source:** `tests/e2e/auth-flow.spec.js`

## 8. References

- [Playwright Chrome Extension Testing Guide](https://playwright.dev/docs/chrome-extensions)
- [Playwright BrowserContext.serviceWorkers()](https://playwright.dev/docs/api/class-browsercontext#browser-context-service-workers)
- Aletheia `tests/e2e/accessibility.spec.js:148` — documents the `ERR_BLOCKED_BY_CLIENT` limitation

---

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-02-24 | Claude Opus 4.6 | Initial draft |
