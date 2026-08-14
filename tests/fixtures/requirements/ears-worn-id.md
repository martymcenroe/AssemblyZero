# feat: needle rendering

Synthetic fixture for the #2368 ruling: a requirement sentence carries no ID.

Every bullet under `## Requirements` here is a well-formed EARS sentence wearing
a criterion ID, in the separators an author actually reaches for. All five must
be reported as wearing an ID rather than as matching no pattern -- the sentence
underneath each one is correct, and the repair is to delete the prefix.

The acceptance criteria below are correctly tagged. They join to the table rows,
which is what an ID is for, and nothing about this ruling changes them. The
fixture holds both halves on purpose: the same document shows where a prefix
belongs and where it does not.

## Requirements

- R1 — The renderer shall place the needle at the value's angle.
- R2. WHEN the value changes the renderer shall redraw the needle.
- R3: WHILE a redraw is in flight the renderer shall drop further updates.
- R4) IF the value is out of range THEN the renderer shall clamp it.
- R5 WHERE the telltale is enabled the renderer shall draw it behind the needle.

Rendering depends on two independent conditions.

| ID | Value in range? | Telltale enabled? | What the frame shows |
|---|---|---|---|
| N1 | no | no | the needle clamped to the nearest limit |
| N2 | no | yes | the needle clamped, and the telltale behind it |
| N3 | yes | no | the needle at the value's angle |
| N4 | yes | yes | the needle at the value's angle, and the telltale behind it |

## Acceptance Criteria

- [ ] N1. Out of range, telltale off: the frame shows the needle clamped to the nearest limit
- [ ] N2. Out of range, telltale on: the frame shows the needle clamped, and the telltale behind it
- [ ] N3. In range, telltale off: the frame shows the needle at the value's angle
- [ ] N4. In range, telltale on: the frame shows the needle at the value's angle, and the telltale behind it
