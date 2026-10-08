# ADR 0238: Personal bulk email goes out through a Gmail mail merge run from a Google Sheet

**Status:** Accepted (the operator, 2026-10-08, in session `dd156424-8f0d-46ee-967a-92bfa5b299d3`: "mark it as accepted ... really the ADR is for other agents." He asked for it the same day: "should you write yourself an ADR so that hwen i do this again you can do it right from the beginning? not just in this repo but anywhere")
**Date:** 2026-10-08
**Deciders:** Operator
**Related:** #4143; `tools/gmail_mail_merge.gs`

---

## Decision

**When the operator needs the same email sent to many people, one personal copy each, from his own Gmail, use `tools/gmail_mail_merge.gs`: a Google Apps Script bound to a Google Sheet, with a Gmail draft as the template.**

- The **Sheet** holds one row per recipient. The header row names the columns, and any column can be a placeholder. It must have an `Email` column and an `Email Sent` column.
- The **template** is an ordinary Gmail draft: subject, body, attachments. `{{Column}}` anywhere in the subject or body is filled from that row.
- The script adds a **Mail merge** menu: **Send test to me** (fills the first unsent row and sends it to the operator only, stamping nothing) and **Send emails** (sends every unsent row, stamping `Email Sent` as each goes).
- A row already stamped is never sent again, so the merge can be re-run as people are added, and a run cut off part-way resumes where it stopped.

It runs inside the operator's Google account and sends as him. Nothing is stored on this machine: no password, no OAuth client, no token. Messages land in his Gmail **Sent** folder like any other.

## Why this design

- Gmail's built-in mail merge is not on every plan, and a personal account may not have it. Apps Script is on every Google account and costs nothing.
- Sending through a local program and the Gmail API would put an OAuth client secret and a refresh token on disk, which then need the full secret-handling treatment. The bound script needs none.
- A draft as template lets the operator write and attach in the tool he already uses, and see exactly what will go out.

## What the first run taught (each one cost a round trip)

### The script

1. **Apps Script stops every run at 6 minutes.** The first version timed out after a successful test. Two causes, both fixed in the tool:
   - It found the template by opening every Gmail draft (`GmailApp.getDrafts()` and `getMessage()` on each). Use one search: `GmailApp.search('in:drafts subject:"..."')`, then the draft message whose subject matches exactly.
   - It ended with a blocking `ui.alert`, and the run stayed open until the operator clicked OK. Report results with `SpreadsheetApp.getActive().toast(...)`, which does not wait.
2. **Do not prompt for the template subject.** Fix it as a constant at the top of the script (`TEMPLATE_SUBJECT`). A prompt is one more thing to type exactly, every run.
3. **Stamp each row the moment its email goes, and flush.** Then a cutoff loses nothing, and the next run continues.
4. **Consumer Gmail allows about 100 script-sent emails a day.** The send step shows the quota left before sending and stops at it.

### The recipient list

5. **Build the list with a program from the canonical data, never by hand.** The list builder in the repo reads the same source as any reviewer or contact sheet, so the two cannot disagree, and prints everyone it leaves out and why.
6. **Keep a sent ledger in the repo** (Email, Name, date sent), and have the builder leave everyone in it out. The Sheet's stamps live in Google; the ledger is the record the next session can read.
7. **Use the name each person goes by.** A roster may hold a legal or transliterated name the person never uses socially. Show the operator the first-name column before the send; he knows who goes by what.
8. **Never guess an address from a company's pattern.** Record where each address came from (a faculty page, the person's own blog, a business card, the operator). Where there is none, route the request through whoever suggested the person.
9. **Leave out people who already have the message**, such as the original recipients of a survey being widened.

### The runbook

10. **Walk every screen before calling the runbook done.** The first runbook skipped naming and saving the Apps Script project, reloading the sheet so the menu appears, which file to attach, and the template subject. The operator found each one by getting stuck.
11. **Put the exact text in the step.** The subject to paste, the attachment's full Windows path, the menu item's exact name. A pointer to another file is a step the operator has to do twice.
12. **Do not tell the operator to type what he pastes.** A caution about typing `{{placeholders}}` carefully is wrong when the step says to paste the body; it only applies to editing a placeholder inside Gmail afterward.
13. **Say where the result shows up.** Gmail has no outbox; sent messages appear in **Sent**.

### Around the edges

14. **Office files cannot be opened from a Linux terminal by link.** Open them through Windows (`explorer.exe` with a `wslpath -w` path), or give the Windows path to open by hand.
15. **The prose gate flags `{{FirstName}}` and proper names.** Judge the template on a copy with the placeholders filled and names swapped for dictionary words, and keep the operator's own previously sent wording even when the judge objects to it.

## Consequences

- The next mail merge starts from `tools/gmail_mail_merge.gs`, changes only `TEMPLATE_SUBJECT`, and builds its list with a program and a sent ledger.
- Its runbook is written by walking the screens, with exact text in each step, before the operator is asked to follow it.
