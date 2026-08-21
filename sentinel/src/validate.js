// PR body validation rules:
// Pass: Closes #N (case-insensitive, also cross-repo owner/repo#N)
// Pass: No-Issue: <reason> (requires non-empty reason)
// Fail: empty body, no matching pattern

const NO_ISSUE_PATTERN = /^No-Issue:\s*\S+/im;

// GitHub auto-closes on THREE verb families. This validator has only ever
// looked at one of them:
//
//   close / closes / closed        <- extracted below, and policed
//   fix / fixes / fixed            <- GitHub honours it, we never looked
//   resolve / resolves / resolved  <- GitHub honours it, we never looked
//
// The two we ignored fail silently. A PR body whose prose named an issue with
// one of those verbs closed that issue on merge, in a PR that said in plain
// words it was NOT addressing it and had pinned the defect as a passing test.
// Nothing warned; it was found days later by a handoff cross-check.
//
// The house standard mandates `Closes #N` in commit, title and body, so the
// fix/resolve forms are never a sanctioned way to close anything. Every
// occurrence is either a mistake or prose about to become one, which is why
// this blocks rather than warns.
const SILENT_CLOSE_PATTERN =
  /\b(?:fix(?:es|ed)?|resolve[sd]?)\s+(?:([\w.-]+)\/([\w.-]+))?#(\d+)/gi;

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
    /\b(?:close[sd]?)\s+(?:([\w.-]+)\/([\w.-]+))?#(\d+)/gi;
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
 * Extract references written with an auto-close verb this check has
 * historically ignored but GitHub acts on.
 *
 * Same shape as extractIssueRefs. Separate function because the two sets mean
 * opposite things: one is the directive we require, the other is the directive
 * we refuse.
 * @param {string} body
 * @returns {Array<{ owner: string|null, repo: string|null, number: number }>}
 */
export function extractSilentCloseRefs(body) {
  if (!body) return [];
  const refs = [];
  // exec() on a /g regex is stateful; build a fresh one per call so a previous
  // partial scan cannot make the next one start mid-string and miss a match.
  const pattern = new RegExp(SILENT_CLOSE_PATTERN.source, SILENT_CLOSE_PATTERN.flags);
  let match;
  while ((match = pattern.exec(body)) !== null) {
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

  // Checked BEFORE the Closes path: a body can carry a correct `Closes #N`
  // and a stray `fixes #M` at the same time, and that combination is the most
  // dangerous one -- it passes every existing check while quietly taking a
  // second issue down with it on merge.
  const silent = extractSilentCloseRefs(body);
  if (silent.length > 0) {
    const listed = silent
      .map((r) => (r.owner ? `${r.owner}/${r.repo}#${r.number}` : `#${r.number}`))
      .join(", ");
    return {
      valid: false,
      reason:
        `PR body uses an auto-close verb GitHub honours but this check has ` +
        `never reported: ${listed}. GitHub closes on fix/fixes/fixed and ` +
        `resolve/resolves/resolved as well as close/closes/closed, so this ` +
        `would close silently on merge. If you mean to close it, write ` +
        `\`Closes #N\` -- the mandated form, in commit, title and body. If ` +
        `you do not, reword: \`see #N\`, \`a fix for #N\`, ` +
        `\`whoever addresses #N\`, \`follow-up: #N\`.`,
      refs: [],
      noIssue: false,
      silentCloseRefs: silent,
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
      "No issue reference found. Add `Closes #N` or `No-Issue: <reason>` to the PR body.",
    refs: [],
    noIssue: false,
  };
}



