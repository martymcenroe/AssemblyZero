# Issue Review: Adversarial Testing Workflow: Separation of Implementation from Verification

## Identity Confirmation
I am Gemini 3 Pro, acting as Senior Technical Product Manager & Governance Lead.

## Pre-Flight Gate
PASSED

## Review Summary
The issue is comprehensive and highly detailed regarding the UX and technical workflow. The inclusion of offline development strategies (mocked fixtures) and cost analysis is excellent. However, because this feature involves **executing LLM-generated code**, security controls must be stricter than currently defined. Additionally, the data residency status of the external API usage is listed as an open question, which is a blocker.

## Tier 1: BLOCKING Issues

### Security
- [ ] **Insufficient Sandbox Controls:** The issue states "Containerization recommended" and relies on "User confirmation" and "Syntax checking" for safety. Syntax checking does not prevent destructive code (e.g., `shutil.rmtree('/')` is valid syntax).
    - **Requirement:** Change requirements to either:
        1.  **Mandate** containerized execution (Docker/Podman) for all LLM-generated script execution.
        2.  **Mandate** AST-based static analysis to reject dangerous imports/calls (e.g., `os`, `subprocess`, `shutil`) if running on the host machine.
- [ ] **Input Sanitization:** The Verification Script is defined as a `.sh` file. Executing an unparsed shell script from an LLM is extremely high risk.
    - **Requirement:** Explicitly require the orchestrator to inspect the shell script for dangerous commands (e.g., `curl`, `wget` to external IPs, `rm -rf`) before the confirmation prompt is shown.

### Legal
- [ ] **Data Residency Uncertainty:** The "Open Questions" section asks: "Confirm existing Gemini integration covers data residency requirements." This cannot remain an open question in the backlog.
    - **Requirement:** Verify this now. Update the "Legal" or "Requirements" section to explicitly state which API endpoint/region must be used to ensure compliance (e.g., "Must use Enterprise endpoint with Zero Data Retention policy").

### Cost
- [ ] No blocking issues found. Analysis is robust.

### Safety
- [ ] No blocking issues found.

## Tier 2: HIGH PRIORITY Issues

### Quality
- [ ] **Vague AC:** "Import errors are caught before reaching human review" is an outcome, not a testable functional requirement for the tool.
    - **Recommendation:** Refine to: "Orchestrator parses `stderr` from verification script; if `ImportError` or `ModuleNotFoundError` is detected, the workflow halts and returns status `FAILED_IMPORT`."

### Architecture
- [ ] **Environment Isolation:** The requirement "Orchestrator runs verification scripts independently without Claude context" is slightly ambiguous.
    - **Recommendation:** Specify *how* context is stripped. E.g., "Script execution must run with a sanitized environment variable set (clearing `PYTHONPATH`, internal API keys) to prevent accidental dependency on the developer's local environment."

## Tier 3: SUGGESTIONS
- **Taxonomy:** Add `security-critical` label due to the code execution nature.
- **Testing:** Consider adding a "Self-Destruct Test" to the test plan: Feed the orchestrator a script that tries to delete a file, and verify the sandbox/AST-scanner blocks it or the user prompt accurately displays the danger.

## Questions for Orchestrator
1. Does the current project configuration for Gemini allow for "Enterprise/Zero Retention" mode, or is it using the standard consumer API? This determines if we can legally send proprietary code for adversarial analysis.

## Verdict
[ ] **APPROVED** - Ready to enter backlog
[x] **REVISE** - Fix Tier 1/2 issues first
[ ] **DISCUSS** - Needs Orchestrator decision