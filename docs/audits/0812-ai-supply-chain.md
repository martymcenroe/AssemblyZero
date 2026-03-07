# 0819 - Audit: AI Supply Chain

## 1. Purpose

Comprehensive AI supply chain audit covering model provenance, training data governance, dependency security, and third-party AI service assessment. Based on OWASP LLM03:2025 Supply Chain guidance and emerging AIBOM (AI Bill of Materials) standards.

**Aletheia Context:**
- Uses AWS Bedrock for Claude model access (not self-hosted)
- Wikipedia-sourced denylist for content filtering
- Python/JavaScript dependencies for Lambda and extension
- Claude Code for development (agentic AI dependency)

---

## 2. AI Supply Chain Components

### 2.1 Supply Chain Inventory

| Component Type | Component | Provider | Version | Risk Level |
|----------------|-----------|----------|---------|------------|
| **Foundation Model** | Claude Haiku | Anthropic via Bedrock | claude-3-haiku-20240307-v1:0 | Medium |
| **Foundation Model** | Claude Sonnet | Anthropic via Bedrock | claude-3-sonnet (fallback) | Medium |
| **Data Source** | Wikipedia Categories | Wikimedia Foundation | Live API | Low |
| **ML Framework** | boto3/botocore | AWS | poetry.lock pinned | Low |
| **Development Agent** | Claude Code | Anthropic | Latest | Medium |

---

## 3. Model Provenance (CRITICAL)

### 3.1 Model Source Verification

| Check | Requirement | Aletheia Status | Status |
|-------|-------------|-----------------|--------|
| Model source documented | Know where model came from | AWS Bedrock (Anthropic) | |
| Model version pinned | Specific version in use | Hardcoded in Lambda | |
| Model signing verified | Cryptographic verification | AWS manages | |
| No unauthorized models | Only approved models used | Bedrock allowlist | |

### 3.2 Model Provenance Chain

```
Anthropic (trains Claude)
    ↓
AWS Bedrock (hosts model)
    ↓
Aletheia Lambda (calls API)
    ↓
User (receives output)
```

**Verification:**
```bash
# Check model ID in Lambda code
🤖 grep -n "model" src/lambda_function.py | grep -i claude
🤖 grep -n "model" src/guardrails/semantic.py | grep -i claude
```

### 3.3 Model Trust Assessment

| Question | Answer | Evidence |
|----------|--------|----------|
| Is provider reputable? | Yes | Anthropic - leading AI safety company |
| Is hosting secure? | Yes | AWS SOC 2, ISO 27001 |
| Can we verify model hasn't been tampered? | Partial | AWS guarantees, no direct verification |
| Do we have model card/documentation? | Yes | Anthropic publishes model cards |

---

## 4. Training Data Governance

### 4.1 Foundation Model Training Data

| Check | Requirement | Status |
|-------|-------------|--------|
| Training data documented | Anthropic publishes summaries | ✅ Public |
| Copyright compliance | Provider responsibility | Anthropic handles |
| Bias assessment | Provider responsibility | Anthropic's Constitutional AI |
| Data poisoning controls | Provider responsibility | Anthropic security |

**Note:** Aletheia uses pre-trained models. We do NOT fine-tune or provide training data. Training data governance is Anthropic's responsibility.

### 4.2 Aletheia-Controlled Data Sources

| Data Source | Purpose | Governance | Status |
|-------------|---------|------------|--------|
| Wikipedia Categories | Denylist terms | Public domain, documented | |
| User selected text | Inference input | TTL 30 days, ephemeral | |
| Seed terms | Denylist bootstrap | Documented in LLD 1121 | |

### 4.3 Data Provenance Verification

```bash
# Verify denylist source documentation
🤖 head -20 tools/fetch_denylist.py
🤖 grep -n "Category:" tools/fetch_denylist.py

# Check for undocumented data sources
🤖 grep -rn "requests.get\|urllib\|fetch" src/ tools/
```

---

## 5. Dependency Security

### 5.1 Python Dependencies (Lambda)

| Check | Tool | Command | Status |
|-------|------|---------|--------|
| Vulnerability scan | pip-audit | `pip-audit` | |
| Outdated packages | poetry | `poetry show --outdated` | |
| Lock file current | poetry | `poetry.lock` committed | |
| Known CVEs | Dependabot | GitHub alerts | |

```bash
# Run dependency audit
🤖 cd /c/Users/mcwiz/Projects/Aletheia
🤖 poetry show --outdated
🤖 pip-audit 2>/dev/null || echo "pip-audit not installed"
```

### 5.2 JavaScript Dependencies (Extension)

| Check | Tool | Command | Status |
|-------|------|---------|--------|
| Vulnerability scan | npm audit | `npm audit` | |
| Outdated packages | npm | `npm outdated` | |
| Lock file current | npm | `package-lock.json` committed | |
| Known CVEs | Dependabot | GitHub alerts | |

```bash
# Run dependency audit
🤖 npm audit
🤖 npm outdated
```

### 5.3 ML-Specific Dependencies

| Package | Purpose | Risk | Mitigation |
|---------|---------|------|------------|
| boto3 | AWS SDK (Bedrock) | Low | Pin version |
| botocore | AWS core | Low | Pin version |
| requests | HTTP client | Low | Pin version |
| beautifulsoup4 | HTML parsing (denylist) | Low | Pin version |

---

## 6. Third-Party AI Services

### 6.1 AWS Bedrock Assessment

| Check | Requirement | Evidence | Status |
|-------|-------------|----------|--------|
| Security certifications | SOC 2, ISO 27001 | AWS compliance page | |
| Data isolation | Per-account isolation | Bedrock architecture | |
| No training on prompts | Data not used for training | Bedrock TOS | |
| Incident notification | Breach notification | AWS support agreement | |
| SLA availability | Uptime guarantees | Bedrock SLA | |

### 6.2 Anthropic Assessment

| Check | Requirement | Evidence | Status |
|-------|-------------|----------|--------|
| Model safety practices | Documented approach | Constitutional AI papers | |
| Responsible AI policy | Published guidelines | anthropic.com/responsible-ai | |
| Model updates communicated | Versioning and changelog | Bedrock model versions | |
| Security practices | Industry standard | SOC 2 (via AWS) | |

### 6.3 Wikipedia API Assessment

| Check | Requirement | Evidence | Status |
|-------|-------------|----------|--------|
| Data authenticity | Official API | api.wikimedia.org | |
| Rate limiting respected | Polite access | 1s delay in fetch_denylist.py | |
| Terms compliance | API usage terms | Wikimedia TOS review | |
| Data integrity | No tampering in transit | HTTPS | |

---

## 7. AIBOM (AI Bill of Materials)

### 7.1 Aletheia AIBOM

Following SPDX 3.0 AI Profile concepts:

```yaml
# Aletheia AI Bill of Materials
aibom_version: "1.0"
generated: "2026-01-06"
organization: "martymcenroe"
project: "Aletheia"

models:
  - name: "Claude 3 Haiku"
    provider: "Anthropic"
    hosting: "AWS Bedrock"
    model_id: "claude-3-haiku-20240307-v1:0"
    purpose: "Semantic guardrail classification"
    risk_level: "low"

  - name: "Claude 3 Sonnet"
    provider: "Anthropic"
    hosting: "AWS Bedrock"
    model_id: "claude-3-sonnet-*"
    purpose: "Etymology generation (fallback)"
    risk_level: "low"

datasets:
  - name: "Wikipedia Profanity Categories"
    source: "Wikimedia Foundation"
    collection_method: "API fetch"
    purpose: "Denylist term source"
    license: "CC BY-SA"

  - name: "Seed Terms"
    source: "Manual curation"
    collection_method: "Manual entry"
    purpose: "Denylist bootstrap"
    license: "MIT"

data_flows:
  - input: "User selected text"
    processing: "Lambda (in-memory)"
    output: "Etymology analysis"
    retention: "30 days (DynamoDB TTL)"
    pii_handling: "Not logged"
```

### 7.2 AIBOM Maintenance

| Task | Frequency | Owner |
|------|-----------|-------|
| Update model versions | On change | Developer |
| Review data sources | Quarterly | Developer |
| Verify dependencies | Weekly (0816) | Automated |
| Full AIBOM refresh | Quarterly | This audit |

---

## 8. Supply Chain Threats (OWASP LLM03:2025)

### 8.1 Threat Checklist

| Threat | Applicability | Mitigation | Status |
|--------|---------------|------------|--------|
| **Malicious model weights** | Low (Bedrock managed) | AWS verification | |
| **Backdoor in pre-trained model** | Low (Bedrock managed) | Trust Anthropic | |
| **Poisoned training data** | Low (Bedrock managed) | Anthropic responsibility | |
| **Compromised fine-tuning** | N/A (no fine-tuning) | Not applicable | |
| **Malicious LoRA adapter** | N/A (no adapters) | Not applicable | |
| **Dependency vulnerability** | Medium | Dependabot, audits | |
| **Compromised data source** | Low | Wikipedia official API | |
| **Supply chain impersonation** | Low | Official endpoints only | |

### 8.2 Detection Controls

| Control | Implementation | Status |
|---------|----------------|--------|
| Dependency scanning | Dependabot enabled | |
| Model version verification | Hardcoded model IDs | |
| API endpoint verification | Official AWS endpoints | |
| Anomaly detection | CloudWatch monitoring | |

---

## 9. Audit Procedure

### 9.1 Quarterly Supply Chain Review

1. **Model Inventory Update**
   - Verify all models in use are documented
   - Check for model version changes
   - Review Anthropic changelog for updates

2. **Dependency Audit**
   - Run `poetry show --outdated`
   - Run `npm audit`
   - Review Dependabot alerts
   - Update dependencies if safe (run 0816 first)

3. **Third-Party Assessment**
   - Check AWS Bedrock status/announcements
   - Review Anthropic policy changes
   - Verify Wikipedia API terms

4. **AIBOM Refresh**
   - Update model versions
   - Document any new data sources
   - Verify data flow accuracy

### 9.2 Event-Triggered Reviews

| Event | Action |
|-------|--------|
| New model version available | Assess, plan upgrade |
| Dependency CVE announced | Run 0816 immediately |
| Anthropic policy change | Review compliance |
| New data source added | Document in AIBOM |

---

## 10. Audit Record

| Date | Auditor | Findings Summary | Issues Created |
|------|---------|------------------|----------------|
| 2026-01-10 | Claude Opus 4.5 | PASS: Model ID pinned (HAIKU_MODEL_ID in etymologist.py, env override available), provenance chain documented (Anthropic→Bedrock→Lambda→User), dependencies locked in poetry.lock, denylist sourced from Wikipedia, AWS manages model signing | None |

---

## 11. References

### Standards and Guidance
- [OWASP LLM03:2025 Supply Chain](https://genai.owasp.org/llmrisk/llm032025-supply-chain/)
- [SPDX 3.0 AI Profile](https://spdx.dev/)
- [NIST AI RMF - GOVERN Function](https://www.nist.gov/itl/ai-risk-management-framework)
- [Coalition for Secure AI (CoSAI)](https://www.coalitionforsecureai.org/)

### AWS/Anthropic
- [AWS Bedrock Security](https://docs.aws.amazon.com/bedrock/latest/userguide/security.html)
- [Anthropic Responsible AI](https://www.anthropic.com/responsible-ai)

### Internal
- docs/0816-audit-dependabot-prs.md - Dependency PR management
- docs/0809-audit-security.md §5 - Extension supply chain
- docs/1121-wikipedia-denylist.md - Denylist data source LLD

---

## 12. History

| Date | Change |
|------|--------|
| 2026-01-06 | Created. OWASP LLM03:2025 alignment for AI supply chain audit. |
