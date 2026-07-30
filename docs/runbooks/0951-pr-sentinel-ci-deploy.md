# 0951 — pr-sentinel: CI deploy via Cloudflare Workers Builds

- **Date:** 2026-07-30 (UI section corrected same day against the live dashboard)
- **Issue:** #1974
- **Status:** Setup pending — the dashboard connection is a one-time operator action; everything else is already in place.

> **Writing rule for this runbook.** Every UI step here is either linked to its current Cloudflare docs page or verified against a screenshot of the live dashboard. Do **not** update it from recalled navigation. #1818 records two incidents of stale Cloudflare paths being handed to the operator, and the first draft of this file repeated the mistake — it listed Root directory as a top-level field (it is under Advanced settings) and Build watch paths as available at connect time (it only appears after connecting). If Cloudflare moves something, re-query the docs and correct this file.
- **Related:** #1972 (deployed-source proof), #1973 (the manual deploy that motivated this), standard `0016-pr-sentinel-system-architecture.md`

## Why this exists

The `pr-sentinel` Worker had **no CI deploy** for its entire life. It was published by hand with `wrangler deploy` from whatever a local working tree happened to contain.

How loose that was, measured:

| Event | Time (Central) |
|---|---|
| Worker version `86190254` uploaded — served for 4 months | 2026-03-20 11:03:36 AM |
| The commit whose content it contained was authored | 2026-03-20 11:03:54 AM (**18s later**) |
| That commit reached `main` via PR #862 | 2026-03-21 8:01:57 AM |

The live artifact was published 18 seconds before its source was committed and ~21 hours before that source reached `main`. For that window it existed in no commit anywhere.

This is the root cause of #1972. Two source trees declared the same Worker name, deployment was manual, and nothing tied the running artifact to a commit — so "which source is live?" could not be answered without inspecting the deployed bundle. It matters because this Worker is the sole live issue-reference gate for every PR in every repo.

## Why Workers Builds rather than a GitHub Actions workflow

The obvious approach — `.github/workflows/deploy-sentinel.yml` using `wrangler-action` — needs two things this fleet makes expensive:

1. A `CLOUDFLARE_API_TOKEN` repo secret. Creating and storing a secret value is an operator-only action; agents must never handle secret values (transcripts capture everything).
2. Landing a workflow file. The fine-grained PAT has no `workflow` scope, so it would need the ADR-0216 classic-PAT Contents API path, and ADR-0216 requires the **operator** to run that script.

Workers Builds removes both:

- **No API token to create.** Per the [Workers Builds configuration docs](https://developers.cloudflare.com/workers/ci-cd/builds/configuration/), the API token field is *optional*: "By default, Cloudflare will automatically generate an API token for your account when using Workers Builds, and continue to use this API token for all subsequent builds."
- **No workflow file**, therefore no `workflow` scope and no ADR-0216 landing.

The whole setup is one dashboard connection.

## Operator setup (one time)

Per the [current Workers Builds docs](https://developers.cloudflare.com/workers/ci-cd/builds/) — do not follow remembered UI paths, Cloudflare moves things (see #1818):

1. Go to **Workers & Pages**: <https://dash.cloudflare.com/?to=/:account/workers-and-pages>
2. Select the **`pr-sentinel`** Worker.
3. **Settings** → **Builds** → **Connect**, and follow the prompts to connect `martymcenroe/AssemblyZero`.

### What the "Connect to a repository" panel actually contains

Verified against the live dashboard 2026-07-30. **Not all settings are on this panel** — an earlier version of this runbook listed them as if they were, which sent the operator hunting for a field that does not exist there.

The panel has, top to bottom:

- **Git account** — a selector, **empty until you choose an account**. If nothing is listed, use the add-account option, which installs and authorizes the [Cloudflare Workers and Pages GitHub App](https://github.com/apps/cloudflare-workers-and-pages). This is the first required field; leave it unset and the rest of the form may not behave.
- **Repository** — pick `AssemblyZero`.
- **Production branch** — `main`.
- **Builds for non-production branches** — checkbox, **checked by default. Uncheck it.** With it on, every push to any non-production branch triggers a build running `npx wrangler versions upload`. AssemblyZero has constant agent branch activity, and because watch paths cannot be scoped until *after* connecting, this would burn account build limits on pushes that never touch `sentinel/`. There is also no upside: preview versions exist to exercise a change before promoting it, and this Worker is a webhook receiver with no UI — its real test is the vitest suite, which already runs in AssemblyZero's CI. Re-enable later only if per-branch preview versions become useful, and only once watch paths are scoped.
- **Build command** *(marked Optional)* — see table below.
- **Deploy command** — pre-filled `npx wrangler deploy`.
- **Advanced settings** — a set of collapsed accordions. **Root directory is in here**, not at top level. Expand the chevron. Also holds Non-production branch deploy command, API Token, Build variables, and Build caching.

| Setting | Value | Where | Why |
|---|---|---|---|
| **Root directory** | `sentinel` | Advanced settings (collapsed) | The Wrangler config lives in a subdirectory of a large repo. Documented [monorepo](https://developers.cloudflare.com/workers/ci-cd/builds/advanced-setups/#monorepos) mechanism. Required — without it the build finds no `wrangler.toml`. |
| **Deploy command** | `npx wrangler deploy` | Main panel | The default. Stated explicitly so it is not silently changed. |
| **Build command** | `npm test` | Main panel, Optional | Gates the deploy on the vitest suite, answering the "should deploys be test-gated?" question #1974 raised. Optional — if the form misbehaves, leave it blank and add it after connecting. |
| **API token** | leave blank | Advanced settings | Cloudflare auto-generates and reuses one. Do not create a token. |

### Settings that only exist AFTER connecting

**Build watch paths is not on the connect panel.** Per the [Workers Builds changelog](https://developers.cloudflare.com/changelog/post/2024-12-29-faster-builds/): "Once connected, you'll see options to configure Build Caching and Build Watch Paths."

So after the connection succeeds, return to **Settings → Builds** and set:

| Setting | Value | Why |
|---|---|---|
| **Build watch paths** | `sentinel/*` | AssemblyZero receives many pushes that never touch the Worker. Without this, every push to `main` triggers a build. See [Build Watch Paths](https://developers.cloudflare.com/workers/ci-cd/builds/build-watch-paths/). |

### If the panel misbehaves

Reported symptoms on first setup: the panel flashing, and Build command / Root directory not persisting.

Check the **Git account** selector first — it is the first required field and was empty when this was observed.

Fallback: connect with defaults and nothing else set, then configure Root directory in the ordinary **Settings → Builds** page rather than the connect panel. A first build that fails costs nothing — **a failed build deploys nothing** — so an initial failure is a safe way to get past a stuck form.

### The one trap

The Cloudflare docs carry an explicit warning: the Worker name in the dashboard **must match** the `name` in the Wrangler config at the specified root directory, or the build fails.

Verified already consistent — `sentinel/wrangler.toml` declares `name = "pr-sentinel"` and the dashboard Worker is `pr-sentinel`. Do not rename either.

## Verification after setup

1. Push any change under `sentinel/` to `main`.
2. A build appears in **Settings → Builds**. It should install deps in `sentinel/`, run `npm test` (58 tests at time of writing), then `wrangler deploy`.
3. Confirm the running version changed:
   ```bash
   cd sentinel && npx wrangler deployments list
   ```
4. Confirm the deployed code is what you expect — read the Worker, not the repo (see below):
   ```bash
   npx wrangler versions list
   ```

To prove the gate works, push a commit under `sentinel/` that breaks a test and confirm no deploy occurs. Revert afterwards.

## The standing rule this replaces

Until this is connected, **the repo cannot tell you what is running.** Manual deployment means the deployed artifact and `main` can diverge in either direction, silently:

- a source fix that is never deployed looks shipped and changes nothing;
- production can run code that no commit describes.

So re-verification must **read the deployed Worker** rather than reason about which tree looks maintained. Three ways, cheapest first:

- the Cloudflare observability API / MCP (`workers_get_worker_code`)
- `npx wrangler deployments list` from `sentinel/`
- the Cloudflare dashboard's Quick Edit view

Once Workers Builds is connected, the running version is traceable to a commit and this caution becomes historical — but leave it documented, because a disconnection would silently restore the old failure mode.
