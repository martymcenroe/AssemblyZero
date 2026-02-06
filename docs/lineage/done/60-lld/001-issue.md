---
repo: martymcenroe/AgentOS
issue: 60
url: https://github.com/martymcenroe/AgentOS/issues/60
fetched: 2026-02-04T14:46:45.069832Z
---

# Issue #60: Track CVE-2026-0994: protobuf JSON recursion depth bypass

## CVE-2026-0994: protobuf JSON Recursion Depth Bypass

### Status: PATCH AVAILABLE - Ready to Upgrade

| Field | Value |
|-------|-------|
| **CVE** | [CVE-2026-0994](https://nvd.nist.gov/vuln/detail/CVE-2026-0994) |
| **Severity** | HIGH (CVSS 8.2) |
| **Type** | Denial of Service (DoS) |
| **Current Version** | 5.29.5 (**AFFECTED**) |
| **Patched Version** | **6.33.5** (available on PyPI) |
| **Published** | 2026-01-23 |

### Vulnerability Details

A denial-of-service vulnerability in `google.protobuf.json_format.ParseDict()` allows attackers to bypass the `max_recursion_depth` limit using deeply nested `Any` messages, causing `RecursionError` and crashing the Python process.

### How It Enters AgentOS

Transitive dependency via Google API packages for Gemini integration:
- google-api-core
- googleapis-common-protos
- grpcio-status
- proto-plus

### Risk Assessment: MEDIUM-HIGH

| Factor | Assessment |
|--------|------------|
| Exploitability | Requires attacker to control JSON being parsed |
| AgentOS exposure | We use protobuf for outbound Gemini API calls, not parsing untrusted input |
| Impact if exploited | DoS (crash), not data breach or RCE |
| Upgrade risk | **Major version jump (5.x → 6.x)** - potential breaking changes |

### Recommendation: Upgrade with Full Regression

**Protocol (Dependabot-style):**

```bash
# 1. Create worktree
git worktree add ../AgentOS-60 -b 60-protobuf-cve-patch
cd ../AgentOS-60
git push -u origin HEAD

# 2. Upgrade protobuf
poetry add protobuf@^6.33.5

# 3. Run full regression
poetry run pytest tests/ -v

# 4. If tests pass, create PR
# If tests fail, document breaking changes
```

### Breaking Change Risk

The 5.x → 6.x upgrade may affect:
- Message serialization format
- Field access patterns
- API compatibility with google-api-core, grpcio-status

**Mitigation:** Run full regression. If failures occur, they will likely be in Gemini integration tests.

### Acceptance Criteria

- [ ] Upgrade protobuf to ≥6.33.5
- [ ] Full regression tests pass
- [ ] Document any breaking changes encountered
- [ ] Verify Gemini API calls still work (run workflow with --mock or live test)

### References

- [NVD CVE-2026-0994](https://nvd.nist.gov/vuln/detail/CVE-2026-0994)
- [GitHub Advisory GHSA-7gcm-g887-7qv7](https://github.com/advisories/GHSA-7gcm-g887-7qv7)
- [GitLab Advisory](https://advisories.gitlab.com/pkg/pypi/protobuf/CVE-2026-0994/)
- [Patch PR #25239](https://github.com/protocolbuffers/protobuf/pull/25239)