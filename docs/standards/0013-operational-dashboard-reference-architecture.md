# Operational Dashboard Reference Architecture

A cross-project playbook for building operational dashboards. Derived from production experience with Hermes (Cloudflare Workers + D1 + React) and intended to guide any project that needs a web-based operational UI backed by AWS or similar cloud services.

This is not prescriptive about specific frameworks. It captures **patterns that worked**, **patterns that didn't**, and **decisions you'll face early** that are expensive to change later.

---

## 1. Architecture: The Three Layers

Every operational dashboard has three layers. Decide upfront where each lives.

| Layer | Responsibility | Hermes Implementation |
|-------|---------------|----------------------|
| **API** | Auth, RBAC, business logic, DB access | Cloudflare Worker (HTTP handler) |
| **Frontend** | UI rendering, client routing, state | React 19 + TypeScript + TanStack |
| **Storage** | Persistence, queries, aggregations | D1 (SQLite), R2 (assets) |

### Key Decision: Monolith vs. Separate API

Hermes runs everything in a single Worker — email handling, cron jobs, and the dashboard API share one deployment unit. This is fine when:

- The dashboard is an operational tool for one person or a small team
- The API surface is modest (< 50 endpoints)
- You want one deploy, not two

Split the API into its own service when:

- The dashboard has different scaling characteristics than the core workload
- Multiple teams need independent deploy cadences
- The API needs to serve multiple frontends (web, mobile, CLI)

### Key Decision: Inline HTML vs. SPA

Hermes started with inline HTML rendered from the Worker (~1300 lines of vanilla JS in `views.js`). This was fast to build but hit a wall at:

- ~20 interactive components needing state management
- Form validation becoming repetitive without a library
- No component reuse between pages

**Lesson:** Inline HTML works for < 10 pages with minimal interactivity. Once you need forms, modals, or client-side routing, invest in an SPA upfront. The migration cost only grows.

---

## 2. Authentication & Authorization

### 2.1 Three Auth Methods (Recommended Minimum)

Production dashboards need at least two auth paths. Hermes uses three:

| Method | Use Case | Implementation |
|--------|----------|---------------|
| **API Key** | Owner/admin shortcut, CI/CD, scripts | `Authorization: Bearer {key}` header or `?key=` query param |
| **OAuth Session** | Primary user login | GitHub OAuth → session cookie (7-day TTL) |
| **Viewer Token** | Temporary read-only sharing | UUID token, 4-hour TTL, stored in DB |

**Pattern: Auth at the gateway, not per-endpoint.**

```javascript
// Check auth ONCE at the router level
const auth = await authenticateRequest(request, env);
if (!auth.authenticated) return renderLoginPage();

// Then pass role to all handlers
return handleAPI(path, request, env, auth.role);
```

Every endpoint then checks `role` — but the auth check itself is centralized.

### 2.2 Role-Based Access Control

Three roles cover most operational dashboards:

| Role | Can Read | Can Write | Can Admin |
|------|----------|-----------|-----------|
| **owner** | Everything | Everything | Everything |
| **editor** | Everything | Own scope | Nothing |
| **viewer** | Demo/public data only | Nothing | Nothing |

**Lesson from Hermes:** The viewer role needs a concept of "demo-safe" data. You can't just strip PII and show everything — you need to explicitly label which records are safe to expose.

```javascript
// Hermes checks for a "demo" label on each conversation
if (role === "viewer") {
  const labels = await getLabels(db, id);
  if (!labels.some(l => l.label === "demo")) {
    return new Response("Forbidden", { status: 403 });
  }
}
```

**Fail closed:** If you can't determine whether data is safe, deny access. Never show UI and then disable buttons — don't render the page at all.

### 2.3 Viewer Tokens (Temporary Access)

This pattern lets you share a dashboard link with an interviewer, recruiter, or client for a limited window:

```
https://dashboard.example.com/?viewer=a1b2c3d4-...
```

Implementation:

1. Owner generates a token (UUID) via admin API
2. Token stored in DB with `created_at` and `expires_at` (4 hours)
3. Dashboard checks `?viewer=` param, validates against DB
4. Expired tokens return a "session expired" login page
5. Cleanup: purge tokens older than 24 hours on every auth check

**Pitfall:** Don't forget to auto-purge. Stale tokens in the DB are a compliance risk even if expired.

### 2.4 Data Masking for Restricted Roles

Apply masking at **API response time**, not at storage. Single source of truth in the database; the API layer transforms on the way out.

```javascript
function maskForViewer(data) {
  return {
    sender_email: `Contact #${data.id}`,  // Replace PII with ID
    sender_name: null,                      // Strip entirely
    subject: maskPatterns(data.subject),    // Regex-based redaction
  };
}
```

Patterns to mask:

| Pattern | Replacement |
|---------|-------------|
| Email addresses | `<email>` |
| Phone numbers | `<phone>` |
| Company URLs | `<url>` (except your own domains) |
| Full names | `Contact #N` |

**Lesson:** Masking is harder than you think. Names appear in email bodies, subjects, signatures, and quoted replies. Start with the patterns above, then add more as you find leaks.

---

## 3. Frontend Architecture

### 3.1 Recommended Stack

This stack is battle-tested in Hermes and covers 95% of operational dashboard needs:

| Concern | Library | Why |
|---------|---------|-----|
| Framework | React 19 + TypeScript | Type safety, ecosystem, hiring pool |
| Routing | TanStack Router | Type-safe routes, search params as state |
| Data fetching | TanStack React Query | Caching, refetch, loading/error states |
| Forms | React Hook Form + Zod | Schema validation, type inference |
| UI primitives | Radix UI | Accessible, headless, composable |
| Styling | Tailwind CSS | Utility-first, no CSS debugging |
| Toasts | Sonner | Lightweight, non-blocking feedback |
| Icons | Lucide React | Consistent, tree-shakeable |
| Build | Vite | Fast dev server, optimized production builds |

### 3.2 API Client Pattern

Centralize auth injection in a single fetch wrapper. Never sprinkle auth logic across components.

```typescript
async function apiFetch<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const auth = getAuthParams(); // Reads from cookies, URL params, or localStorage
  let url = `/api${path}`;
  if (auth.query) url += (url.includes("?") ? "&" : "?") + auth.query;

  const res = await fetch(url, {
    ...opts,
    headers: { ...opts.headers, ...auth.header },
    credentials: "include",
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(body.error || res.statusText);
  }
  return res.json() as Promise<T>;
}
```

**Lesson:** Always catch the JSON parse. A 502 from a proxy returns HTML, not JSON. Your error handler must survive that.

### 3.3 React Query Configuration

```typescript
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,           // 30 seconds — dashboard data isn't real-time
      retry: 1,                     // One retry, then show error
      refetchOnWindowFocus: false,  // Don't spam the API on tab switch
    },
  },
});
```

**Pitfall:** `retry: 1` with no backoff can mask transient failures. Consider:

```typescript
retry: (failureCount, error) => {
  if (error.message.includes("401") || error.message.includes("403")) return false;
  return failureCount < 2;
},
retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 10000),
```

Don't retry auth failures. Do retry network glitches with exponential backoff.

### 3.4 State Management

For operational dashboards, you almost never need Redux or Zustand. The combination of:

- **React Query** for server state (fetched data)
- **useState/useReducer** for UI state (sort order, filters, modals)
- **URL search params** for shareable state (active tab, filter selection)
- **localStorage** for preferences (collapsed sections, theme)

...covers everything. Add a global store only if you have cross-page state that isn't server-derived.

### 3.5 Component Patterns

**Role checks at page level, not element level:**

```typescript
// Good: Don't render the page at all
if (!canViewAdmin(role)) {
  return <div>Admin access required.</div>;
}

// Bad: Render everything, then disable buttons
<button disabled={role !== "owner"}>Delete</button>
```

**Toast over confirm dialogs:**

```typescript
// Good: Non-blocking feedback
toast.success("Conversation archived");

// Bad: Blocks the entire UI
if (!confirm("Are you sure?")) return;
```

Users hate `confirm()` dialogs. Use toasts with an undo action if the operation is reversible.

---

## 4. API Design

### 4.1 Route Organization

Group by resource, not by action:

```
GET    /api/conversations              — list
GET    /api/conversations/:id          — detail
PATCH  /api/conversations/:id          — update
DELETE /api/conversations/:id          — delete
GET    /api/conversations/:id/messages — nested resource
POST   /api/conversations/:id/send     — action

GET    /api/admin/settings             — admin namespace
POST   /api/admin/audit                — admin action
```

**Public routes go before the auth check:**

```javascript
// These don't require auth
if (path === "/api/callback") return handleCallback(request, env);
if (path === "/api/unsubscribe") return handleUnsubscribe(request, env);

// Auth gate — everything below requires a session
const auth = await authenticateRequest(request, env);
if (!auth.authenticated) return renderLoginPage();
```

### 4.2 Error Responses

Always return JSON with an `error` field. Consider adding a `code` for programmatic handling:

```json
{
  "error": "Conversation not found",
  "code": "NOT_FOUND"
}
```

**Lesson from Hermes:** We only return `{ error: message }` with no structured codes. This works until you need the frontend to distinguish between "not found" and "forbidden" for different UI behavior. Add codes from the start — it's cheap.

### 4.3 Pagination

Use **cursor-based pagination** (timestamp or ID), not offset:

```javascript
// Good: Cursor-based (stable under inserts)
const before = url.searchParams.get("before"); // ISO timestamp
if (before) query += " AND updated_at < ?";

// Bad: Offset-based (breaks when new rows are inserted)
const offset = url.searchParams.get("offset");
query += ` OFFSET ${offset}`;
```

Offset pagination skips or duplicates rows when new data arrives between page loads. Cursor pagination is stable.

---

## 5. Observability Pane

Every operational dashboard needs an observability section. Here's what to include:

### 5.1 Minimum Viable Observability

| Metric | Query Pattern | Why |
|--------|--------------|-----|
| **Messages by day** | `GROUP BY DATE(created_at), direction` | Volume trends, anomaly detection |
| **State distribution** | `GROUP BY state` | Pipeline health at a glance |
| **Send success rate** | `SUM(send_success) / COUNT(*)` | Delivery reliability |
| **Failed sends** | `WHERE send_success = 0 ORDER BY created_at DESC` | Immediate action items |
| **Intent distribution** | `GROUP BY ai_intent` | What are users asking for? |
| **Token usage** | `SUM(ai_tokens_in), SUM(ai_tokens_out)` | Cost tracking |

### 5.2 Implementation Pattern

Compute aggregations in SQL, not in application code:

```javascript
async function getObservability(db) {
  const [sendStats, stateDistribution, messagesByDay] = await db.batch([
    db.prepare(`
      SELECT COUNT(*) as total,
             SUM(CASE WHEN send_success = 1 THEN 1 ELSE 0 END) as success
      FROM messages WHERE direction = 'outbound'
    `),
    db.prepare(`SELECT state, COUNT(*) as count FROM conversations GROUP BY state`),
    db.prepare(`
      SELECT DATE(created_at) as day, direction, COUNT(*) as count
      FROM messages GROUP BY day, direction ORDER BY day DESC LIMIT 60
    `),
  ]);
  return { sendStats, stateDistribution, messagesByDay };
}
```

**Lesson:** Batch multiple queries into a single round-trip. D1 and most databases support this. Don't make 6 sequential queries when 1 batch call works.

### 5.3 Timezone Handling

**Do not hardcode timezone offsets in SQL:**

```sql
-- Bad: Hardcoded CT offset (breaks during DST)
DATE(created_at, '-6 hours')

-- Better: Store UTC, convert in the frontend
DATE(created_at)
```

Store all timestamps as UTC ISO 8601. Convert to local time in the frontend using `Intl.DateTimeFormat` or `date-fns-tz`. Hardcoded offsets break twice a year at DST transitions.

---

## 6. Deployment & Caching

### 6.1 Static Asset Strategy

Use content-hashed filenames for immutable caching:

```
dashboard/assets/index-CB56JrlB.css  → Cache: 1 year, immutable
dashboard/assets/index-ObACJQUB.js   → Cache: 1 year, immutable
dashboard/index.html                  → Cache: no-cache (always revalidate)
```

**Pattern:**

```javascript
const isHashed = /[-\.][a-f0-9]{8,}\./.test(filePath);
const cacheControl = isHashed
  ? "public, max-age=31536000, immutable"
  : "no-cache";
```

Vite (and most bundlers) add content hashes automatically. Your deploy script just needs to set the right `Cache-Control` headers.

### 6.2 Deploy Pipeline

Minimum viable deploy script:

```bash
#!/bin/bash
set -euo pipefail

echo "=== Building ==="
cd dashboard && npm run build && cd ..

echo "=== Uploading assets ==="
for file in dashboard/dist/**/*; do
  # Upload to R2/S3/CloudFront with correct MIME type
  upload_asset "$file"
done

echo "=== Deploying API ==="
deploy_worker  # or: cdk deploy, or: serverless deploy

echo "=== Verifying ==="
curl -sf https://your-dashboard.com/api/health || exit 1
echo "Deploy verified."
```

**Lesson from Hermes:** The deploy script didn't have a post-deploy health check. We added one after a deploy broke the API but the static assets loaded fine — the dashboard appeared to work but every API call 500'd. Always verify the API endpoint, not just that the page loads.

### 6.3 MIME Type Mapping

When uploading static assets to object storage, set MIME types explicitly. Don't rely on auto-detection — it gets `.mjs` and `.woff2` wrong.

```bash
case "$ext" in
  js|mjs)  mime="application/javascript; charset=utf-8" ;;
  css)     mime="text/css; charset=utf-8" ;;
  html)    mime="text/html; charset=utf-8" ;;
  json)    mime="application/json" ;;
  svg)     mime="image/svg+xml" ;;
  woff2)   mime="font/woff2" ;;
  png)     mime="image/png" ;;
  *)       mime="application/octet-stream" ;;
esac
```

---

## 7. Database Patterns

### 7.1 Soft Deletes

Use soft deletes for any data that might need to be recovered or audited:

```sql
UPDATE knowledge_base SET active = 0, updated_at = ? WHERE id = ?
```

**Always filter:** `WHERE active = 1` in all read queries. Missing this filter once is an instant data leak.

### 7.2 Cascading Hard Deletes (When Needed)

When you do need hard deletes (e.g., GDPR erasure), use batch operations:

```javascript
await db.batch([
  db.prepare("DELETE FROM ratings WHERE conversation_id = ?").bind(id),
  db.prepare("DELETE FROM labels WHERE conversation_id = ?").bind(id),
  db.prepare("DELETE FROM messages WHERE conversation_id = ?").bind(id),
  db.prepare("DELETE FROM conversations WHERE id = ?").bind(id),
]);
```

Order matters: delete child records before parent records to avoid foreign key violations.

### 7.3 Labels/Tags Pattern

Use a junction table, not a comma-separated column:

```sql
CREATE TABLE conversation_labels (
  conversation_id INTEGER,
  label TEXT,
  created_at TEXT,
  PRIMARY KEY (conversation_id, label)
);
```

**Pitfall from Hermes:** `GROUP_CONCAT(label)` returns a comma-separated string, not an array. The frontend has to `split(",")` it. This is fragile — if a label ever contains a comma, it breaks. Consider returning labels as a separate query or using JSON aggregation if your DB supports it.

---

## 8. Lessons Learned (The Hard Way)

### 8.1 Cloudflare Workers Specifics

| Lesson | Detail |
|--------|--------|
| **50 subrequest limit** | Free plan allows 50 external `fetch()` calls per invocation. D1 bindings don't count. Batch your SQS sends. |
| **`ctx.waitUntil()` swallows errors** | Rejected promises in `waitUntil` are silently discarded. Always wrap in try/catch with console.error. |
| **Cron errors are invisible** | Scheduled handlers have no HTTP response to surface errors. Use `wrangler dev --remote` + curl to reproduce cron behavior with visible errors. |

### 8.2 AWS Lambda + SES

| Lesson | Detail |
|--------|--------|
| **SES sandbox limits** | New accounts start in sandbox mode — can only send to verified addresses. Production access requires unsubscribe support (List-Unsubscribe header + keyword detection). |
| **HMAC secrets in SQS payloads** | If Worker sends a callback secret in the SQS payload, Lambda can use it directly. Don't create a second secret retrieval path if one already exists. |
| **Idempotency on SQS** | SQS can deliver the same message twice. Always check for duplicate `sqsMessageId` before processing. |

### 8.3 General Dashboard Pitfalls

| Pitfall | Fix |
|---------|-----|
| **Showing UI then disabling it** | Don't render the page at all if the user lacks permission. |
| **No post-deploy verification** | Always curl a health endpoint after deploy. Static assets loading doesn't mean the API works. |
| **Hardcoded timezone offsets** | Store UTC, convert in frontend. Offsets break at DST. |
| **Offset pagination** | Use cursor-based (timestamp/ID). Offsets break under concurrent writes. |
| **`confirm()` dialogs** | Use toast notifications with undo. Dialogs block the entire UI and frustrate power users. |
| **No structured error codes** | Add `code` field to error responses from day one. "Not found" vs "forbidden" matters to the frontend. |
| **Retry without backoff** | Exponential backoff on network errors. Never retry auth failures. |
| **Stale viewer tokens** | Auto-purge expired tokens. Stale tokens are a compliance risk. |

### 8.4 React + TypeScript Specifics

| Pitfall | Fix |
|---------|-----|
| **JSON parse on error responses** | A 502 from a proxy returns HTML. Always `.catch()` the `.json()` call. |
| **`refetchOnWindowFocus: true` (default)** | Hammers your API when users alt-tab. Disable for dashboards. |
| **No loading states** | Always handle `isLoading` in React Query. A blank page looks broken. |
| **Prop drilling auth role** | Use a context provider. Auth role is needed everywhere. |

---

## 9. Security Checklist

Before shipping any operational dashboard:

- [ ] Auth check before every protected route (not just most of them)
- [ ] HMAC or signed tokens for any public-facing endpoint (unsubscribe, callbacks)
- [ ] Timing-safe comparison for all token/signature verification
- [ ] CORS headers set correctly (or not set at all if same-origin)
- [ ] `HttpOnly`, `Secure`, `SameSite=Lax` on session cookies
- [ ] PII masking for restricted roles — tested with real data, not just unit tests
- [ ] Rate limiting on auth endpoints (login, token generation)
- [ ] No secrets in frontend bundles (use environment variables server-side)
- [ ] `Content-Security-Policy` headers if serving inline HTML

---

## 10. Quick-Start Checklist for New Dashboards

When spinning up a new operational dashboard:

1. **Define roles** — Who needs access? What can each role see/do?
2. **Choose auth** — API key for scripts, OAuth for humans, viewer tokens for sharing
3. **Choose frontend** — Inline HTML if < 10 pages, React SPA otherwise
4. **Design the API** — RESTful resources, JSON errors with codes, cursor pagination
5. **Build observability first** — Volume trends, success rates, failed operations
6. **Set up deployment** — Build → upload assets → deploy API → health check
7. **Add viewer masking** — PII redaction at API layer, not storage layer
8. **Add structured logging** — Every operation logs enough to reconstruct what happened
9. **Test with restricted roles** — Log in as viewer and verify you can't see anything you shouldn't
10. **Post-deploy verification** — Automated curl after every deploy

---

*Derived from production experience with Hermes (2024-2026). Updated as new patterns emerge.*
