import { describe, it, expect } from "vitest";
import { validatePRBody } from "../src/validate.js";

describe("validatePRBody", () => {
  describe("passing cases", () => {
    it.each([
      ["Closes #42", "simple Closes"],
      ["closes #1", "lowercase"],
      ["Closed #99", "past tense"],
      ["Close #5", "imperative"],
      ["Fixes #10", "Fixes"],
      ["Fixed #10", "Fixed"],
      ["Fix #10", "Fix"],
      ["Resolves #7", "Resolves"],
      ["Resolved #7", "Resolved"],
      ["Resolve #7", "Resolve"],
    ])("passes for '%s' (%s)", (body) => {
      const result = validatePRBody(body);
      expect(result.valid).toBe(true);
    });

    it("passes for cross-repo reference", () => {
      const result = validatePRBody("Closes martymcenroe/Aletheia#123");
      expect(result.valid).toBe(true);
    });

    it("passes for cross-repo reference with dots/hyphens", () => {
      const result = validatePRBody("Fixes my-org/my.repo#5");
      expect(result.valid).toBe(true);
    });

    it("passes when reference is embedded in longer text", () => {
      const body = "This PR refactors the auth module.\n\nCloses #15";
      const result = validatePRBody(body);
      expect(result.valid).toBe(true);
    });

    it("passes for No-Issue with reason", () => {
      const result = validatePRBody("No-Issue: infrastructure change");
      expect(result.valid).toBe(true);
    });

    it("passes for No-Issue case-insensitive", () => {
      const result = validatePRBody("no-issue: testing");
      expect(result.valid).toBe(true);
    });

    it("passes for multiple issue references", () => {
      const result = validatePRBody("Closes #1, Fixes #2");
      expect(result.valid).toBe(true);
    });
  });

  describe("failing cases", () => {
    it("fails for null body", () => {
      const result = validatePRBody(null);
      expect(result.valid).toBe(false);
      expect(result.reason).toContain("empty");
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
  });
});
