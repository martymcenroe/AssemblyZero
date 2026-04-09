# Sextant — Build Spec (Demo Night)

## Context

Demo app for a Monday morning meeting with the CEO of Ringside Talent (a small consulting company). They are competing for a contract to advise a President-level executive at a multi-billion-dollar organization on enterprise AI strategy. Marty (repo owner) is the technical advisor being brought in.

Sextant is an employee engagement platform where employees of the client organization can share how they use AI, voice concerns, and challenge what AI can do. It replaces every "AI adoption survey" and "change management playbook" in existence with a live, interactive, Claude-mediated conversation.

**This is a demo build. Scope discipline is critical. Tonight to build and deploy.**

---

## Tech Stack (Decided)

| Layer | Technology | Why |
|-------|-----------|-----|
| Backend | **Cloudflare Worker (TypeScript)** | Proven pattern (Hermes, Career Dashboard), zero cold starts, one-command deploy |
| Database | **Cloudflare D1 (SQLite)** | Zero provisioning, included with Worker, sufficient for demo |
| Frontend | **React + Vite**, served as Worker static assets | Single deployment unit, no CORS |
| Auth | **LinkedIn OAuth 2.0 (OpenID Connect)** | Reusing existing LinkedIn app registration |
| AI | **`@anthropic-ai/sdk`** (confirmed Workers-compatible) | Official Cloudflare Workers support, no polyfills needed |
| Deployment | **`wrangler deploy`** to `voices.sextant.ceo` | Custom domain via Cloudflare zone |

### Architecture: Single Worker

Everything runs in one Cloudflare Worker:
- `/api/*` routes handle auth, posts, votes, Claude integration
- `/*` serves the React static build (Vite output)
- No CORS configuration needed (same origin)
- One `wrangler deploy` deploys everything

Reference implementation: Hermes (`C:\Users\mcwiz\Projects\Hermes\wrangler.toml`) uses this same pattern.

---

## Repository

- **Name:** `sextant` (private repo under `martymcenroe`)
- **Shadow wiki:** `sextant-wiki` (public repo, created separately — private repo wikis inherit visibility)
- **Domain:** `voices.sextant.ceo`
- **Cloudflare zone:** `sextant.ceo` (nameservers pointed to Cloudflare, may still be propagating)

---

## LinkedIn OAuth (Reference: Aletheia)

### What to Reuse

Aletheia's LinkedIn app registration (`86yrqtke9ewvhk`) is being reused. The redirect URI `https://voices.sextant.ceo/auth/linkedin/callback` must be added to the LinkedIn app's authorized redirect URIs in the LinkedIn Developer Portal (human step).

### Scopes

```
openid profile email
```

Uses the OIDC `/v2/userinfo` endpoint (NOT the restricted `/v2/me` Profile API). Returns:
- `sub` — stable LinkedIn member ID (use as primary key)
- `name` — display name
- `email` — email address
- `picture` — avatar URL

### Flow (Web App — Different From Aletheia)

Aletheia is a browser extension using `chrome.identity.launchWebAuthFlow()`. Sextant is a web app. The flow is:

1. User clicks "Sign in with LinkedIn"
2. Browser redirects to `https://www.linkedin.com/oauth/v2/authorization` with client_id, redirect_uri, scope, state (CSPRNG)
3. User authorizes on LinkedIn
4. LinkedIn redirects to `https://voices.sextant.ceo/auth/linkedin/callback?code=XXX&state=YYY`
5. Worker validates state, exchanges code for tokens via `https://www.linkedin.com/oauth/v2/accessToken`
6. Worker fetches user profile via `https://www.linkedin.com/oauth/v2/userinfo`
7. Worker creates/updates user in D1 (keyed by `sub`)
8. Worker issues JWT, sets as `httpOnly` cookie
9. Redirect to feed page

### Session Strategy

- JWT (HS256) in `httpOnly`, `Secure`, `SameSite=Lax` cookie
- 24-hour expiration
- JWT payload: `{ sub, name, iat, exp }`
- Signing secret stored as Worker secret (`wrangler secret put JWT_SECRET`)

### Auth Model (Demo Simplification)

**Any LinkedIn user can log in. No roles, no admin, no demo user distinction.** Everyone gets the same experience. If posts need to be deleted during the demo, do it via D1 directly (`wrangler d1 execute`).

Role-based access (admin, verified employee, anonymous) is post-demo work.

---

## Database Schema (D1)

```sql
CREATE TABLE users (
  id TEXT PRIMARY KEY,           -- LinkedIn OIDC sub claim
  name TEXT NOT NULL,
  email TEXT,
  headline TEXT,
  picture_url TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  last_login TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE posts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL REFERENCES users(id),
  category TEXT NOT NULL CHECK (category IN ('use', 'concern', 'challenge')),
  original_text TEXT NOT NULL,
  polished_text TEXT,
  claude_response TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE votes (
  user_id TEXT NOT NULL REFERENCES users(id),
  post_id INTEGER NOT NULL REFERENCES posts(id),
  value INTEGER NOT NULL CHECK (value IN (-1, 1)),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (user_id, post_id)
);
```

Indexes:
```sql
CREATE INDEX idx_posts_category ON posts(category);
CREATE INDEX idx_posts_created ON posts(created_at DESC);
CREATE INDEX idx_votes_post ON votes(post_id);
```

---

## Core Features (BUILD TONIGHT)

### 1. Landing Page

- Clean branded header: "Sextant" with tagline: "What your organization already knows about AI"
- Brief explanation: three categories, why this exists, how to participate
- "Sign in with LinkedIn" button — prominent
- ThriveTech.ai branding in footer — subtle, professional
- Desktop only for demo — mobile responsiveness is post-demo

### 2. Three Categories

Each category is a card/tab on the main feed page:

**"How I Use AI Today"** (category: `use`)
- Subtitle: "Share how you're already using AI to create business value"
- Surfaces hidden adoption. The most valuable discovery data.

**"What Concerns Me About AI"** (category: `concern`)
- Subtitle: "Voice your honest concerns — about data, jobs, ethics, or anything else"
- Surfaces real resistance. Not complaints — signal.

**"What AI Will Never Do"** (category: `challenge`)
- Subtitle: "Challenge AI with something you believe only humans can do"
- The bold one. Every entry becomes a use case to explore.

### 3. Post Submission Flow

1. User selects a category
2. User writes their post (min 50 chars, max 2000)
3. **Before publishing:** POST to `/api/posts` sends text + category to Claude via `@anthropic-ai/sdk`:
   - **Light polish:** Fix grammar, tighten prose, preserve voice. Do NOT rewrite.
   - **Engagement response:** 2-4 sentence thoughtful response (see system prompt below)
4. User sees polished version + Claude's response. Can accept, edit, or revert to original.
5. Post publishes to feed.

### 4. Feed Display

- All posts in unified feed, newest first
- Each post shows: author name, author headline (from LinkedIn), category tag (color-coded), post text, Claude's response, timestamp, vote counts
- Filter by category (three toggle buttons)
- Clean card layout — enterprise aesthetic, not startup

### 5. Voting

- Authenticated users can upvote or downvote any post (not their own)
- One vote per user per post (upsert on `votes` table)
- Vote counts displayed on each post

### 6. Seed Posts

Create these after deployment via the app itself (log in as Marty):

**Category: use**
> "I use Claude to prep for every client meeting. I upload the last three call transcripts and our CRM notes, then ask for a briefing with three things I should bring up and one risk I might be missing. Takes two minutes. Used to take me an hour of reading."

**Category: concern**
> "My worry isn't that AI takes my job. It's that my company will use AI metrics to judge my performance without understanding what I actually do. If AI can draft a proposal in five minutes, does my manager now expect ten proposals a day instead of two good ones?"

**Category: challenge**
> "AI will never close a deal with a difficult client. The last three deals I closed happened because I read the room, knew when to shut up, and bought the right person a drink at the right moment. Try automating that."

---

## System Prompt for Claude Post Engagement

```
You are the AI engagement layer for an enterprise employee forum about AI adoption.
Your role is to make every contributor feel heard, respected, and curious.

When polishing a post:
- Fix grammar and clarity only. Do not change tone, vocabulary level, or personality.
- If the post is already well-written, change nothing. Say so.
- Never add jargon, buzzwords, or corporate language.
- Keep the author's voice. A blunt post stays blunt. A cautious post stays cautious.

When responding to a post:
- Category "use": Acknowledge the use case. If you can see a connection to a broader
  pattern or an adjacent use case they might not have considered, mention it briefly.
  Be genuinely curious, not performatively impressed.
- Category "concern": Validate the concern. Do not dismiss, minimize, or "well actually."
  If there is relevant context that might help them think about it differently, offer it
  gently. If the concern is legitimate and unresolvable, say so.
- Category "challenge": This is delicate. The contributor is drawing a line. Respect the
  line. Then, without being adversarial, explore one edge case or one dimension where AI
  might surprise them. Frame it as genuine inquiry, not a gotcha. End with something that
  honors their expertise: "You know this domain — what would change your mind?"

Tone: warm, direct, intellectually honest. Never sycophantic. Never dismissive.
You are a thoughtful colleague, not a chatbot.

Keep responses to 2-4 sentences maximum.
```

The Claude API call should use `claude-sonnet-4-20250514` and request a structured response:

```typescript
const response = await anthropic.messages.create({
  model: "claude-sonnet-4-20250514",
  max_tokens: 1024,
  system: SYSTEM_PROMPT,
  messages: [{
    role: "user",
    content: `Category: ${category}\n\nOriginal post:\n${text}\n\nRespond with JSON:\n{"polished": "...", "response": "..."}\nIf no polish needed, set polished to null.`
  }],
});
```

---

## Design

| Token | Value |
|-------|-------|
| Primary | `#1B4F72` (deep blue) |
| Accent | `#D4E6F1` (light blue) |
| Background | white, `#F2F7FB` for cards |
| Font | Inter or system font stack |

No animations, no gradients, no hero images. Enterprise tool. Desktop only for demo.

---

## Environment Variables / Secrets

```toml
# wrangler.toml [vars]
LINKEDIN_CLIENT_ID = "86yrqtke9ewvhk"
LINKEDIN_CALLBACK_URL = "https://voices.sextant.ceo/auth/linkedin/callback"

# wrangler secret put (never in code)
# LINKEDIN_CLIENT_SECRET
# ANTHROPIC_API_KEY
# JWT_SECRET
```

D1 database is bound in `wrangler.toml` as `DB`.

---

## wrangler.toml Skeleton

```toml
name = "sextant"
main = "src/worker.ts"
compatibility_date = "2025-12-01"
assets = { directory = "./frontend/dist" }

[[routes]]
pattern = "voices.sextant.ceo"
custom_domain = true

[vars]
LINKEDIN_CLIENT_ID = "86yrqtke9ewvhk"
LINKEDIN_CALLBACK_URL = "https://voices.sextant.ceo/auth/linkedin/callback"

[[d1_databases]]
binding = "DB"
database_name = "sextant-db"
database_id = "" # fill after `wrangler d1 create sextant-db`
```

---

## What NOT to Build Tonight

These go in `ROADMAP.md`:

- Anonymous posting (moderation queue)
- Executive dashboard (sliders, filters, Claude-adaptive curation)
- Employee verification (LinkedIn company check or CSV whitelist)
- Department tagging
- Conversational threads (replies)
- Export/reporting (PDF/CSV)
- Notifications (email/Slack)
- Claude adaptive filtering
- Role-based access (admin, verified, anonymous)
- Vote attribution visibility

---

## Priority Order

1. LinkedIn OAuth working end-to-end, deployed to `voices.sextant.ceo`
2. D1 schema and user creation on auth
3. Post submission with category selection
4. Claude API integration for polish + response
5. Feed display with category filtering
6. Voting mechanism
7. Seed posts
8. README and ROADMAP

**If time runs short:** cut voting before cutting Claude integration. The Claude engagement is the demo's soul.

---

## Deployment Checklist

- [ ] Worker deployed to `voices.sextant.ceo`
- [ ] LinkedIn OAuth redirect URI added to app (human step: LinkedIn Developer Portal)
- [ ] LinkedIn OAuth working end-to-end
- [ ] D1 database created and migrated
- [ ] Can submit a post in each category
- [ ] Claude polishes and responds to each post
- [ ] Feed displays posts with votes
- [ ] At least 3 seed posts (one per category)
- [ ] HTTPS working (Cloudflare handles this)
- [ ] ~~Mobile responsive~~ (post-demo)

---

## Shadow Wiki

The `sextant` repo is private. GitHub wikis inherit visibility — a private repo's wiki is also private. A separate **public** repo `sextant-wiki` must be created for any public-facing documentation or portfolio material.

---

## Repo Setup

This repo was created by `new_repo_setup.py` from AssemblyZero, which provides:
- 39-directory governance structure (docs, tests, standards, session logs)
- `.claude/settings.json` with security hooks
- `.github/workflows/pr-sentinel.yml` + `auto-reviewer.yml`
- Branch protection (require PR, block force push, require pr-sentinel check)
- `.unleashed.json` configuration

The build agent must add on top of this scaffold:
- `frontend/` directory (React + Vite)
- `src/worker.ts` (Cloudflare Worker entry point)
- `src/routes/` (API route handlers)
- `wrangler.toml` (Worker + D1 config)
- `package.json` (root, for Worker + frontend deps)
- `tsconfig.json`

---

## Reference Implementations

| Pattern | Source | What to Reference |
|---------|--------|-------------------|
| Cloudflare Worker + D1 + React | Hermes (`~/Projects/Hermes/`) | Worker structure, D1 bindings, static asset serving |
| LinkedIn OAuth (scopes, token exchange, userinfo) | Aletheia (`~/Projects/Aletheia/src/lambda_auth_function.py`) | Lines 101-197 for token exchange + profile fetch |
| Dashboard reference architecture | AssemblyZero `docs/standards/0013-operational-dashboard-reference-architecture.md` | Sections 1-2 for Worker + D1 patterns |
| JWT service | Aletheia (`~/Projects/Aletheia/src/auth/jwt_service.py`) | Lines 37-65 for JWT creation pattern |
