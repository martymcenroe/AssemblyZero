// The auto-close verbs this check never looked at.
//
// GitHub acts on three verb families; validate.js only ever extracted one.
// The other two close an issue on merge with nothing reporting it, which is
// the failure this suite pins down. A body that reads as prose to a human is
// a directive to GitHub.
import { describe, it, expect } from "vitest";
import { validatePRBody, extractSilentCloseRefs } from "../src/validate.js";

describe("extractSilentCloseRefs", () => {
  it("catches every fix-family spelling", () => {
    for (const verb of ["fix", "fixes", "fixed", "Fix", "FIXES", "Fixed"]) {
      const refs = extractSilentCloseRefs(`this ${verb} #47 somehow`);
      expect(refs, verb).toHaveLength(1);
      expect(refs[0].number, verb).toBe(47);
    }
  });

  it("catches every resolve-family spelling", () => {
    for (const verb of ["resolve", "resolves", "resolved", "Resolve", "RESOLVED"]) {
      const refs = extractSilentCloseRefs(`this ${verb} #9 somehow`);
      expect(refs, verb).toHaveLength(1);
      expect(refs[0].number, verb).toBe(9);
    }
  });

  it("catches the cross-repo qualified form", () => {
    const refs = extractSilentCloseRefs("fixed owner-x/repo-y#1234");
    expect(refs).toEqual([{ owner: "owner-x", repo: "repo-y", number: 1234 }]);
  });

  it("does not fire on close/closes/closed", () => {
    // Those are the mandated form and are policed by extractIssueRefs. Firing
    // here would refuse every correctly written PR in the fleet.
    expect(extractSilentCloseRefs("Closes #1")).toHaveLength(0);
    expect(extractSilentCloseRefs("closed #1")).toHaveLength(0);
  });

  it("does not fire on prose that merely mentions a repair", () => {
    // The verb must be immediately followed by the reference. Without this the
    // check would make ordinary PR bodies unwritable, and an over-blocking
    // gate gets switched off, taking the real protections with it.
    expect(extractSilentCloseRefs("a fix for #47 lands separately")).toHaveLength(0);
    expect(extractSilentCloseRefs("the repair in #47 is unrelated")).toHaveLength(0);
    expect(extractSilentCloseRefs("whoever addresses #47")).toHaveLength(0);
    expect(extractSilentCloseRefs("see #47")).toHaveLength(0);
    expect(extractSilentCloseRefs("follow-up: #47")).toHaveLength(0);
  });

  it("does not treat prefixed words as the verb", () => {
    expect(extractSilentCloseRefs("postfixes #47")).toHaveLength(0);
    expect(extractSilentCloseRefs("unresolved #47")).toHaveLength(0);
  });

  it("finds every occurrence, not just the first", () => {
    // The regex is /g and exec() is stateful; a shared object would resume
    // mid-string on the next call and silently miss matches.
    const refs = extractSilentCloseRefs("fixes #1 and resolves #2 and fixed #3");
    expect(refs.map((r) => r.number)).toEqual([1, 2, 3]);
  });

  it("is not stateful across calls", () => {
    const body = "fixes #5";
    expect(extractSilentCloseRefs(body)).toHaveLength(1);
    expect(extractSilentCloseRefs(body)).toHaveLength(1);
  });

  it("handles an empty or missing body", () => {
    expect(extractSilentCloseRefs("")).toEqual([]);
    expect(extractSilentCloseRefs(null)).toEqual([]);
  });
});

describe("validatePRBody with silent-close verbs", () => {
  it("refuses a body whose only directive is a silent one", () => {
    const r = validatePRBody("Fixes #47");
    expect(r.valid).toBe(false);
    expect(r.reason).toContain("#47");
    expect(r.silentCloseRefs).toHaveLength(1);
  });

  it("refuses a correct Closes that also carries a stray silent verb", () => {
    // The most dangerous combination and the reason this is checked BEFORE the
    // Closes path: it satisfies every pre-existing rule while quietly taking a
    // second issue down on merge.
    const r = validatePRBody("Closes #100. Whoever fixes #47 gets a listing.");
    expect(r.valid).toBe(false);
    expect(r.silentCloseRefs.map((x) => x.number)).toEqual([47]);
    expect(r.reason).not.toContain("#100");
  });

  it("names the substitution in the refusal", () => {
    // A gate that refuses without saying what to type instead gets worked
    // around rather than obeyed.
    const r = validatePRBody("Resolves #9");
    expect(r.reason).toContain("Closes #N");
    expect(r.reason).toContain("see #N");
  });

  it("still passes an ordinary correct body", () => {
    const r = validatePRBody("Does the thing.\n\nCloses #123");
    expect(r.valid).toBe(true);
    expect(r.refs).toHaveLength(1);
  });

  it("still passes a No-Issue exemption", () => {
    const r = validatePRBody("No-Issue: scaffolder catch-up for a same-day repo");
    expect(r.valid).toBe(true);
    expect(r.noIssue).toBe(true);
  });

  it("refuses a No-Issue body carrying a silent verb", () => {
    // The exemption is from needing an issue, not from closing one by accident.
    const r = validatePRBody("No-Issue: cleanup\n\nthis fixes #47 incidentally");
    expect(r.valid).toBe(false);
    expect(r.silentCloseRefs).toHaveLength(1);
  });

  it("still refuses an empty body for the original reason", () => {
    const r = validatePRBody("");
    expect(r.valid).toBe(false);
    expect(r.reason).toContain("empty");
  });
});
