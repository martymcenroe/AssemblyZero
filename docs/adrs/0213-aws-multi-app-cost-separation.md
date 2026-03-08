# ADR-0213: AWS Multi-App Cost Separation Pattern

**Status:** Accepted
**Date:** 2026-03-07
**Issue:** Aletheia #535
**Related:** Aletheia runbook 10902

## 1. Context

Multiple applications (Aletheia, Hermes) share a single AWS account (`383687041805`). A single budget covered everything, meaning Hermes Bedrock costs could trigger Aletheia's kill switch. IAM roles were shared (`AletheiaHermesPoller` ran on `AletheiaLambdaRole`). Cost Explorer showed one undifferentiated Bedrock bill.

## 2. Decision

Adopt a per-application cost isolation pattern using Application Inference Profiles (AIPs), resource tagging, and scoped budgets.

### Pattern (applies to all apps in the account)

1. **Application Inference Profiles** — every app creates AIPs wrapping the foundation models it uses. AIPs are tagged `Project:<app>`. Bedrock costs route through the AIP and appear under the tag in Cost Explorer.

2. **Resource tagging** — all resources (Lambdas, DynamoDB tables, IAM roles) tagged `Project:<app>`. `Project` is activated as a cost allocation tag.

3. **Separate IAM roles** — no shared roles between apps. Each app's Lambda functions use their own role. Budget actions target only the relevant role.

4. **Per-app budgets** — each app gets a budget filtered by `TagKeyValue: user:Project$<app>`. Budget actions (deny policies) target only that app's IAM role.

5. **Account canary budget** — a single `Account-Monthly-Canary` budget (alert-only, no actions) monitors total account spend as a safety net.

## 3. Consequences

**Positive:**
- Hermes overspend cannot kill Aletheia (and vice versa)
- Cost Explorer shows per-app Bedrock spend after 24h tag propagation
- Budget actions are scoped — only the offending app gets throttled
- New apps follow the same pattern: create AIPs, tag resources, create budget

**Negative:**
- AIP creation adds a provisioning step per model per app
- Tag-based budget filtering has 24h propagation delay on initial setup
- More IAM roles to manage (one per app)

**Neutral:**
- No code changes needed beyond reading model IDs from env vars
- Claude 4.x uses the same Messages API as Claude 3 — AIP migration is transparent

## 4. Implementation Checklist (for new apps)

```
[ ] Create AIPs: aws bedrock create-inference-profile --tags key=Project,value=<app>
[ ] Set Lambda env vars to AIP ARNs
[ ] Tag all resources: Project=<app>
[ ] Create dedicated IAM role (no sharing)
[ ] Create budget: <app>-Monthly-<limit>
[ ] Add budget action targeting the app's IAM role
[ ] Activate cost allocation tag (one-time): aws ce update-cost-allocation-tags-status
[ ] Verify in Cost Explorer after 24h
```
