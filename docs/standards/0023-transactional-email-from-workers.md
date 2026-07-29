# Transactional Email From Workers

How a Cloudflare Worker sends mail, and how to pick the transport before you
build against the wrong one. Derived from production experience across fleet
projects, one of which shipped this pattern months ago and one of which spent
an evening blocked on the alternative before rediscovering the same answer.

The expensive mistake this standard prevents: choosing a transport by which
one appears first in the platform documentation, discovering its limit only
after the pipeline is built, and reading a product-entitlement refusal as a
credential bug.

---

## 1. The three transports

| Transport | Reaches arbitrary recipients | Plan floor | Setup |
|---|---|---|---|
| **Email Routing `send_email` binding** | **No** — only addresses verified as destinations on your own account | Free | Binding in `wrangler.jsonc`, destination verified once |
| **Cloudflare Email Sending** | Yes | **Workers Paid** (monthly floor before the first message) | Dashboard-only domain onboarding; API refuses until done |
| **SES over HTTPS from the Worker** | Yes | Free (per-message pricing only) | Domain identity + DKIM records, one IAM user |

### The limit that surprises people

The `send_email` binding is free and already present in most fleet Workers,
so it becomes the default by inertia. It cannot mail a user. It delivers only
to addresses that have been verified as destinations on your own Cloudflare
account, which is exactly right for operator alerts and structurally unable to
notify a customer. This is a property of the product, not a configuration you
can widen.

Build operator alerting on the binding. The moment a requirement says "mail
the person who signed up," the binding is out of scope and you need one of the
other two.

### The refusal that looks like a credential bug

Cloudflare Email Sending returns `2036 Unauthorized` on every
`/accounts/{id}/email/sending/*` endpoint until the domain has been onboarded
through the dashboard. The API cannot perform its own enablement, so the error
you get while trying to enable it is indistinguishable in shape from a scope
problem.

Diagnostic rule: if two or more **independent credentials** are refused on the
same product family, stop investigating tokens. That is account or product
state, and no amount of scope-widening will move it. Widening a token in
response to this is how a fleet ends up with over-scoped credentials that fix
nothing.

---

## 2. Economics

The comparison that matters is the floor, not the per-message rate, because
transactional volumes for small services are trivial either way.

- **Cloudflare Email Sending** requires the Workers Paid plan. If the project
  is otherwise happy on Free, the true cost is the full monthly plan price
  multiplied by twelve, purchased for the email feature alone.
- **SES** has no monthly floor and bills per thousand messages. Production
  access must be requested once per account (out of the sandbox), after which
  the account carries a 24-hour send quota that is orders of magnitude above
  what a notification feature consumes.

If the account is already on Workers Paid for other reasons, Email Sending
becomes the cheaper option and removes the AWS coupling. Re-evaluate then;
the adapter in Section 5 makes that a configuration change.

**Check the real quota before assuming it is scarce.** Recollection of quota
pressure is often a memory of the SES sandbox limit, or of a different
account. Verify:

```bash
aws sesv2 get-account --region us-east-1
```

Read `SendQuota.Max24HourSend` against `SentLast24Hours`, and confirm
`ProductionAccessEnabled` is true.

---

## 3. The SES-over-HTTPS pattern

SES is an HTTPS API, and a Worker can call any HTTPS API. There is no SMTP
server, no Lambda in the outbound path, and no AWS SDK.

**Never install the AWS SDK in a Worker.** It is large, assumes Node built-ins,
and exists to do what forty lines of signed `fetch` do here. Use `aws4fetch`,
which implements SigV4 and nothing else.

```js
export async function sendViaSES(env, from, to, subject, body) {
  const { AwsClient } = await import("aws4fetch");
  const aws = new AwsClient({
    accessKeyId: env.AWS_ACCESS_KEY_ID,
    secretAccessKey: env.AWS_SECRET_ACCESS_KEY,
    region: env.AWS_REGION || "us-east-1",
    service: "ses",
  });

  const params = new URLSearchParams({
    Action: "SendEmail",
    Source: from,
    "Destination.ToAddresses.member.1": to,
    "Message.Subject.Data": subject,
    "Message.Body.Text.Data": body,
  });

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await aws.fetch(
      `https://email.${env.AWS_REGION || "us-east-1"}.amazonaws.com/`,
      {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: params.toString(),
        signal: controller.signal,
      },
    );
    if (!res.ok) throw new Error(`SES ${res.status}: ${await res.text()}`);
    return { ok: true };
  } finally {
    clearTimeout(timeout);
  }
}
```

Points that are load-bearing:

- **Always set a timeout.** A Worker request that hangs on a third-party API
  burns the invocation. `AbortController` with `clearTimeout` in `finally`.
- **Credentials come from Worker secrets**, never from a config file and never
  from process arguments. `npx wrangler secret put AWS_ACCESS_KEY_ID` and the
  same for the secret key. The operator types the values; they are never
  echoed into a transcript or a command line.
- **Import `aws4fetch` dynamically** (`await import`) when the sender is on a
  cold path, so the cost is not paid by requests that never send mail.

### Attachments and non-ASCII bodies

For attachments or anything beyond a plain-text body, build a MIME message and
use `SendRawEmail` with the message base64-encoded. `btoa()` handles Latin-1
only, which silently corrupts em-dashes and smart quotes, so encode UTF-8
first:

```js
const raw = btoa(unescape(encodeURIComponent(mime)));
```

This is the single most common defect in Worker-based senders. Any drafting
step that produces typographic punctuation will hit it.

---

## 4. Sender identity

Outbound sending identity is **independent of inbound routing**. A domain can
keep receiving mail through Email Routing while sending through SES; the two
use different DNS records and neither disturbs the other. Onboarding a sending
identity does not put inbound mail at risk.

Setup, once per sending domain:

1. Create the domain identity with Easy DKIM:
   ```bash
   aws sesv2 create-email-identity --email-identity mail.example.com --region us-east-1
   ```
2. Write the three returned CNAME records into DNS. If DNS is on Cloudflare,
   an agent can do this end-to-end through the API; no dashboard step exists in
   this path.
3. Wait for verification (minutes when DNS is authoritative and fast).
4. Confirm a DMARC policy exists on the domain. DKIM alignment from step 1
   satisfies it.

**Prefer a subdomain** (`mail.example.com`, `notifications.example.com`) over
the root. Sending reputation is then scoped to the application, and a
deliverability problem in one service cannot damage the root domain's
reputation for everything else.

### IAM scope

One IAM user per sending application, with exactly one permission:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": "ses:SendEmail",
    "Resource": "*"
  }]
}
```

Add `ses:SendRawEmail` only if attachments are in scope. Nothing else, ever:
these keys live in a Worker and are therefore reachable by anyone who can
deploy that Worker.

---

## 5. Transport adapter discipline

The transport must be swappable by configuration, because the correct choice
changes with plan tier and product availability. Both times the fleet faced
this decision, the answer moved after the pipeline was designed.

Structure the sender as a single function the rest of the codebase calls, with
per-transport implementations behind it:

```
send(env, message)          <- everything else calls only this
  ├─ operator path  -> send_email binding      (free, own addresses only)
  └─ player path    -> SES over HTTPS          (arbitrary recipients)
```

Rules that keep the seam honest:

- **The alert path must not share the failing transport.** When the primary
  send fails, the alert reporting that failure has to travel a different road,
  or the failure is silent precisely when it matters.
- **Recheck consent at send time, not only at enqueue time.** A durable outbox
  means arbitrary delay between the two, and a player may have revoked in the
  interval.
- **Log the provider's error code, not just the message.** Sender-not-verified
  and quota-exceeded demand completely different responses, and the message
  text is not stable enough to branch on.

### The outbox

If mail is queued durably before a transport exists, the queue is doing its
job: the consent decisions and the dedupe keys are captured at the moment the
event happened, which cannot be reconstructed later.

But **queued is not sent**, and the gap must be visible. Surface the unsent
count on an operational dashboard from the day the queue is created. A queue
nobody can see is indistinguishable from a feature that works.

When the transport finally lands, draining is a **decision, not a loop**.
Stale notifications are worse than none: nobody wants to learn on Friday that
someone passed them on a leaderboard on Monday. Classify by type before
sending anything, and be willing to mark rows sent without sending them.

---

## 6. Anti-patterns

| Anti-pattern | Why it fails |
|---|---|
| AWS SDK inside a Worker | Bundle size and Node built-in assumptions; `aws4fetch` does the only part you need |
| Credentials in argv or a committed config | Process arguments are readable by same-user processes; use Worker secrets |
| Widening a token in response to `2036` | It is product state, not scope; widening leaves an over-scoped credential and an unfixed problem |
| One transport for both alerts and user mail | The alert about a transport failure cannot travel the failed transport |
| Root domain as sending identity | Couples application reputation to the whole domain |
| Draining a stale outbox unconditionally | Delivers notifications whose moment has passed, which reads as malfunction |
| `btoa()` on a UTF-8 body | Silent corruption of every em-dash and smart quote |

---

## 7. Operator steps, in full

The agent can do everything except the two steps that require human-held
credentials:

1. **Agent:** create the SES domain identity, write DKIM CNAMEs, verify.
2. **Operator:** create the IAM user and read the two key values once.
3. **Operator:** type them into `wrangler secret put AWS_ACCESS_KEY_ID` and
   `wrangler secret put AWS_SECRET_ACCESS_KEY`.
4. **Agent:** implement the adapter, deploy, verify a live send end to end.

Two typed values is the whole human cost. Any design that asks the operator
for more than this has pushed work onto them that the agent could have done.
