// GitHub Checks API — create check runs on PRs.

/**
 * Create or update a check run on a PR.
 * @param {string} token - Installation access token
 * @param {string} owner - Repo owner
 * @param {string} repo - Repo name
 * @param {string} headSha - Commit SHA
 * @param {string} checkName - Name of the check
 * @param {{ valid: boolean, reason: string }} result - Validation result
 * @returns {Promise<Response>}
 */
export async function createCheckRun(
  token,
  owner,
  repo,
  headSha,
  checkName,
  result
) {
  const body = {
    name: checkName,
    head_sha: headSha,
    status: "completed",
    conclusion: result.valid ? "success" : "action_required",
    output: {
      title: result.valid
        ? "Issue reference found"
        : "Missing issue reference",
      summary: result.reason,
    },
  };

  const response = await fetch(
    `https://api.github.com/repos/${owner}/${repo}/check-runs`,
    {
      method: "POST",
      headers: {
        Authorization: `token ${token}`,
        Accept: "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "pr-sentinel",
        "X-GitHub-Api-Version": "2022-11-28",
      },
      body: JSON.stringify(body),
    }
  );

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Failed to create check run: ${response.status} ${text}`);
  }

  return response;
}
