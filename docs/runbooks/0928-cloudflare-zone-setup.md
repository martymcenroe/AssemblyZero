# 0928 - New Domain: Cloudflare Zone Setup

**Category:** Runbook / Operational Procedure
**Version:** 1.0
**Last Updated:** 2026-04-08

---

## Purpose

Steps for adding a new domain to Cloudflare for use with Workers. All projects deploy to the same Cloudflare account (`4fe1c5e241425c85d0f2c35c69fb45b8`, mcwizard1@gmail.com).

---

## Prerequisites

- Cloudflare account access (mcwizard1@gmail.com)
- Domain purchased from a registrar (Namecheap, etc.)
- The domain's TLD must be supported by Cloudflare (most are; `.study` is not)

---

## Steps

### 1. Add zone in Cloudflare

1. Go to https://dash.cloudflare.com/
2. Click **Add a site**
3. Enter the domain (e.g., `sextant.ceo`)
4. Select the **Free** plan
5. Cloudflare will scan existing DNS records — review and confirm
6. Cloudflare assigns two nameservers (e.g., `ada.ns.cloudflare.com`, `bob.ns.cloudflare.com`)

### 2. Change nameservers at registrar

**Namecheap:**
1. Go to https://www.namecheap.com/ > Domain List > Manage
2. Under **Nameservers**, switch from "Namecheap BasicDNS" to **Custom DNS**
3. Enter the two Cloudflare nameservers from step 1
4. Save

**Other registrars:** Find the DNS/Nameserver settings and replace with Cloudflare's nameservers.

### 3. Verify propagation

Nameserver changes can take 1-24 hours. Check status:

```bash
# Check nameservers
dig NS sextant.ceo +short

# Or use Cloudflare's dashboard — it shows "Active" when propagated
```

Cloudflare also sends an email when the zone becomes active.

### 4. Configure Worker route (in wrangler.toml)

```toml
[[routes]]
pattern = "subdomain.yourdomain.com"
custom_domain = true
```

Then `wrangler deploy` will automatically create the DNS record and route.

### 5. Verify HTTPS

Cloudflare provides free SSL. After deploying the Worker:

```bash
curl -I https://subdomain.yourdomain.com
# Should return HTTP/2 200 with Cloudflare headers
```

---

## Notes

- `.ceo`, `.dev`, `.com`, `.io` — all supported by Cloudflare
- `.study` — NOT supported by Cloudflare (discovered during Aletheia setup)
- Free plan is sufficient for Workers + D1 + custom domains
- Each domain is a separate "zone" in Cloudflare, but all under the same account

---

## Related Documents

- [0901 - New Project Setup](0901-new-project-setup.md) — Script reference
- [0927 - New Repo: Human Steps Checklist](0927-new-repo-human-checklist.md) — Full new-repo workflow

---

## History

| Date | Change |
|------|--------|
| 2026-04-08 | v1.0: Initial runbook. Documented from Sextant domain setup experience (#883). |
