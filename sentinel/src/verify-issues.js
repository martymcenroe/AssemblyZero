// Verify that issue references point to real, open issues (not PRs, not closed).

// GitHub owner/repo names: alphanumeric, hyphens, dots, underscores.
// Must not be ".." (path traversal) or start/end with dots.
const GITHUB_NAME_PATTERN = /^[a-zA-Z0-9](?:[a-zA-Z0-9._-]*[a-zA-Z0-9])?$/;

// Maximum number of refs to verify per webhook (prevent rate limit exhaustion)
const MAX_REFS_TO_VERIFY = 10;

/**
 * Validate that a GitHub owner or repo name is safe for URL construction.
 * @param {string} name
 * @returns {boolean}
 */
function isValidGitHubName(name) {
  return (
    typeof name === "string" &&
    name.length > 0 &&
    name.length <= 100 &&
    !name.includes("..") &&
    GITHUB_NAME_PATTERN.test(name)
  );
}

/**
 * Verify a single issue reference via the GitHub API.
 * @param {string} token - Installation access token
 * @param {string} owner - Repo owner
 * @param {string} repo - Repo name
 * @param {number} number - Issue number
 * @param {boolean} isCrossRepo - Whether this ref explicitly named a different repo
 * @returns {Promise<{ valid: boolean, reason: string }>}
 */
async function verifySingleIssue(token, owner, repo, number, isCrossRepo) {
  // Validate owner/repo names before URL construction (prevent path traversal)
  if (!isValidGitHubName(owner) || !isValidGitHubName(repo)) {
    return {
      valid: false,
      reason: `Invalid owner/repo name in reference: ${owner}/${repo}#${number}.`,
    };
  }

  const url = `https://api.github.com/repos/${owner}/${repo}/issues/${number}`;

  let response;
  try {
    response = await fetch(url, {
      headers: {
        Authorization: `token ${token}`,
        Accept: "application/vnd.github+json",
        "User-Agent": "pr-sentinel",
        "X-GitHub-Api-Version": "2022-11-28",
      },
    });
  } catch {
    // Network error — fail open for same-repo (transient), fail closed for cross-repo
    if (isCrossRepo) {
      return { valid: false, reason: `Could not verify cross-repo reference ${owner}/${repo}#${number}. Network error.` };
    }
    return { valid: true, reason: `Could not reach GitHub API for ${owner}/${repo}#${number} — skipping verification.` };
  }

  if (response.status === 404) {
    return {
      valid: false,
      reason: `Issue ${owner}/${repo}#${number} does not exist. Create an issue first, then reference it.`,
    };
  }

  if (!response.ok) {
    // Cross-repo: 403 likely means no access — fail closed
    // Same-repo: 403 likely means rate limit — fail open
    if (isCrossRepo) {
      return { valid: false, reason: `Cannot verify cross-repo reference ${owner}/${repo}#${number} (HTTP ${response.status}). Ensure the issue exists and is accessible.` };
    }
    return { valid: true, reason: `GitHub API returned ${response.status} for ${owner}/${repo}#${number} — skipping verification.` };
  }

  let data;
  try {
    data = await response.json();
  } catch {
    return { valid: false, reason: `Invalid response from GitHub API for ${owner}/${repo}#${number}.` };
  }

  if (data.pull_request) {
    return {
      valid: false,
      reason: `#${number} in ${owner}/${repo} is a pull request, not an issue. Reference an actual issue.`,
    };
  }

  if (data.state !== "open") {
    return {
      valid: false,
      reason: `Issue ${owner}/${repo}#${number} is already ${data.state}. Reference an open issue.`,
    };
  }

  return { valid: true, reason: `Issue ${owner}/${repo}#${number} is open.` };
}

/**
 * Verify all issue references from a PR body.
 * @param {string} token - Installation access token
 * @param {string} defaultOwner - PR's repo owner (for bare #N refs)
 * @param {string} defaultRepo - PR's repo name (for bare #N refs)
 * @param {Array<{ owner: string|null, repo: string|null, number: number }>} refs
 * @returns {Promise<{ valid: boolean, reason: string }>}
 */
export async function verifyIssueRefs(token, defaultOwner, defaultRepo, refs) {
  if (refs.length === 0) {
    return { valid: true, reason: "No references to verify." };
  }

  // Cap refs to prevent rate limit exhaustion
  const capped = refs.slice(0, MAX_REFS_TO_VERIFY);

  const results = await Promise.all(
    capped.map((ref) =>
      verifySingleIssue(
        token,
        ref.owner || defaultOwner,
        ref.repo || defaultRepo,
        ref.number,
        ref.owner !== null // isCrossRepo: true when owner was explicitly provided
      )
    )
  );

  const failures = results.filter((r) => !r.valid);
  if (failures.length > 0) {
    return {
      valid: false,
      reason: failures.map((f) => f.reason).join("\n"),
    };
  }

  let reason = results.map((r) => r.reason).join("\n");
  if (refs.length > MAX_REFS_TO_VERIFY) {
    reason += `\nNote: Only first ${MAX_REFS_TO_VERIFY} of ${refs.length} references were verified.`;
  }

  return { valid: true, reason };
}
