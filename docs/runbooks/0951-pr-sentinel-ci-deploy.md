# 0951 — pr-sentinel: CI deploy via Cloudflare Workers Builds

- **Date:** 2026-07-30
- **Issue:** #1974
- **Status:** Setup pending — the dashboard connection is a one-time operator action; everything else is already in place.
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

Then set these build settings:

| Setting | Value | Why |
|---|---|---|
| **Root directory** | `sentinel` | The Wrangler config lives in a subdirectory of a large repo. This is the documented [monorepo](https://developers.cloudflare.com/workers/ci-cd/builds/advanced-setups/#monorepos) mechanism. |
| **Build command** | `npm test` | Gates the deploy on the vitest suite. A failing test means no deploy — this answers the "should deploys be test-gated?" question #1974 raised. |
| **Deploy command** | `npx wrangler deploy` | The default. Listed explicitly so it is not silently changed. |
| **Build watch paths** | `sentinel/*` | AssemblyZero receives many pushes that do not touch the Worker. Without this, every push to `main` triggers a build. See [Build Watch Paths](https://developers.cloudflare.com/workers/ci-cd/builds/build-watch-paths/). |
| **API token** | leave blank | Cloudflare auto-generates and reuses one. Do not create a token. |

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
