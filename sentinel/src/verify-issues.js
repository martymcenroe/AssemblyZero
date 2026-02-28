// Verify that issue references point to real, open issues (not PRs, not closed).

/**
 * Verify a single issue reference via the GitHub API.
 * @param {string} token - Installation access token
 * @param {string} owner - Repo owner
 * @param {string} repo - Repo name
 * @param {number} number - Issue number
 * @returns {Promise<{ valid: boolean, reason: string }>}
 */
async function verifySingleIssue(token, owner, repo, number) {
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
    // Network error — fail open so we don't block PRs on transient failures
    return { valid: true, reason: `Could not reach GitHub API for ${owner}/${repo}#${number} — skipping verification.` };
  }

  if (response.status === 404) {
    return {
      valid: false,
      reason: `Issue ${owner}/${repo}#${number} does not exist. Create an issue first, then reference it.`,
    };
  }

  if (!response.ok) {
    // API error (rate limit, auth issue) — fail open
    return { valid: true, reason: `GitHub API returned ${response.status} for ${owner}/${repo}#${number} — skipping verification.` };
  }

  const data = await response.json();

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

  const results = await Promise.all(
    refs.map((ref) =>
      verifySingleIssue(
        token,
        ref.owner || defaultOwner,
        ref.repo || defaultRepo,
        ref.number
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

  return {
    valid: true,
    reason: results.map((r) => r.reason).join("\n"),
  };
}
