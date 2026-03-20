import { describe, it, expect } from "vitest";
import { validatePRBody, extractIssueRefs } from "../src/validate.js";

describe("extractIssueRefs", () => {
  it("extracts a simple reference", () => {
    expect(extractIssueRefs("Closes #42")).toEqual([
      { owner: null, repo: null, number: 42 },
    ]);
  });

  it("extracts cross-repo reference", () => {
    expect(extractIssueRefs("Closes martymcenroe/Aletheia#123")).toEqual([
      { owner: "martymcenroe", repo: "Aletheia", number: 123 },
    ]);
  });

  it("extracts multiple references", () => {
    const refs = extractIssueRefs("Closes #1, Closes owner/repo#2");
    expect(refs).toEqual([
      { owner: null, repo: null, number: 1 },
      { owner: "owner", repo: "repo", number: 2 },
    ]);
  });

  it("returns empty for no references", () => {
    expect(extractIssueRefs("Just a PR")).toEqual([]);
  });

  it("returns empty for null", () => {
    expect(extractIssueRefs(null)).toEqual([]);
  });

  it("handles dots and hyphens in owner/repo", () => {
    expect(extractIssueRefs("Closes my-org/my.repo#5")).toEqual([
      { owner: "my-org", repo: "my.repo", number: 5 },
    ]);
  });
});

describe("validatePRBody", () => {
  describe("passing cases", () => {
    it.each([
      ["Closes #42", "simple Closes"],
      ["closes #1", "lowercase"],
      ["Closed #99", "past tense"],
      ["Close #5", "imperative"],
    ])("passes for '%s' (%s)", (body) => {
      const result = validatePRBody(body);
      expect(result.valid).toBe(true);
      expect(result.refs.length).toBeGreaterThan(0);
      expect(result.noIssue).toBe(false);
    });

    it("passes for cross-repo reference", () => {
      const result = validatePRBody("Closes martymcenroe/Aletheia#123");
      expect(result.valid).toBe(true);
      expect(result.refs[0].owner).toBe("martymcenroe");
    });

    it("passes for cross-repo reference with dots/hyphens", () => {
      const result = validatePRBody("Closes my-org/my.repo#5");
      expect(result.valid).toBe(true);
    });

    it("passes when reference is embedded in longer text", () => {
      const body = "This PR refactors the auth module.\n\nCloses #15";
      const result = validatePRBody(body);
      expect(result.valid).toBe(true);
      expect(result.refs[0].number).toBe(15);
    });

    it("passes for No-Issue with reason", () => {
      const result = validatePRBody("No-Issue: infrastructure change");
      expect(result.valid).toBe(true);
      expect(result.noIssue).toBe(true);
      expect(result.refs).toEqual([]);
    });

    it("passes for No-Issue case-insensitive", () => {
      const result = validatePRBody("no-issue: testing");
      expect(result.valid).toBe(true);
      expect(result.noIssue).toBe(true);
    });

    it("passes for No-Issue on its own line in longer body", () => {
      const body = "Some description here.\n\nNo-Issue: infrastructure change";
      const result = validatePRBody(body);
      expect(result.valid).toBe(true);
      expect(result.noIssue).toBe(true);
    });

    it("passes for multiple issue references", () => {
      const result = validatePRBody("Closes #1, Closes #2");
      expect(result.valid).toBe(true);
      expect(result.refs).toHaveLength(2);
    });
  });

  describe("failing cases", () => {
    it.each([
      ["Fixed #10", "fails for Fixed"],
      ["Fix #10", "fails for Fix"],
      ["Resolved #7", "fails for Resolved"],
      ["Resolve #7", "fails for Resolve"],
    ])("fails for '%s' (%s)", (body) => {
      const result = validatePRBody(body);
      expect(result.valid).toBe(false);
    });

    it("fails for null body", () => {
      const result = validatePRBody(null);
      expect(result.valid).toBe(false);
      expect(result.reason).toContain("empty");
      expect(result.refs).toEqual([]);
    });

    it("fails for empty string", () => {
      const result = validatePRBody("");
      expect(result.valid).toBe(false);
    });

    it("fails for whitespace-only body", () => {
      const result = validatePRBody("   \n\t  ");
      expect(result.valid).toBe(false);
    });

    it("fails for body without any reference", () => {
      const result = validatePRBody("Updated the README with new docs");
      expect(result.valid).toBe(false);
      expect(result.reason).toContain("No issue reference");
    });

    it("fails for bare issue number without keyword", () => {
      const result = validatePRBody("#42");
      expect(result.valid).toBe(false);
    });

    it("fails for No-Issue without reason", () => {
      const result = validatePRBody("No-Issue:");
      expect(result.valid).toBe(false);
    });

    it("fails for No-Issue with only whitespace after colon", () => {
      const result = validatePRBody("No-Issue:   ");
      expect(result.valid).toBe(false);
    });

    it("fails for No-Issue embedded mid-line in prose", () => {
      const result = validatePRBody("This is about No-Issue: stuff but should have an issue");
      expect(result.valid).toBe(false);
    });
  });
});
