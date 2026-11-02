# Implementation report: #4552

Revision pinning read a verdict's "Section 5.1" as text and looked for it in the draft. A spec heading reads `### 5.1 ...`, never "Section 5.1", so the reference named no block. The subsection the reviewer asked to change stayed locked and the drafter's edit was refused. On the real run behind #4551 this refused the two edge-case lines under `### 5.1` and the "No changes required" line under `### 6.7`.

## What changed

- `revision_pinning.py`: a Section reference is read by a closed grammar, parsed by hand with no regex. The marker is the word `section` in any letter case, not preceded by a letter, digit or `_`, followed by whitespace, or the sign `§` with optional whitespace. The number is N or N.M in ASCII digits, and it must not run into a letter, digit, `_`, or a `.` followed by one. The vocabulary is enumerated in `SECTION_WORDS`, `SECTION_SIGNS` and `SECTION_REFERENCE_PARTS`. `named_tokens` emits each reference as its canonical token (`section 5.1`). `named_line_flags` resolves that token through `section_spans`: the blocks from each heading carrying the number (read by `heading_number`; the marker is optional there and the number may have any depth) up to the next heading of the same or a shallower level. Headings inside a fence are skipped, as `_blocks` skips them. A number no heading carries names nothing, and a Section token is never matched as text.
- R1: `Section N.M` names the `### N.M` subsection whatever its heading says after the number, its fenced functions included.
- R2: `Section N` names everything from `## N.` to the next `## ` heading.
- R3: an unmatched number names nothing and never widens.
- Conservation (#2559) is not loosened: `enforce_pinning` passes the conservation gate flags computed without Section tokens, so naming the section a test sits in does not let the test go.
- `complaint_answers` (#4551) leaves Section tokens out, so a revised line that only mentions a section answers nothing.
- `message_addressability.py`: the classifier resolves Section tokens through headings, as pinning does, and reports `section_headings` in `via`.
- `validate_completeness.py` and `error_path_coverage.py`: five completeness messages carried a section number that was not an address of what they complain about: template 0701's "section 5" and "section 8", "§10" in the assertions and fixtures checks, and "Section 10 owes each a test" in the error-path check. Each now omits the number, so those complaints still unlock only the functions and spans they name.

## What did not change

Text tokens, line ranges, ranges of numbered tests, the demanded-additions exemption, the regression class and the conservation tiers work as before. A plural such as `Sections 3.6 and 5.7` is outside the grammar and names nothing; #4554 tracks it.

## The real round

Replaying `named_tokens` and `named_line_flags` on the run's previous draft with the verdict that asked for the edits: the `### 5.1` heading, both edge-case lines, the `### 6.7` heading and its "No changes required" line read LOCKED on `main` and NAMED on this branch.
