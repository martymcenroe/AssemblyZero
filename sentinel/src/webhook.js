// Webhook handler — HMAC-SHA256 signature verification + event dispatch.

import { getInstallationToken } from "./auth.js";
import { createCheckRun } from "./checks.js";
import { validatePRBody } from "./validate.js";
import { verifyIssueRefs } from "./verify-issues.js";

/**
 * Verify the HMAC-SHA256 signature from GitHub.
 * @param {string} secret - Webhook secret
 * @param {string} signature - X-Hub-Signature-256 header value
 * @param {string} body - Raw request body
 * @returns {Promise<boolean>}
 */
export async function verifySignature(secret, signature, body) {
  if (!signature || !signature.startsWith("sha256=")) {
    return false;
  }

  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );

  const mac = await crypto.subtle.sign(
    "HMAC",
    key,
    new TextEncoder().encode(body)
  );

  const expected = Array.from(new Uint8Array(mac))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");

  const received = signature.slice("sha256=".length);

  // Constant-time comparison
  if (expected.length !== received.length) return false;
  let mismatch = 0;
  for (let i = 0; i < expected.length; i++) {
    mismatch |= expected.charCodeAt(i) ^ received.charCodeAt(i);
  }
  return mismatch === 0;
}

/**
 * Handle incoming webhook requests from GitHub.
 */
export async function handleWebhook(request, env) {
  // Guard: webhook secret must be configured
  if (!env.WEBHOOK_SECRET) {
    console.error("WEBHOOK_SECRET is not configured");
    return new Response("Server misconfigured", { status: 500 });
  }

  const body = await request.text();
  const signature = request.headers.get("X-Hub-Signature-256");

  const valid = await verifySignature(env.WEBHOOK_SECRET, signature, body);
  if (!valid) {
    return new Response("Invalid signature", { status: 401 });
  }

  const event = request.headers.get("X-GitHub-Event");

  // Only handle pull_request events
  if (event !== "pull_request") {
    return new Response("Ignored event", { status: 200 });
  }

  try {
    const payload = JSON.parse(body);
    const action = payload.action;

    // Only evaluate on opened, edited, reopened, synchronize
    if (!["opened", "edited", "reopened", "synchronize"].includes(action)) {
      return new Response("Ignored action", { status: 200 });
    }

    const pr = payload.pull_request;

    const owner = payload.repository.owner.login;
    const repo = payload.repository.name;
    const headSha = pr.head.sha;
    const installationId = payload.installation.id;
    const checkName = env.CHECK_NAME || "pr-sentinel / issue-reference";

    // Auto-pass dependabot PRs — they don't have issue references
    // but the check run must be created to complete the check suite
    if (pr.user?.login === "dependabot[bot]") {
      const token = await getInstallationToken(
        env.APP_ID,
        env.PRIVATE_KEY_B64,
        installationId
      );
      await createCheckRun(token, owner, repo, headSha, checkName, {
        valid: true,
        reason: "Dependabot PR — issue reference not required.",
      });
      return new Response(
        JSON.stringify({ conclusion: "success", skipped: "dependabot" }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    }

    // Validate PR body (regex check)
    let result = validatePRBody(pr.body);

    // Get installation token (needed for both verification and check run)
    const token = await getInstallationToken(
      env.APP_ID,
      env.PRIVATE_KEY_B64,
      installationId
    );

    // If regex passed with issue refs, verify they point to real open issues
    if (result.valid && result.refs.length > 0) {
      const verification = await verifyIssueRefs(token, owner, repo, result.refs);
      if (!verification.valid) {
        result = {
          valid: false,
          reason: verification.reason,
        };
      }
    }

    await createCheckRun(token, owner, repo, headSha, checkName, result);

    return new Response(
      JSON.stringify({ conclusion: result.valid ? "success" : "action_required" }),
      {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }
    );
  } catch (err) {
    console.error("Webhook processing error:", err.message);
    return new Response("Internal error", { status: 500 });
  }
}
