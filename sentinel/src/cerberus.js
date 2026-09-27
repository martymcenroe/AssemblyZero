// Approve a PR as the Cerberus App from inside pr-sentinel (#3663).
//
// Every Auto Review caller waits for exactly one check, `issue-reference`,
// which this Worker posts itself. Approving in the same request keeps the gate
// identical and ends the Actions runner that used to sit waiting for it, a
// billed minute per PR.
//
// The key lives only in the Worker's secrets. Nothing here logs it: errors
// carry GitHub's response text, never the JWT or the key.

import { createAppJWT } from "./auth.js";

const API = "https://api.github.com";
export const CERBERUS_LOGIN = "cerberus-az[bot]";
export const APPROVAL_BODY =
  "Approved by pr-sentinel as Cerberus: issue-reference passed. 🤖";

function headers(auth) {
  return {
    Authorization: auth,
    Accept: "application/vnd.github+json",
    "Content-Type": "application/json",
    "User-Agent": "pr-sentinel",
    "X-GitHub-Api-Version": "2022-11-28",
  };
}

/**
 * Whether the Worker should approve. Mirrors the reusable workflow's gate:
 * issue-reference passed, the author is not Dependabot, and Cerberus's
 * credentials are configured.
 * @param {{ valid: boolean, author: string|null|undefined, env: object }} input
 * @returns {boolean}
 */
export function shouldApprove({ valid, author, env }) {
  return (
    valid === true &&
    author !== "dependabot[bot]" &&
    Boolean(env && env.CERBERUS_APP_ID && env.CERBERUS_PRIVATE_KEY_B64)
  );
}

async function call(fetchImpl, url, init, what) {
  const response = await fetchImpl(url, init);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`${what}: ${response.status} ${text.slice(0, 200)}`);
  }
  return response.json();
}

/**
 * Approve the PR's head commit as Cerberus, unless Cerberus already approved
 * that commit. Never throws: returns what happened.
 * @returns {Promise<{ approved: boolean, reason: string }>}
 */
export async function approveAsCerberus(env, owner, repo, prNumber, headSha, fetchImpl = fetch) {
  try {
    const jwt = await createAppJWT(env.CERBERUS_APP_ID, env.CERBERUS_PRIVATE_KEY_B64);
    const installation = await call(
      fetchImpl,
      `${API}/repos/${owner}/${repo}/installation`,
      { headers: headers(`Bearer ${jwt}`) },
      "Cerberus installation lookup"
    );
    const { token } = await call(
      fetchImpl,
      `${API}/app/installations/${installation.id}/access_tokens`,
      { method: "POST", headers: headers(`Bearer ${jwt}`) },
      "Cerberus installation token"
    );
    const reviews = await call(
      fetchImpl,
      `${API}/repos/${owner}/${repo}/pulls/${prNumber}/reviews?per_page=100`,
      { headers: headers(`token ${token}`) },
      "review list"
    );
    const already = reviews.some(
      (r) =>
        r.state === "APPROVED" &&
        r.commit_id === headSha &&
        r.user &&
        r.user.login === CERBERUS_LOGIN
    );
    if (already) return { approved: false, reason: "already approved on this commit" };
    await call(
      fetchImpl,
      `${API}/repos/${owner}/${repo}/pulls/${prNumber}/reviews`,
      {
        method: "POST",
        headers: headers(`token ${token}`),
        body: JSON.stringify({ event: "APPROVE", commit_id: headSha, body: APPROVAL_BODY }),
      },
      "approval"
    );
    return { approved: true, reason: "approved" };
  } catch (err) {
    return { approved: false, reason: `failed: ${err.message}` };
  }
}
