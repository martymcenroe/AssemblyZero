import { describe, it, expect, vi, beforeEach } from "vitest";
import { verifyIssueRefs } from "../src/verify-issues.js";

describe("verifyIssueRefs", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  function mockFetch(responses) {
    let callIndex = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(() => {
        const resp = responses[callIndex++];
        return Promise.resolve(resp);
      })
    );
  }

  function jsonResponse(status, body) {
    return {
      ok: status >= 200 && status < 300,
      status,
      json: () => Promise.resolve(body),
      text: () => Promise.resolve(JSON.stringify(body)),
    };
  }

  it("returns valid for empty refs array", async () => {
    const result = await verifyIssueRefs("token", "owner", "repo", []);
    expect(result.valid).toBe(true);
  });

  it("passes for a real open issue", async () => {
    mockFetch([jsonResponse(200, { state: "open" })]);

    const result = await verifyIssueRefs("token", "owner", "repo", [
      { owner: null, repo: null, number: 1 },
    ]);
    expect(result.valid).toBe(true);
    expect(result.reason).toContain("open");
  });

  it("fails for a nonexistent issue (404)", async () => {
    mockFetch([{ ok: false, status: 404, text: () => Promise.resolve("") }]);

    const result = await verifyIssueRefs("token", "owner", "repo", [
      { owner: null, repo: null, number: 9999 },
    ]);
    expect(result.valid).toBe(false);
    expect(result.reason).toContain("does not exist");
  });

  it("fails for a pull request masquerading as an issue", async () => {
    mockFetch([
      jsonResponse(200, { state: "open", pull_request: { url: "..." } }),
    ]);

    const result = await verifyIssueRefs("token", "owner", "repo", [
      { owner: null, repo: null, number: 5 },
    ]);
    expect(result.valid).toBe(false);
    expect(result.reason).toContain("pull request, not an issue");
  });

  it("fails for a closed issue", async () => {
    mockFetch([jsonResponse(200, { state: "closed" })]);

    const result = await verifyIssueRefs("token", "owner", "repo", [
      { owner: null, repo: null, number: 10 },
    ]);
    expect(result.valid).toBe(false);
    expect(result.reason).toContain("already closed");
  });

  it("uses cross-repo owner/repo when provided", async () => {
    mockFetch([jsonResponse(200, { state: "open" })]);

    await verifyIssueRefs("token", "default-owner", "default-repo", [
      { owner: "other-owner", repo: "other-repo", number: 3 },
    ]);

    expect(fetch).toHaveBeenCalledWith(
      "https://api.github.com/repos/other-owner/other-repo/issues/3",
      expect.any(Object)
    );
  });

  it("uses default owner/repo for bare refs", async () => {
    mockFetch([jsonResponse(200, { state: "open" })]);

    await verifyIssueRefs("token", "default-owner", "default-repo", [
      { owner: null, repo: null, number: 7 },
    ]);

    expect(fetch).toHaveBeenCalledWith(
      "https://api.github.com/repos/default-owner/default-repo/issues/7",
      expect.any(Object)
    );
  });

  it("fails open on network error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new Error("network down")))
    );

    const result = await verifyIssueRefs("token", "owner", "repo", [
      { owner: null, repo: null, number: 1 },
    ]);
    expect(result.valid).toBe(true);
    expect(result.reason).toContain("skipping verification");
  });

  it("fails open on rate limit (403)", async () => {
    mockFetch([{ ok: false, status: 403, text: () => Promise.resolve("rate limited") }]);

    const result = await verifyIssueRefs("token", "owner", "repo", [
      { owner: null, repo: null, number: 1 },
    ]);
    expect(result.valid).toBe(true);
    expect(result.reason).toContain("skipping verification");
  });

  it("validates multiple refs — all must pass", async () => {
    mockFetch([
      jsonResponse(200, { state: "open" }),
      jsonResponse(200, { state: "closed" }),
    ]);

    const result = await verifyIssueRefs("token", "owner", "repo", [
      { owner: null, repo: null, number: 1 },
      { owner: null, repo: null, number: 2 },
    ]);
    expect(result.valid).toBe(false);
    expect(result.reason).toContain("already closed");
  });

  it("passes when all multiple refs are valid", async () => {
    mockFetch([
      jsonResponse(200, { state: "open" }),
      jsonResponse(200, { state: "open" }),
    ]);

    const result = await verifyIssueRefs("token", "owner", "repo", [
      { owner: null, repo: null, number: 1 },
      { owner: null, repo: null, number: 2 },
    ]);
    expect(result.valid).toBe(true);
  });
});
