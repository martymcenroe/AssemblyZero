# 0216 - ADR: System Chrome Channel for Playwright Automation Against Anti-Automation-Gated Sites

**Status:** Implemented
**Date:** 2026-04-22
**Categories:** Infrastructure, Process

> **Mirror ADR.** This decision originated in Clio — see Clio `docs/adrs/0201-playwright-system-chrome-channel.md`. Mirrored here so AssemblyZero-orchestrated Playwright work has a canonical AZ-side reference alongside ADR-0209 (persistent context for extension-internal testing).

## 1. Context

Clio's DOM-discovery harness (`Clio/tests/e2e/dom-discovery.spec.js`, Clio issue #47) drives Playwright to Gemini, Claude, and ChatGPT to capture sidebar DOM structure for sidebar-harvesting work. On first live run, signing into `gemini.google.com` with Playwright's bundled Chromium failed at the Google sign-in page BEFORE any credentials could be entered:

> Couldn't sign you in. This browser or app may not be secure.
> Try using a different browser.

The block is deterministic. Retrying, clearing cookies, or waiting does not resolve it. The cause is browser fingerprinting. Google's sign-in path rejects clients whose signature matches known automation stacks. Playwright's default configuration presents at least three such signals:

1. **Bundled Chromium has a slightly different binary + TLS fingerprint** than user-installed Chrome (different build flags, revision cadence, TLS cipher order)
2. **Playwright injects `navigator.webdriver = true`** at runtime
3. **The bundled Chromium channel presents a fresh, history-less profile**

### Why this matters beyond Clio

The same block applies to any AssemblyZero-orchestrated Playwright work that touches anti-automation-gated sites:

- **Google properties** — Gemini (Clio), Google Workspace APIs accessed via browser, Google Meet / Drive automation
- **Microsoft / Azure AD sign-in** — if any future AZ agent needs to drive enterprise SSO
- **SaaS with bot detection** — Cloudflare-guarded sites, Okta, Duo, enterprise billing portals
- **Unleashed subagent work** — any agent spawned through AssemblyZero that orchestrates Playwright against these surfaces

Clio hit it first but won't be the last consumer.

### Complementary scope

This ADR is distinct from ADR-0209 (Playwright Persistent Context for Extension E2E Testing). The two solve different problems:

| ADR | Problem | Technique |
|-----|---------|-----------|
| ADR-0209 | Playwright can't access Chrome extension service workers / `chrome-extension://` URLs | `chromium.launchPersistentContext()` with the extension loaded |
| ADR-0216 (this) | Google blocks bundled Chromium at sign-in based on fingerprint | `channel: 'chrome'` + disable-blink-features flag |

Escalation from ADR-0216 would move to a persistent-context pattern similar to ADR-0209 but with a pre-authenticated Chrome profile dir. The two ADRs would then converge in technique if the user chooses to escalate.

## 2. Decision

**AssemblyZero-aligned projects using Playwright against anti-automation-gated sites will launch with the system Chrome channel and disable Blink's automation-controlled feature, scoped per-spec (not globally).**

Concretely, the affected spec adds at file top:

```js
test.use({
  channel: 'chrome',
  launchOptions: {
    args: ['--disable-blink-features=AutomationControlled']
  }
});
```

Per-spec scoping keeps other tests on bundled Chromium (faster, no external Chrome dependency).

## 3. Alternatives Considered

### Option A: `channel: 'chrome'` + `--disable-blink-features=AutomationControlled` — SELECTED

**Description:** Launch the user's installed Chrome instead of bundled Chromium; strip `navigator.webdriver`.

**Pros:**
- Uses existing Chrome install — matches real-user fingerprint end-to-end
- Minimal Playwright API surface — one `test.use()` block per spec
- Canonical, well-documented workaround across Playwright / Puppeteer / Selenium ecosystems
- Per-spec scope keeps unrelated tests fast and dependency-free

**Cons:**
- Requires system Chrome (negligible for devs working on Chrome extensions; real consideration for CI)
- CI/CD images must include Chrome to run affected specs
- Google could theoretically tighten further; escalation path exists (Option B)

### Option B: Persistent user-data-dir with pre-logged-in profile — Not Selected (reserved as escalation)

**Description:** `chromium.launchPersistentContext(userDataDir, {...})` pointing at a dir where the user pre-authenticated; sign-in state persists.

**Pros:**
- Strongest dodge — looks like a returning user, not a fresh sign-in attempt
- Bypasses sign-in blocks AND 2FA prompts on subsequent runs

**Cons:**
- Profile management complexity — first-run is still manual, profile rot possible
- Stored session tokens are a minor secrets-hygiene concern (in user home, not repo)
- Blurs the scope of ADR-0209 if mixed — better to keep each ADR single-purpose
- Not needed yet — Option A is sufficient for the current Clio harness

Reserved. If Google tightens and Option A stops working, file a superseding ADR and move affected specs here.

### Option C: User-agent spoofing alone — Rejected

**Description:** `setExtraHTTPHeaders({ 'User-Agent': '<real Chrome UA>' })` on bundled Chromium.

**Cons:**
- Google checks TLS fingerprint and JS-accessible properties (`navigator.webdriver`, plugins, canvas) — UA alone insufficient ← deciding factor
- HTTP/JS inconsistency is itself a detection signal

### Option D: Firefox — Rejected

**Description:** Route affected specs to Firefox via `browserName: 'firefox'`.

**Cons:**
- Google is MORE aggressive against non-Chrome UAs on Google properties
- Moves the fingerprint problem instead of solving it

### Option E: Manual-only testing — Rejected

**Description:** Abandon automation; do DOM discovery / sign-in flows by hand.

**Cons:**
- Defeats the entire point of a harness
- Clio specifically captures the pain of manual DevTools iteration in its `feedback_verify_dom_extraction.md` memory — 4 accounts × ~10 retries = the exhaustion this decision exists to eliminate

## 4. Rationale

Option A is the minimum-complexity working solution. System Chrome's fingerprint matches a normal user; `--disable-blink-features=AutomationControlled` is a single extra `args` entry. The whole change is one `test.use` block per affected spec plus a runbook prerequisite note.

Key deciding factors:

- **Proven** — the flag is documented across the automation testing ecosystem for years
- **Small blast radius** — scoped per-spec, no global config change
- **Escalation preserved** — Option B is available without retracting this ADR
- **Cross-project reusable** — same pattern applies regardless of which repo owns the spec

Trade-offs accepted:

- CI/CD runners that execute these specs must have Chrome (docker image addition)
- Chrome auto-update could silently change fingerprint — low likelihood, loud failure mode when it happens

## 5. Security Risk Analysis

| Risk | Impact | Likelihood | Severity | Mitigation |
|------|--------|------------|----------|------------|
| `channel: 'chrome'` uses the user's real Chrome profile (cookie / auth leak) | Medium | Low | 2 | Playwright's `test.use({ channel: 'chrome' })` creates a fresh temp user-data-dir, NOT the user's real profile. Verified in Playwright docs. Cannot read real Chrome cookies. |
| `--disable-blink-features=AutomationControlled` weakens browser sandbox / same-origin | Low | Low | 1 | The flag only affects the `navigator.webdriver` signal and related detection hints. Sandboxing, same-origin policy, TLS, extension permissions — unchanged. |
| Chrome auto-update silently breaks automation | Low | Low | 1 | Chrome updates rarely change fingerprint. Failures are loud (sign-in block) not silent (wrong data). |
| Normalizes "dodge anti-automation" as project-wide default | Low | Low | 1 | Scoped per-spec to legitimate reconnaissance on the user's own accounts. Not for third-party scraping. Documented here. |

**Residual Risk:** Minimal. Affects test infrastructure, not production code paths or user data.

## 6. Consequences

### Positive
- Clio's DOM-discovery harness (and any future AZ-orchestrated Playwright work against gated sites) can actually sign in
- Pattern is repo-agnostic — same `test.use` block applies in Clio, Aletheia, AZ internals, future projects
- No production code or user-facing behavior change
- System Chrome is what users actually run — extension-stack tests align with the real browser

### Negative
- System Chrome becomes a prerequisite for affected specs (runbook-noted in each consuming repo)
- CI/CD adoption requires adding Chrome to the runner image
- Per-repo runbooks now need a "system Chrome required for these specs" prerequisite

### Neutral
- Existing E2E tests unchanged — scoping limits the change to opt-in specs

## 7. Implementation

- **Origin:** Clio ADR-0201 — shipped in `martymcenroe/Clio` PR #76 (harness fix) and documented in PR #78 (ADR)
- **Status:** Pattern in active use on Clio's `tests/e2e/dom-discovery.spec.js`. No AZ-native consumers yet; this ADR stands as canonical reference for when one appears.
- **Pattern for new AZ-aligned specs:**
  ```js
  // At spec file top, alongside test.use({ headless: false, ... })
  test.use({
    channel: 'chrome',
    launchOptions: {
      args: ['--disable-blink-features=AutomationControlled']
    }
  });
  ```
- **When to apply:** any Playwright spec that must sign into Google, Microsoft, or comparable anti-automation-gated provider. Do NOT apply to specs that don't need it — bundled Chromium stays faster and dependency-free.
- **Per-repo runbook addendum:** each consuming repo should add a "System Chrome required" note in its development runbook alongside other Playwright prerequisites.
- **Escalation:** if Google (or a comparable provider) tightens further and this pattern stops working, move affected specs to Option B — persistent user-data-dir with pre-authenticated profile — and file a superseding ADR.

## 8. References

- **Clio ADR-0201** (`Clio/docs/adrs/0201-playwright-system-chrome-channel.md`) — origin decision with Clio-specific context
- **AssemblyZero ADR-0209** (`0209-playwright-persistent-context-for-extensions.md`) — complementary scope (extension-internal testing, different technique, converges in Option B escalation)
- [Playwright docs — Browser channels](https://playwright.dev/docs/browsers#google-chrome--microsoft-edge)
- [Playwright docs — launchPersistentContext](https://playwright.dev/docs/api/class-browsertype#browser-type-launch-persistent-context) — for Option B escalation path
- [Chromium `runtime_enabled_features.json5`](https://source.chromium.org/chromium/chromium/src/+/main:third_party/blink/renderer/platform/runtime_enabled_features.json5) — authoritative list of Blink feature flags

---

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-04-22 | Claude Opus 4.7 (1M context) | Initial mirror of Clio ADR-0201 into AZ 02xx namespace |
