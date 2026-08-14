## Summary

BoostGauge needs a configuration system for thresholds, polling intervals, visual preferences, and window behavior.

## Config file

Location: `~/.boostgauge/config.json` (or `%APPDATA%/boostgauge/config.json` on Windows)

```json
{
  "polling_interval_seconds": 2,
  "theme": "dark",
  "size": 300,
  "opacity": 0.9,
  "always_on_top": true,
  "position": {"x": 100, "y": 100},
  "thresholds": {
    "conpty": {"yellow": 30, "red": 60},
    "memory_percent": {"yellow": 60, "red": 80},
    "process_count": {"yellow": 300, "red": 500},
    "handle_count": {"yellow": 30000, "red": 50000}
  },
  "telltale_windows": {
    "short": 60,
    "medium": 600,
    "long": 3600
  },
  "show_driver_label": true,
  "show_digital_readout": true,
  "show_session_count": true
}
```

## CLI arguments

```
boostgauge [OPTIONS]

Options:
  --theme THEME          Visual theme (dark, light, neon, classic)
  --size PIXELS          Gauge diameter in pixels (default: 300)
  --poll SECONDS         Polling interval (default: 2)
  --opacity FLOAT        Window opacity 0.0-1.0 (default: 0.9)
  --no-topmost           Don't keep window on top
  --config PATH          Path to config file
  --reset-config         Reset config to defaults
```

## Config persistence

**Writes.** The app writes to the config file at exactly three moments and at no other time:

1. **First-run auto-create.** Launch finds no config file and creates one with defaults.
2. **Launch reset.** `--reset-config` rewrites the file to defaults before the app reads it. The flag has no further effect; the rest of the session proceeds as any other.
3. **Exit write.** The app writes the keys the user changed by hand during the session, and only those keys: `position` if the window was moved, `size` if it was resized. Every other key keeps whatever the file already holds, including edits made directly to the file while the app ran. Position and size are the only keys with a hand-change mechanism, so they are the only keys the exit write can ever touch. A session with no hand-made changes skips the exit write entirely.

**Reads are not restricted.** Launch reads the file after step 2, and the app re-reads it during the session; of the re-read values, only the threshold values — the keys under the `thresholds` object — are applied to the running session, so threshold edits take effect without a restart, while a direct edit to any non-threshold key (any key outside the `thresholds` object, `telltale_windows` included) leaves the running session unchanged; it is never applied mid-session, and the next launch reads the file as the exit-write rules leave it. Reading never modifies the file.

**Direct edits to the file while the app runs are the user's writes, not the app's.** The three moments above are the app's complete write behavior. After launch, the app's only write is the exit write, and the exit write never overwrites a key the user did not change by hand during the session. The launch writes (auto-create, reset) happen before the app reads the file and before any session activity exists. The file's content after quit is therefore the composition of the app's writes and the user's.

**Launch order** is: reset if flagged, then read the file (auto-create if missing), then apply CLI overrides in memory. CLI value overrides (`--theme`, `--size`, `--poll`, `--opacity`, `--no-topmost`) govern the running session; the app never writes them to the file. The window opens at the file's position, since no position flag exists, and at the CLI size when `--size` is given, otherwise the file's size. After a `--reset-config` launch the file holds defaults when it is read, so the window opens at the default position, and at the default size unless `--size` overrides it for the session.

**Persistence of `position` and `size` is independent**, each governed by its own table. Every row follows from the write rules above, and each row is an acceptance criterion below. Both tables hold one further condition fixed: no direct edit to the file during the session. The composition criterion in the acceptance list governs a session with one.

Position, which has no CLI flag and only ever changes by hand:

| ID | `--reset-config`? | Window moved by hand? | `position` in the file after quit (no direct edits) |
|---|---|---|---|
| P1 | no | no | unchanged |
| P2 | no | yes | the new position |
| P3 | yes | no | default |
| P4 | yes | yes | the new position |

Size, which has a CLI flag:

| ID | `--reset-config`? | `--size` given? | Window resized by hand? | `size` in the file after quit (no direct edits) |
|---|---|---|---|---|
| S1 | no | no | no | unchanged |
| S2 | no | no | yes | the new size |
| S3 | no | yes | no | unchanged; the CLI value is not written |
| S4 | no | yes | yes | the new size |
| S5 | yes | no | no | default |
| S6 | yes | no | yes | the new size |
| S7 | yes | yes | no | default; the CLI value is not written |
| S8 | yes | yes | yes | the new size |

`--config PATH` selects which config file is in play for the session and writes nothing by itself; the three write moments above apply to the selected file.

## State Variables and Ownership

Per AssemblyZero's variable-ownership discipline (the sibling ADR to ADR 0226): every claim about a variable's fate belongs to that variable's owner; any other mention cites the owner instead of asserting a value.

| Variable | Extension | Owner |
|---|---|---|
| File content per key at quit | every key in the config file | The three write moments, the exit-write criteria (including the collision rule for a key both directly edited and hand-changed), and the position/size tables (P1–P4, S1–S8) for their keys; all other content follows by composition |
| File bytes after an untouched session | the file verbatim | The byte-identical criterion, with its inline scope |
| Running-session values | the in-memory value of every key | The launch-order criterion and CLI overrides; the threshold hot-reload criterion for keys under `thresholds`; the non-threshold reload criterion for timing only — it states when file content is read, never what the file holds |
| Window geometry on screen | the window's position and size | The launch-behavior criteria and the hand-change mechanisms (drag, resize) |

Boundary term: **threshold values** are exactly the keys under the `thresholds` object (defined in the Reads paragraph); every other key is non-threshold.

## Acceptance Criteria

- [ ] First run with no config file creates one with defaults
- [ ] Launch order is reset, then read, then CLI overrides in memory; CLI value overrides govern the session and the app never writes them to the file
- [ ] With no CLI overrides, the window opens at the file's position and size
- [ ] Launched with `--reset-config` and no `--size`, the window opens at the default position and default size; launched with `--reset-config --size N`, it opens at the default position and size N while the file holds the default size
- [ ] Threshold values (the keys under the `thresholds` object) edited directly in the config file take effect without restart, and reading them never modifies the file
- [ ] The exit write writes exactly the keys the user hand-changed during the session and touches no other key: a direct file edit made while the app ran survives the exit write for every key the user did not also hand-change
- [ ] With a direct file edit during the session, the edited key holds the edited value after quit, unless the user also hand-changed that same key, in which case the hand-made value wins
- [ ] A session with no hand-made changes performs no exit write; if the session also found an existing config file at launch, was launched without `--reset-config`, and the file was not edited directly, the file is byte-identical after quit
- [ ] P1 — Position, no reset, not moved, no direct edits: `position` unchanged
- [ ] P2 — Position, no reset, moved, no direct edits: `position` holds the new position
- [ ] P3 — Position, reset, not moved, no direct edits: `position` holds the default
- [ ] P4 — Position, reset, moved, no direct edits: `position` holds the new position
- [ ] S1 — Size, no reset, no `--size`, not resized, no direct edits: `size` unchanged
- [ ] S2 — Size, no reset, no `--size`, resized, no direct edits: `size` holds the new size
- [ ] S3 — Size, no reset, `--size` given, not resized, no direct edits: `size` unchanged; the CLI value is not written
- [ ] S4 — Size, no reset, `--size` given, resized, no direct edits: `size` holds the new size
- [ ] S5 — Size, reset, no `--size`, not resized, no direct edits: `size` holds the default
- [ ] S6 — Size, reset, no `--size`, resized, no direct edits: `size` holds the new size
- [ ] S7 — Size, reset, `--size` given, not resized, no direct edits: `size` holds the default; the CLI value is not written
- [ ] S8 — Size, reset, `--size` given, resized, no direct edits: `size` holds the new size
- [ ] Invalid config values produce clear error messages
- [ ] A non-threshold key (e.g. `theme` or `telltale_windows.short`) edited directly in the config file while the app runs leaves the running session unchanged; the running session never applies it, and the next launch reads whatever the file holds at that point — content governed by the exit-write criteria above (a direct edit to a key the user also hand-changed is overwritten at quit; every other direct edit survives)

## Revision History

- **2026-08-09 — ruling on #235 (filed by run-issue7-181229's requirements-consistency gate):** The original text held both "CLI args override config" and "Position/size saved on exit" with no rule for a session that exits under an untouched CLI override. Operator ruling: CLI overrides are session-scoped and never persisted. On exit the app writes only hand-made changes (drag/resize) to the config file; a CLI-injected value the user never touched leaves the config file unchanged. Acceptance criteria 2 and 3 rewritten to carry the ruling.
- **2026-08-10 — ruling on #240 (filed by run-issue7-233727's requirements-consistency gate):** The #235 ruling's blanket sentence ("an override is never written back to the config file") contradicted `--reset-config`, whose entire purpose is to write defaults into the config file. Operator ruling: the session-only rule governs value overrides; `--reset-config` is the one deliberate exception and rewrites the config file to defaults. `--config` selects the file and writes nothing by itself.
- **2026-08-10 — ruling on #249 (filed by run-issue7-031357's requirements-consistency gate):** "Position always persists on exit" read as an unconditional write, contradicting "persists only changes the user made by hand" for a session in which the window was never moved. Operator ruling: persistence is change-driven — exit writes only hand-made changes, and an untouched session leaves the config file byte-identical, preserving any direct edits made to the file while the app ran. The "always persists" sentence rephrased to its intent: position only ever changes by hand, so a moved window always keeps its new position.
- **2026-08-10 — ruling on #252 (filed by run-issue7-094316's requirements-consistency gate):** The #249 sentence's byte-identical guarantee, written without its exception, contradicted the #240 carve-out when the app is launched with `--reset-config` and exited untouched. Operator ruling: the reset wins — `--reset-config` is a config-file command and rewrites the file regardless of hand-made changes; the byte-identical guarantee is scoped to sessions launched without a config-file command. Both sentences now carry the exception inline.
- **2026-08-11 — ruling on #273/#274/#275 (filed by run-issue7-083155's requirements-consistency gate):** Three conflicts from one run, each pitting a persistence sentence against `--reset-config`'s "rewrites the file regardless." Operator ruling: **the reset happens at launch.** `--reset-config` rewrites the file to defaults before the app reads it; the session then behaves normally and exit writes hand-made changes as usual, so a window moved during a reset session keeps its new position, and that session's own window opens at the defaults. The prose paragraph that produced seven conflicts across five rulings was replaced by an ordered rule and a decision table.
- **2026-08-11 — repair after #277/#278/#279 (filed by run-issue7-140703's requirements-consistency gate):** All three conflicts were in text introduced by the #273/#274/#275 rewrite itself, and none required a new behavioral decision. (1) "Nothing else touches it" accidentally forbade the mid-session reads that hot threshold reload requires; the constraint is now scoped to writes, with reads explicitly unrestricted (#277). (2) The single table bundled position and size into one "moved or resized" condition, so a session launched with `--size` whose window was only moved appeared to write the CLI size to the file; position and size are independent variables with different rules, because size has a CLI flag and position does not, and each now has its own table (#278). The four-condition count that forced the split is AssemblyZero ADR 0226's split rule applied. (3) "Opens at the default position and size" overstated the reset launch by one noun; with `--reset-config --size N` the session runs at the CLI size while the file holds the default (#279). Two latent gaps no run had yet reported were closed in the same pass: the exit write is defined as a per-key patch, so direct file edits survive an exit that writes position or size; and the byte-identical guarantee is stated with its no-reset scope inline, so the #252 collision shape cannot recur. First-run auto-create was also added to the enumerated write moments, which the previous "exactly three things" sentence omitted.
- **2026-08-11 — repair after #280/#281 (filed by run-issue7-152239's requirements-consistency gate):** Both conflicts paired a table row's final-state claim against #249's standing rule that direct file edits survive. The rows were written as if the app were the file's only writer; the user can edit the file while the app runs, so the file's final content is a composition of the app's writes and the user's, and a row claiming "holds the default" is false when a direct edit lands after the launch reset. No behavior changed and no new ruling was needed: the app's writes were already fully specified, and #249 already governed direct edits. The repair is scope. Every table row now names its held-fixed condition ("no direct edits"), a composition criterion states what a direct edit leaves behind, and the byte-identical guarantee carries the same scope. The underlying rule, from the same body of work ADR 0226 draws on: state post-conditions only over variables the system controls. The config file is shared with the user, so the app's requirement is its write behavior; file content follows by composition.
- **2026-08-11 — repair after #282/#283 (filed by the standalone pre-check, AssemblyZero #2221, on its first run against this issue):** The first conflicts caught without spending a roll: the pre-check invokes the same gate a roll runs, offline, and it found two overclaimed guarantees in the prose around the tables. (1) "The app never overwrites a key the user did not change by hand" was written as a blanket claim about the app; the launch reset exists to overwrite untouched keys. The claim is now scoped to the exit write, which is what it was always about (#282). (2) The byte-identical guarantee did not exclude a first run, where auto-create writes a file from nothing; it now requires that the session found an existing config file at launch (#283). No behavior changed and no ruling was needed. Both defects are the universal-dressed-as-conditional disease recurring in the prose that remains around the tables.
- **2026-08-13 — ruling on #290 (filed by the standalone pre-check during the pre-roll verification pass):** Criterion A's survival claim was unqualified — "a direct file edit survives an exit that also writes a new position or size" — while criterion B ruled that the hand-made value wins a same-key collision. An implementer following A would suppress the exit write for any directly-edited key; one following B would let it win. Operator ruling: B's semantics stand — the exit write's read-then-patch design produces them by composition — and A now carries the per-key qualifier: the exit write writes exactly the hand-changed keys, and a direct edit survives for every key not also hand-changed. Repaired in both this issue and LLD-007 criterion 6 (commit `92821f8` on PR #285), because the roll resumes at the spec stage reusing the LLD.
- **2026-08-13 — ruling on #291 (filed by the standalone pre-check's second verification run):** "The app re-reads it during the session so that threshold edits take effect" left two readings for a mid-session direct edit to a non-threshold key: whole-file hot-reload or threshold-only. Acceptance criterion 5 tests only thresholds, which pass under both readings, so no criterion discriminated. Operator ruling: threshold-only, matching the approved design — LLD-007's tick applies re-read threshold values and nothing else. The prose now scopes the live effect to thresholds (the re-read itself stays unrestricted, per #277), a discriminating criterion pins the non-threshold case, and LLD-007 gains matching criterion 23 and test row 051.
- **2026-08-13 — ruling on #292 (filed by the standalone pre-check's third verification run):** "Threshold" was never defined, and `telltale_windows` — a separate config object whose durations govern how threshold computations window their samples — was arguably either side of the #291 split: not named `thresholds`, but threshold-adjacent in function. Operator ruling: **threshold values are exactly the keys under the `thresholds` object**; every other key, `telltale_windows` included, is non-threshold and defers to the next launch. Grounds: the term now maps mechanically to the config's own structure, and the approved design already reads this way — LLD-007 types `TelltaleWindows` apart from thresholds, its reload path applies threshold values only, and live-resizing a peak-hold window would force re-deriving the telltale buffers mid-session. The definition landed in the prose and in acceptance criterion 5; criterion 23's exemplars now include `telltale_windows.short`, pinning the discriminating instance.
- **2026-08-13 — ruling on #294 (filed by the roll's launch gate, the fourth conflict pairing):** The #291 repair's own criterion carried an unconditional promise — a directly edited non-threshold key "takes effect at the next launch" — which is false for `position` and `size`, non-threshold keys WITH hand-change mechanisms, when the same key is also hand-changed in the session: criterion 7's collision rule overwrites the edit at quit. The universal-dressed-as-conditional disease this history already records twice, this time introduced by a repair. Operator ruling: the reload criterion states only WHEN file content is read — never mid-session for non-threshold keys, at the next launch from whatever the file then holds — and never claims WHAT the file will hold; persistence stays owned by criteria 6 and 7. Criterion 23 and the Reads prose both rescoped. The LLD was deliberately not hand-edited this round: a conflict ruling makes the next launch redraw it fresh from this corrected text, so LLD edits would be discarded by the machine's own rule.
- **2026-08-14 — post-roll retrofit per #284 and #296 (no behavior change):** With the pipeline run complete (PR #298 merged to the arc), the two graduations deferred to protect the certified chain landed together. The decision tables carry row IDs (P1–P4, S1–S8) and each row criterion carries its ID, per ADR 0226's exact mode — the criterion-to-test join becomes an exact ID join. A State Variables and Ownership section declares each variable's extension and owning criteria group per AssemblyZero's variable-ownership discipline (AZ #2314), making the conflict class behind rulings #235 through #294 structurally unwritable rather than serially findable. No requirement's meaning changed; both edits are form.






