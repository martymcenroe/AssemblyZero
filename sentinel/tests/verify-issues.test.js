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

  it("fails open on network error for same-repo ref", async () => {
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

  it("fails CLOSED on network error for cross-repo ref", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new Error("network down")))
    );

    const result = await verifyIssueRefs("token", "owner", "repo", [
      { owner: "other-org", repo: "other-repo", number: 1 },
    ]);
    expect(result.valid).toBe(false);
    expect(result.reason).toContain("cross-repo");
  });

  it("fails open on rate limit (403) for same-repo ref", async () => {
    mockFetch([{ ok: false, status: 403, text: () => Promise.resolve("rate limited") }]);

    const result = await verifyIssueRefs("token", "owner", "repo", [
      { owner: null, repo: null, number: 1 },
    ]);
    expect(result.valid).toBe(true);
    expect(result.reason).toContain("skipping verification");
  });

  it("fails CLOSED on 403 for cross-repo ref", async () => {
    mockFetch([{ ok: false, status: 403, text: () => Promise.resolve("rate limited") }]);

    const result = await verifyIssueRefs("token", "owner", "repo", [
      { owner: "other-org", repo: "other-repo", number: 1 },
    ]);
    expect(result.valid).toBe(false);
    expect(result.reason).toContain("cross-repo");
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

  describe("path traversal prevention", () => {
    it("rejects '..' as owner name", async () => {
      const result = await verifyIssueRefs("token", "owner", "repo", [
        { owner: "..", repo: "something", number: 1 },
      ]);
      expect(result.valid).toBe(false);
      expect(result.reason).toContain("Invalid owner/repo");
    });

    it("rejects '..' as repo name", async () => {
      const result = await verifyIssueRefs("token", "owner", "repo", [
        { owner: "legit-owner", repo: "..", number: 1 },
      ]);
      expect(result.valid).toBe(false);
      expect(result.reason).toContain("Invalid owner/repo");
    });

    it("rejects owner containing '..'", async () => {
      const result = await verifyIssueRefs("token", "owner", "repo", [
        { owner: "foo..bar", repo: "repo", number: 1 },
      ]);
      expect(result.valid).toBe(false);
      expect(result.reason).toContain("Invalid owner/repo");
    });

    it("accepts valid GitHub names with dots and hyphens", async () => {
      mockFetch([jsonResponse(200, { state: "open" })]);

      const result = await verifyIssueRefs("token", "owner", "repo", [
        { owner: "my-org", repo: "my.repo", number: 1 },
      ]);
      expect(result.valid).toBe(true);
    });

    it("rejects owner starting with a dot", async () => {
      const result = await verifyIssueRefs("token", "owner", "repo", [
        { owner: ".hidden", repo: "repo", number: 1 },
      ]);
      expect(result.valid).toBe(false);
      expect(result.reason).toContain("Invalid owner/repo");
    });
  });

  describe("ref capping", () => {
    it("caps verification at 10 refs", async () => {
      const responses = Array(10).fill(jsonResponse(200, { state: "open" }));
      mockFetch(responses);

      const refs = Array.from({ length: 15 }, (_, i) => ({
        owner: null,
        repo: null,
        number: i + 1,
      }));

      const result = await verifyIssueRefs("token", "owner", "repo", refs);
      expect(result.valid).toBe(true);
      expect(fetch).toHaveBeenCalledTimes(10);
      expect(result.reason).toContain("Only first 10");
    });
  });

  describe("response parsing", () => {
    it("handles non-JSON response gracefully", async () => {
      vi.stubGlobal(
        "fetch",
        vi.fn(() =>
          Promise.resolve({
            ok: true,
            status: 200,
            json: () => Promise.reject(new SyntaxError("Unexpected token")),
          })
        )
      );

      const result = await verifyIssueRefs("token", "owner", "repo", [
        { owner: null, repo: null, number: 1 },
      ]);
      expect(result.valid).toBe(false);
      expect(result.reason).toContain("Invalid response");
    });
  });
});
