# Issue #60: Track CVE-2026-0994: protobuf JSON recursion depth bypass

## Dependabot Alert #1

**Package:** protobuf 5.29.5  
**CVE:** [CVE-2026-0994](https://nvd.nist.gov/vuln/detail/CVE-2026-0994)  
**Severity:** High (CVSS 4.0: 8.2)  
**Type:** Denial of Service (DoS)  
**Patched Version:** None available yet  

## Vulnerability Details

JSON recursion depth bypass in `google.protobuf.json_format.ParseDict()`. An attacker can supply deeply nested `Any` messages to exhaust Python's recursion stack and cause a `RecursionError`.

## How It Enters AgentOS

Transitive dependency via Google API packages:
- google-api-core
- googleapis-common-protos
- grpcio-status
- proto-plus

These are used for Gemini API integration.

## Risk Assessment: LOW

- The vulnerable function parses JSON into protobuf messages
- AgentOS uses protobuf for **outbound** API calls to Gemini, not for parsing untrusted user input
- An attacker would need to control the JSON being parsed to exploit this
- This is a DoS vulnerability, not data breach or RCE

## Action

Monitoring for patch release. Will update protobuf when a fixed version (likely >= 6.33.5) becomes available.

## References

- [Dependabot Alert](https://github.com/martymcenroe/AgentOS/security/dependabot/1)
- [GHSA-7gcm-g887-7qv7](https://github.com/advisories/GHSA-7gcm-g887-7qv7)
- [protobuf issue #25070](https://github.com/protocolbuffers/protobuf/issues/25070)
- [protobuf PR #25239](https://github.com/protocolbuffers/protobuf/pull/25239)