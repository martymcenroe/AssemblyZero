// PR body validation rules:
// Pass: Closes #N, Fixes #N, Resolves #N (case-insensitive, also cross-repo owner/repo#N)
// Pass: No-Issue: <reason> (requires non-empty reason)
// Fail: empty body, no matching pattern

const ISSUE_REF_PATTERN =
  /\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+(?:[\w.-]+\/[\w.-]+)?#\d+/i;

const NO_ISSUE_PATTERN = /No-Issue:\s*\S+/i;

/**
 * Validate a PR body for issue references.
 * @param {string|null} body - The PR body text
 * @returns {{ valid: boolean, reason: string }}
 */
export function validatePRBody(body) {
  if (!body || !body.trim()) {
    return {
      valid: false,
      reason: "PR body is empty. Add `Closes #N` or `No-Issue: <reason>`.",
    };
  }

  if (ISSUE_REF_PATTERN.test(body)) {
    return { valid: true, reason: "Issue reference found." };
  }

  if (NO_ISSUE_PATTERN.test(body)) {
    return { valid: true, reason: "No-Issue exemption with reason." };
  }

  return {
    valid: false,
    reason:
      "No issue reference found. Add `Closes #N`, `Fixes #N`, `Resolves #N`, or `No-Issue: <reason>` to the PR body.",
  };
}
