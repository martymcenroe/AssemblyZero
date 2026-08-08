# 0225 - Authenticated by Default: OIDC Is the Gate and Public Routes Are an Enumerated Allowlist

**Status:** Accepted
**Date:** 2026-08-07
**Supersedes:** none
**Related:** ADR-0219 (CLAUDE.md division of responsibility), ADR-0222 (adversarial PR security review)

---

## Context

Two private applications in the fleet share a shape: a single Worker serving a React client and a JSON API, D1 for state, an OIDC provider for identity, and an operator-only administrative surface gated by an allowlist in worker configuration.

They reached opposite answers to the same question — whether a stranger may use the application without signing in — and one of them arrived at "yes" without anyone deciding it.

In the first application the question was settled by operator directive and recorded in the code that implements it: the identity provider **is** the gate, no anonymous identities are minted, and an unconfigured provider fails closed as a hard outage rather than degrading to anonymous access. Its handful of deliberately public endpoints each carry a comment naming the reason it is public.

The second application drifted the other way. An audit on 2026-08-07 found **nine ungated routes**, among them the complete reviewed question corpus, the full lesson prose, the global concept graph, a leaderboard naming other users, and an unauthenticated write into D1 that accepted an unbounded array and turned one request into an arbitrarily large database batch.

Three properties of that drift are the reason this ADR exists, because none of them is specific to the application it happened in.

**Every ungated route was correct when written.** Under an anonymous-practice design, a public corpus endpoint is not a defect. The routes became defects when the product decision changed, and nothing in the repository noticed, because a route's authorization posture was expressed only by whether a human remembered to wrap the handler. Nothing distinguished *public on purpose* from *ungated by omission*.

**An edge access policy masked it.** The application sat entirely behind an identity-aware edge proxy: every unauthenticated probe of the live host was redirected to the edge login and never reached the Worker. The application's own authorization was therefore never exercised in production. A comment in that repository states it plainly about the write path — the edge policy was the only thing standing between the open internet and a write straight into the corpus — and the same sentence turned out to be true of nine read paths nobody had looked at. The edge control was substituting for authorization rather than layering over it, and the substitution is invisible precisely while it is working.

**The intent was written down in the wrong layer.** The client's navigation module gave the leaderboard door an authority floor above anonymous, with a comment explaining that the board names other users and is not a stranger's to read. The reasoning was correct. The endpoint stayed open. A hidden door with an open endpoint behind it is not a boundary; it is a boundary-shaped decoration, and it is what you get whenever a policy is expressed in a layer that does not enforce it.

Adding nine gates fixes nine routes. It does not stop the tenth.

## Decision

**Applications in the fleet are authenticated by default. OIDC sign-in is the gate, the set of public routes is closed and enumerated with a stated reason per entry, and that enumeration is enforced by a test derived from the router rather than maintained by convention.**

### 1. Anonymous is not a tier

Sign-in is required to use the application. There is no guest identity, no anonymous-with-degraded-persistence mode, and no "best-effort" client behaviour that interprets a 401 as permission to continue. Where anonymous rows already exist in a database from an earlier design, they are retained — they are somebody's history — but no new ones are written.

An unconfigured identity provider **fails closed**. It is a hard outage, and it is reported as one. Falling back to anonymous access when authentication is unavailable converts a visible outage into a silent removal of the gate, which is the worse failure in every case.

### 2. The public set is closed, enumerated, and justified

Public routes are an allowlist, not a residue. Each entry carries a one-line reason in the same place as the entry. An entry with no reason is not an entry.

The reason matters more than the list. Two categories recur and both are legitimate:

- **The routes that make signing in possible.** The OIDC authorization redirect and callback, the endpoint reporting which providers are configured, the identity endpoint that answers "nobody" for a visitor, and sign-out. These cannot require a session without making a session unobtainable.
- **The routes a person the gate has turned away still needs.** A problem-reporting endpoint is the canonical case. The first application learned this from a live incident: a signed-out user hit a 403 and the report was filed by exactly the person an authenticated-only form would have silenced. Similarly, a token-authorized unsubscribe must not require a sign-in, because an unsubscribe that requires signing in is not an unsubscribe — the signed token **is** the authorization.

Unauthenticated endpoints that write are subject to **hard caps expressed as named constants and checked before any write** — on body size, on array length, on every field bound into a statement. The framing that keeps this honest is that limits on an unauthenticated write are not validation niceties: the endpoint must not be a free write amplifier.

### 3. The enumeration is enforced by a test, derived from the router

A test enumerates the routes the application dispatches and asserts each is either gated or named on the public allowlist. A route that is neither fails the suite, and the failure message names the route and states the two ways to resolve it.

**The enumeration must derive from the router itself.** A hand-maintained second list of routes is a second thing to forget, which is the failure being closed. Where a router cannot be introspected, the dispatch table is extracted into an exported array of route descriptors and the handler iterates it — a refactor that pays for itself by making the whole posture readable in one place.

A test that merely asserts today's allowlist passes forever while the next route is added ungated. That is theatre, and it is worse than no test, because it reads as coverage.

### 4. Edge access control is a second factor, never the gate

An identity-aware edge proxy in front of an application is a legitimate and useful control. It is not authorization, and an application must be correct with it removed.

Two obligations follow. An application behind an edge policy is **not** thereby exempt from gating its own routes; and the ordering of any change that narrows or removes such a policy must place the application's own gates first. Narrowing the policy before the gates land publishes every ungated route at once — which is exactly the sequencing that turns a masked design flaw into an incident.

### 5. Administrative authority is fail-closed and configuration-sourced

- Authority derives from an allowlist in worker configuration, matched against provider-asserted identity claims. **An empty allowlist grants nothing.** A misconfigured deployment must lock the operator out, never open the surface to everyone.
- Configuration rather than only a database row, for two reasons that are both load-bearing: a role column that defaults to unprivileged for every account, with nothing that ever grants another value, locks out the person who owns the system; and configuration survives a database rebuild, which is a documented operation in at least one of these applications.
- Authority may have several independent sources — a configuration allowlist, a stored role, a verified edge identity — with any one sufficient. Sources are evaluated **at the gate**, not trusted from the claims a session token was minted with, so a session issued before a configuration change still resolves correctly on the next request.
- A verified edge identity may grant authority. **Verified** is the operative word: signature, audience, issuer, and expiry all checked against the provider's keys. An edge proxy's assertion arrives as a request header, and any caller can set a header. Trusting an unverified one makes administrative authority self-asserted, which is strictly worse than the rejection it replaces.
- Identity strings in an allowlist are **identities, not credentials**. Holding one grants nothing without also authenticating as that person, so the allowlist is ordinary configuration rather than a secret. The corollary is that an operator's several identities across several providers all belong in the list; a missing entry is what causes a lockout, and extra entries cost nothing.

### 6. One rejection posture for administrative surfaces, fleet-wide

The two applications answer a rejected caller differently. One returns a 404 indistinguishable from a route that does not exist. The other returns a 403 that names the caller's own identity strings **and the configuration variable that would grant access**.

Both were reasoned. The informative version exists because being told "you lack authority" without being told what to add is what turns a configuration typo into a lockout, and its author was in that position. But echoing the caller's own identity is defensible where naming the authorization mechanism to someone who just failed it is not — that is reconnaissance, handed over on request.

**The fleet-wide posture is the hidden one: an administrative route rejects as though it does not exist.** Lockout diagnosis is preserved, and moved somewhere an attacker cannot read — the worker log, or a response available only to a caller who already holds a valid session and merely lacks authority. Where an application deviates, the deviation is recorded in its own ADR with its reasoning, not left as an undocumented difference between siblings.

### 7. The doctrine lives in the repository's CLAUDE.md

Per ADR-0219 each repository's CLAUDE.md carries what is true for that repository. The auth posture qualifies, and its absence is part of why the drift happened: an agent adding a route had no statement of the rule it was about to violate. The application that did not drift carries its gate decision, with the date it was corrected, inline in the file its agents read at session start.

## Consequences

- **Public endpoints become a deliberate act.** Adding one requires an allowlist entry and a written reason, and the test refuses the route until both exist. This is friction on purpose; it is the only step at which the question gets asked.
- **A whole class of drift becomes loud.** Any future product change that alters who may reach the application surfaces as a failing test enumerating the affected routes, rather than as an audit finding some number of months later.
- **The refactor is the deliverable, not a side effect.** Extracting a dispatch table so it can be enumerated leaves the authorization posture legible in one place. Reviewers stop having to trace nested conditionals to answer "is this public?".
- **Edge policies get narrowed rather than removed.** Retaining an edge proxy over administrative surfaces while learner-facing routes rely on the application's own gate gives genuine defence in depth. It also means such a change is production configuration under the fleet rules: tracking issue, blast-radius statement, rollback plan, post-change verification.
- **Applications become correct standing alone.** The test measures the application, not the deployment, so a masked flaw cannot pass. This is the property that was missing: a Worker whose authorization has never been exercised in production has not been shown to have any.
- **Cost is honestly a real one.** Nine gates, a route-table refactor, a test, client changes where a 401 was previously treated as permission to continue anonymously, and a public-route allowlist with a reason for every entry. It is smaller than the audit that finds them later, and much smaller than the incident.
