# Implementation report: #4554

#4552 made a verdict's `Section N` or `Section N.M` name the draft block under the heading with that number, through a closed grammar that read one section per reference. A plural named nothing. A verdict saying "Update Sections 5.1 and 6.2 to ..." left every line under both headings locked, and the edit it asked for was refused, as the singular once was. One verdict in the real run behind #4551 and #4552 opens "Sections 3.6 and 5.7 specify that ...".

## What changed

- `revision_pinning.py`: a plural reference is read by a second closed grammar, parsed by hand with no regex, beside the singular one. Its vocabulary is enumerated in four constants: `SECTION_PLURAL_WORDS` (`sections`, in any letter case, not preceded by a letter, digit or `_`, then whitespace), `SECTION_PLURAL_SIGNS` (`§§`, not preceded by another `§`, then optional whitespace), `SECTION_LIST_SEPARATORS` (`,` directly after an item, then whitespace) and `SECTION_LIST_CONJUNCTIONS` (`and` in any letter case, with whitespace on both sides). An item is a number as the singular grammar reads it, N or N.M. A list has two or more items: the last two joined by `and`, every earlier pair by `,`. The list must end there; a separator or conjunction that carries it on to another item makes the whole reference name nothing.
- `section_references` returns every item of a plural, in order and each once, so `named_tokens` emits one canonical token per item (`section 5.1`, `section 6.2`) and everything downstream resolves them as it resolves a singular reference.
- R1: `Sections A and B` names exactly the union of what `Section A` and `Section B` name, and an item no heading carries names nothing.
- R2: `Sections A, B and C` names each item.
- R3: every other plural shape names nothing. The code's comment table lists each refused shape, and the tests enumerate the same list.
- `section_token_numbers` is new: the numbers a token is when the whole token is one reference, singular or plural. A plural quoted or backticked whole (`` `Sections 5.1 and 6.2` ``) is therefore a Section token, never a text token. The four readers that keep Section tokens away from text matching (`named_line_flags`, the conservation gate in `enforce_pinning`, `complaint_answers`, and the classifier in `message_addressability.py`) now ask it in place of the singular `section_token_number`. Without this, a quoted plural reached any block that happened to mention it, could let a test in that block go, and entered #4551's answers vocabulary.

## Decisions the issue left open

Each one takes the narrower reading.

- The joiners are exactly `,` and `and`, as R3 lists them. `or` (T3), `&` and `/` are refused.
- A comma before the final `and` (`Sections 5.1, 5.2, and 6.2`) is refused. R2's example has none, and `, and` is not one of the two listed joiners.
- A list of commas with no final `and` (`Sections 5.1, 5.2`) is refused: R2 names a comma list with a final `and`.
- `and` between earlier items (`Sections 5.1 and 5.2 and 6.2`), and a list carried on past its last pair (`Sections 5.1 and 5.2, 6.2`), are refused, not read in part.
- The comma takes whitespace after it and none before it.
- A plural with one item (`Sections 5.1 cover it`, `§§5.1`) is refused.
- Items are bare numbers. An item carrying its own marker ends the list, and the marked item is read as a singular reference: `Sections 5.1 and Section 6.2` names 6.2 only. `Section 5.1 and 6.2` stays a singular reference to 5.1, as under #4552.
- Words in the grammar are compared in lower case, as `section` already was, so `SECTIONS 5 AND 6` is accepted.

## What did not change

The singular grammar and its constants, text tokens, line ranges, ranges of numbered tests, the conservation tiers and the regression class. A Section reference, singular or plural, still names no test, and #4551's answers still leave Section tokens out.

## 7a. Loud-failure compliance (standard 0034)

None added or touched. The new readers return None or `()` for text that is not a reference; that is a parse result, not a failure path.
