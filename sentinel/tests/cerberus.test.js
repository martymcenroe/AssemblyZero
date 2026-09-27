import { describe, it, expect, beforeAll } from "vitest";
import { approveAsCerberus, shouldApprove, CERBERUS_LOGIN } from "../src/cerberus.js";

const SHA = "abc123";
let env;

beforeAll(async () => {
  // A real RSA key, so createAppJWT signs exactly as it does in production.
  const pair = await crypto.subtle.generateKey(
    { name: "RSASSA-PKCS1-v1_5", modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: "SHA-256" },
    true,
    ["sign", "verify"]
  );
  const pkcs8 = new Uint8Array(await crypto.subtle.exportKey("pkcs8", pair.privateKey));
  env = { CERBERUS_APP_ID: "12345", CERBERUS_PRIVATE_KEY_B64: btoa(String.fromCharCode(...pkcs8)) };
});

function fakeGitHub({ reviews = [], failOn = null } = {}) {
  const calls = [];
  const fetchImpl = async (url, init = {}) => {
    calls.push({ url, method: init.method || "GET", body: init.body, auth: init.headers?.Authorization });
    const ok = !(failOn && url.includes(failOn));
    const json = url.endsWith("/installation")
      ? { id: 99 }
      : url.includes("/access_tokens")
        ? { token: "inst-token" }
        : url.includes("/reviews?")
          ? reviews
          : {};
    return {
      ok,
      status: ok ? 200 : 500,
      json: async () => json,
      text: async () => (ok ? "" : "boom"),
    };
  };
  return { calls, fetchImpl };
}

describe("shouldApprove (#3663)", () => {
  it("T1 approves a passing PR from an ordinary author", () => {
    expect(shouldApprove({ valid: true, author: "someone", env })).toBe(true);
  });
  it("T1 never approves Dependabot", () => {
    expect(shouldApprove({ valid: true, author: "dependabot[bot]", env })).toBe(false);
  });
  it("T1 never approves when issue-reference did not pass", () => {
    expect(shouldApprove({ valid: false, author: "someone", env })).toBe(false);
  });
  it("T1 does nothing without both secrets", () => {
    expect(shouldApprove({ valid: true, author: "someone", env: {} })).toBe(false);
    expect(shouldApprove({ valid: true, author: "someone", env: { CERBERUS_APP_ID: "1" } })).toBe(false);
  });
});

describe("approveAsCerberus (#3663)", () => {
  it("T2 posts one APPROVE review on the head commit", async () => {
    const gh = fakeGitHub();
    const result = await approveAsCerberus(env, "o", "r", 7, SHA, gh.fetchImpl);
    expect(result).toEqual({ approved: true, reason: "approved" });
    const posts = gh.calls.filter((c) => c.method === "POST" && c.url.endsWith("/pulls/7/reviews"));
    expect(posts).toHaveLength(1);
    expect(JSON.parse(posts[0].body)).toMatchObject({ event: "APPROVE", commit_id: SHA });
    expect(posts[0].auth).toBe("token inst-token");
  });

  it("T2 posts nothing when Cerberus already approved this commit", async () => {
    const gh = fakeGitHub({
      reviews: [{ state: "APPROVED", commit_id: SHA, user: { login: CERBERUS_LOGIN } }],
    });
    const result = await approveAsCerberus(env, "o", "r", 7, SHA, gh.fetchImpl);
    expect(result.approved).toBe(false);
    expect(gh.calls.some((c) => c.method === "POST" && c.url.endsWith("/reviews"))).toBe(false);
  });

  it("T2 approves again after a new push (an approval on an older commit)", async () => {
    const gh = fakeGitHub({
      reviews: [{ state: "APPROVED", commit_id: "older", user: { login: CERBERUS_LOGIN } }],
    });
    expect((await approveAsCerberus(env, "o", "r", 7, SHA, gh.fetchImpl)).approved).toBe(true);
  });

  it("T3 a failing GitHub call is reported, never thrown, and carries no key", async () => {
    const gh = fakeGitHub({ failOn: "/access_tokens" });
    const result = await approveAsCerberus(env, "o", "r", 7, SHA, gh.fetchImpl);
    expect(result.approved).toBe(false);
    expect(result.reason).toMatch(/^failed: Cerberus installation token: 500/);
    expect(result.reason).not.toContain(env.CERBERUS_PRIVATE_KEY_B64.slice(0, 40));
  });
});
