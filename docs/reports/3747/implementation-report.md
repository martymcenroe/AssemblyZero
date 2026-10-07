# Implementation report: #3747

## A requirements conflict halts a roll only when it reproduces

`assemblyzero/workflows/requirements/nodes/analyze_requirements.py`, in `analyze_requirements`, after the #2462 filter and before the conflict message:

- When the first answer reports articulated conflicts, the gate asks the same model the same content once more (`_invoke(provider)` again) and prints `[N0c] N conflict(s) reported; asking again to confirm before halting (#3747).`
- `_articulated_conflicts(second)` is the second answer's conflicts that #2462 would file (none when it says the text is consistent). `_reported_again` matches a first-answer conflict against them by its pair of quoted criteria, in either order, without case or spacing, and with one quote allowed to contain the other, because a model asked twice may quote a longer or shorter span of the same sentence.
- A first-answer conflict the second answer does not repeat is printed as `[N0c] not reproduced, not filed:` with both criteria, and is neither filed nor halted on. When none repeat, the gate prints that the requirements are consistent, names the model, and proceeds. That return carries a `# fail-open:` ruling: it is the second ask's verdict, and each dropped conflict is printed.
- Only repeated conflicts reach `_format_conflict_message`, the telemetry and `file_all_conflicts`, exactly as before.
- A confirming ask that returns no verdict (unparseable, failed) leaves the first answer's conflicts standing: the gate halts and files as before. The second ask failed to answer; it did not disagree.

What prompted it, measured on boostgauge #2, whose body was unedited from 2026-08-16 until a clarifying edit on 2026-10-07: run 46 (23:07) consistent; run 48 (01:10) two conflicts, filed as #473 and #474; run 49 (01:17, after two clarifying sentences) a third, #475, whose two quotes state the same thing. Each answered on the issues; boostgauge #421 carries the runs.

## Left for #3748

#3747's requirements 2 (each verdict in the model record with its content fingerprint) and 3 (the unparseable-answer rate counted per model) are filed as #3748, so the first could land before the next roll.

## Fail-open baseline

Regenerated; only the totals change (9540 to 9552 sites, 556 to 557 findings), since the new site is ruled on in the code.
