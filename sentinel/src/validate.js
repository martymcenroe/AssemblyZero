// PR body validation rules:
// Pass: Closes #N, Fixes #N, Resolves #N (case-insensitive, also cross-repo owner/repo#N)
// Pass: No-Issue: <reason> (requires non-empty reason)
// Fail: empty body, no matching pattern

const NO_ISSUE_PATTERN = /^No-Issue:\s*\S+/im;

/**
 * Extract issue references from a PR body.
 * Returns an array of { owner, repo, number } objects.
 * If owner/repo is omitted, they are null (meaning same-repo).
 * @param {string} body
 * @returns {Array<{ owner: string|null, repo: string|null, number: number }>}
 */
export function extractIssueRefs(body) {
  if (!body) return [];
  const refs = [];
  const refPattern =
    /\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+(?:([\w.-]+)\/([\w.-]+))?#(\d+)/gi;
  let match;
  while ((match = refPattern.exec(body)) !== null) {
    refs.push({
      owner: match[1] || null,
      repo: match[2] || null,
      number: parseInt(match[3], 10),
    });
  }
  return refs;
}

/**
 * Validate a PR body for issue references.
 * @param {string|null} body - The PR body text
 * @returns {{ valid: boolean, reason: string, refs: Array, noIssue: boolean }}
 */
export function validatePRBody(body) {
  if (!body || !body.trim()) {
    return {
      valid: false,
      reason: "PR body is empty. Add `Closes #N` or `No-Issue: <reason>`.",
      refs: [],
      noIssue: false,
    };
  }

  const refs = extractIssueRefs(body);
  if (refs.length > 0) {
    return { valid: true, reason: "Issue reference found.", refs, noIssue: false };
  }

  if (NO_ISSUE_PATTERN.test(body)) {
    return {
      valid: true,
      reason: "No-Issue exemption with reason.",
      refs: [],
      noIssue: true,
    };
  }

  return {
    valid: false,
    reason:
      "No issue reference found. Add `Closes #N`, `Fixes #N`, `Resolves #N`, or `No-Issue: <reason>` to the PR body.",
    refs: [],
    noIssue: false,
  };
}
