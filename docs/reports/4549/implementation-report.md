# Implementation report: #4549

The range grammar from #4545 did not read a range whose endpoints were written as Markdown code. A resumed implementation-spec run's verdict said "Functions `test_req_060` through `test_req_130` in the Python test block in Section 10.1 ...". The grammar wanted whitespace or a dash right after the first endpoint and found a backtick, so the text was not a range. The endpoints still named themselves as backticked spans, and conservation refused the requested removal three times, naming the three tests between them that no other token happened to match. The run halted `edit_script_rejected`.

## What changed

- `assemblyzero/workflows/implementation_spec/revision_pinning.py`: an endpoint may stand in one pair of single backticks, each endpoint on its own: `` `test_req_060` through `test_req_130` ``, `` `T060` to `T130` ``, `` `test_req_060`–`test_req_130` ``. The range regex opens a backtick group before each endpoint and, through a conditional group, closes one only when one opened. The grammar table in the module carries the new row, and `named_test_ranges` reads the endpoints by group name.

## What did not change

Every form refused before stays refused, with or without backticks: other joiners, mixed prefixes, a reversed span, other identifier shapes, lower-case T ids, a word joiner without whitespace, an endpoint inside a word, a number not delimited. An unpaired backtick beside the joiner and an endpoint in double backticks are not ranges. A whole range inside one code span was already read as the bare form and still is. Conservation still refuses a test outside the range.
