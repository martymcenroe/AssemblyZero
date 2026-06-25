# CloudFlare Access-Protected App Reference Architecture

A cross-project playbook for putting a CloudFlare Worker app behind **CloudFlare
Access** with two kinds of caller: a **human in a browser** and a **script/CLI**.
Derived from production experience wiring `chiron.thrivetech.ai` (Workers +
assets + R2 + Access + a CLI `sync` command) in June 2026. Every gotcha below
cost real hours to find; they are not obvious from the CF docs.

This complements:
- **0013** (Operational Dashboard Reference Architecture) — the app layers.
- **0928** (`runbooks/0928-cloudflare-zone-setup.md`) — zone/DNS setup.
- **ADR-0216** (in-process secret decryption) — the credential-handling posture.

---

## 1. The shape

```
Browser ──(email-PIN / SSO)──┐
                             ├─► CF Access ──► Worker (assets + /api/*) ──► R2/D1
CLI/script ──(service token)─┘
```

One Worker serves the SPA and the `/api/*` JSON. CF Access sits in front of the
custom domain. **Two caller classes need two different auth mechanisms**, and
conflating them is the #1 time sink.

---

## 2. Deploy (Workers-with-assets)

One `wrangler deploy` ships the static build AND the Worker. `wrangler.toml`:

```toml
name = "my-app"
main = "worker/index.ts"
compatibility_date = "2026-..."

[[routes]]
pattern = "my-app.example.com"
custom_domain = true        # auto-creates the DNS record via the Workers

[assets]                     # Custom Domains API — no zone-write PAT needed
directory = "./dist"
binding = "ASSETS"
not_found_handling = "single-page-application"
```

The `custom_domain = true` route auto-provisions DNS through the **Workers Custom
Domains API**, which the OAuth `workers_routes: write` scope already covers — you
do NOT need a zone-write PAT for the binding. (You still need one for *Access
policy* writes; see §6.)

---

## 3. Human auth (browser)

CF dashboard → **Access controls → Applications → Create new self-hosted
application** (the 2026 UI renamed "Zero Trust" to "Cloudflare One"; the create
button is "Create new", not "Add an application").

- **Destinations → Public hostnames:** the protected host.
- **Policy:** action `Allow`, Include → Emails → the operator's email.
- **Login method:** ensure a method exists that authenticates the operator AS
  that email (One-time PIN to the inbox, or an IdP).

> **GOTCHA 1 — "That account does not have access."** The policy email must match
> the identity the login method asserts. The generic "Cloudflare" SSO button
> signs the user in as their **CloudFlare account email**, which is often NOT the
> app's contact inbox. If the policy lists the contact inbox but the user logs in
> via the Cloudflare button, Access denies them. Fix: either list the account
> email, or add a **One-time PIN** login method (Settings → Authentication →
> Login methods) and list the inbox, then log in via OTP.

> **GOTCHA 2 — two saves.** Editing a policy from the application page has a
> "Save policy" button AND a separate bottom-of-page "Save". Both are required;
> missing the second silently discards the change.

---

## 4. Machine auth (CLI / scripts) — the load-bearing section

A script can't do the email-PIN dance. It authenticates with an Access
**service token**.

1. **Access controls → Service credentials → Create Service Token.** CF shows a
   **Client ID** (ends in `.access`) and a **Client Secret** **once**.

2. > **GOTCHA 3 — service tokens need a `Service Auth` policy, NOT `Allow`.** A
   > service-token request does NOT satisfy an `Allow` policy — `Allow` requires
   > identity-provider (human) authentication, so the request gets **302'd to the
   > login page**. The token needs its **own** policy on the app with action
   > **Service Auth** (API value `non_identity`), Include → Service Token → the
   > token. This is the single biggest time sink; an `Allow`-policy-with-a-
   > service-token-include looks correct and silently fails.

3. The script sends the token in two headers:
   ```
   CF-Access-Client-Id: <client id>
   CF-Access-Client-Secret: <client secret>
   ```

> **GOTCHA 4 — CF WAF blocks default scripted User-Agents (error 1010).** The
> CloudFlare WAF rejects the default `Python-urllib/<ver>` (and similar bot-ish)
> User-Agent with **HTTP 403, body `error code: 1010`**, BEFORE the request
> reaches the Access layer — so valid service-token headers never get evaluated.
> Any scripted client to a CF-proxied origin MUST send a real, browser-like
> `User-Agent`.

> **GOTCHA 5 — don't blindly parse the response.** When auth is missing/wrong,
> Access returns a **302 → the HTML login page**. A naive client that follows the
> redirect and `json.loads()`-es the body explodes with an inscrutable
> `JSONDecodeError: Expecting value: line 1 column 1`. Use a no-redirect opener,
> detect the 302/HTML/403-1010, and raise an actionable error instead.

---

## 5. Credential handling (ADR-0216)

The service-token Client ID + Secret are secrets. **Do NOT route them through the
shell environment** — not via `export`, not via `source ~/.../creds.env` in a
shell rc, not read through `os.environ`. That re-introduces the env-block
exposure ADR-0216 closes, AND breaks the moment a non-login shell doesn't source
the file (login shells read `~/.bash_profile`; non-login interactive shells read
`~/.bashrc` — a fresh `bash` silently has no creds).

**The program reads the credentials from a file, in-process, at the moment of
use** — held only as local variables for the request, never logged. Reference
implementation: `Chiron/src/chiron/access_creds.py` (`load_access_creds()` reads
`~/.secrets/<app>-access.env` directly; `$<APP>_ACCESS_FILE` overrides the PATH
only, never the secret). For at-rest protection, store a `.gpg` and decrypt
in-process per ADR-0216's `_pat_session.py` pattern.

This is the same principle as ADR-0216 (classic PAT): secrets are read in-process
and never exported. A CF Access service token is exactly that class of secret.

---

## 6. What the agent can vs. can't do

| Task | Who | Why |
|---|---|---|
| `wrangler deploy` (Worker + assets + custom domain) | **Agent** | OAuth `workers_*` scope covers it |
| Create R2 bucket / bind it | **Agent** | `wrangler r2 bucket create` |
| Create the Access app / policies / service token | **Operator** (dashboard) OR a classic-PAT script | OAuth lacks `access_apps_write`; only the gpg-encrypted classic PAT has it (ADR-0216) |
| Write the creds file | **Operator** | The agent must never read or transcribe the secret |
| Run the CLI that decrypts/reads the creds | **Operator** | ADR-0216 §6.1 — an agent-child process is heap-readable |

The agent owns repeat deploys end-to-end. Access configuration is operator-gated
because the elevated scope lives only in the operator's gpg-encrypted PAT, and
because the live secret must not pass through an agent's process.

---

## 7. Checklist for a new Access-protected app

- [ ] `wrangler.toml` with `custom_domain = true` + `[assets]`; `wrangler deploy`
- [ ] Access app on the custom domain; `Allow` policy + a matching login method (§3)
- [ ] Service token + a separate **Service Auth** policy (§4 GOTCHA 3)
- [ ] Scripted client sends a real `User-Agent` (§4 GOTCHA 4)
- [ ] Scripted client detects 302/HTML/403 and errors clearly (§4 GOTCHA 5)
- [ ] Creds read from a file in-process, never via env (§5)
- [ ] Runbook documents all of the above for the next operator
