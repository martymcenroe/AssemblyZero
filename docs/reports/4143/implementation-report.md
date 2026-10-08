# Implementation Report — Issue #4143

- `docs/adrs/0238-gmail-mail-merge-from-a-sheet.md` (Proposed): personal bulk email goes through a Gmail mail merge run from a Google Sheet, with fifteen lessons from a first run of 28 emails, covering the script, the recipient list, the runbook, and the edges.
- `tools/gmail_mail_merge.gs`: the working script from that run, made generic. `TEMPLATE_SUBJECT` is a placeholder, and the script refuses to run until it is set.

Neither file names a private repository, a person, or the activity the first run served.
