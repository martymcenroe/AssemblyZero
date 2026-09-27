import { describe, it, expect } from "vitest";
import { DRIVER_STAMP, driverProvenance, validatePRBody } from "../src/validate.js";

const RUN = "20260927T124453-95623d";
const STAMPED = `Does the thing.\n\nCloses #12\n\nLanded-By: merge-driver ${RUN}\n`;
const BARE = "Does the thing.\n\nCloses #12\n";

const decide = (body, mode, author = "someone", exemptAuthors = "") =>
  driverProvenance({ body, author, mode, exemptAuthors });

describe("driverProvenance (#3660)", () => {
  it("T1 warn, no stamp: warns; issue-reference is not touched", () => {
    expect(decide(BARE, "warn").verdict).toBe("warn");
    expect(validatePRBody(BARE).valid).toBe(true);
  });

  it("T2 enforce, no stamp: fails", () => {
    expect(decide(BARE, "enforce").verdict).toBe("fail");
  });

  it("T3 enforce, stamp and a valid Closes: passes", () => {
    expect(decide(STAMPED, "enforce").verdict).toBe("pass");
    expect(validatePRBody(STAMPED).valid).toBe(true);
  });

  it("T4 dependabot and a listed author pass in enforce", () => {
    expect(decide(BARE, "enforce", "dependabot[bot]").verdict).toBe("pass");
    expect(decide(BARE, "enforce", "ops-bot", "a, ops-bot ,b").verdict).toBe("pass");
    expect(decide(BARE, "enforce", "other", "a,ops-bot").verdict).toBe("fail");
  });

  it("T5 the stamp inside a sentence is not a stamp", () => {
    const inline = `Closes #12. See Landed-By: merge-driver ${RUN} above.\n`;
    expect(DRIVER_STAMP.test(inline)).toBe(false);
    expect(decide(inline, "enforce").verdict).toBe("fail");
  });

  it("T6 off, or an unknown mode, skips entirely", () => {
    expect(decide(BARE, "off").verdict).toBe("skip");
    expect(decide(BARE, undefined).verdict).toBe("skip");
    expect(decide(BARE, "ENFORCE").verdict).toBe("skip");
  });

  it("the stamp is never read as an issue reference", () => {
    expect(validatePRBody(STAMPED).refs).toEqual([{ owner: null, repo: null, number: 12 }]);
  });

  it("a stamp with a malformed run id does not count", () => {
    expect(decide("Closes #1\nLanded-By: merge-driver 2026-09-27\n", "enforce").verdict).toBe("fail");
  });
});
